"""Single entrypoint. `ild run --config configs/smoke.yaml`."""
import argparse, asyncio, json, os, random, subprocess, sys, time, uuid
from pathlib import Path
import yaml
from dotenv import load_dotenv
from .prompts import load_conditions, load_variants, build_system_prompt, build_user_prompt
from .client import OpenAICompatClient
from . import parse, upstream

ROOT = Path(__file__).resolve().parents[2]

def git_hash(path=ROOT):
    try: return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    except Exception: return "unknown"

def dataset_version(bench: Path):
    try: return subprocess.check_output(["git", "-C", str(bench), "describe", "--tags", "--always", "--dirty"], text=True).strip()
    except Exception: return "unknown"

async def run_episode(client, cfg, cond, variant, variants, sample, sem):
    sys_p = build_system_prompt(cond, variant, variants)
    usr_p = build_user_prompt(cond)
    async with sem:
        for attempt in range(cfg.get("retries", 1) + 1):
            try:
                r = await client(cfg["model"], [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}],
                                 max_tokens=cfg.get("max_tokens", 4000), temperature=cfg.get("temperature", 1.0))
                break
            except Exception as ex:
                if attempt == cfg.get("retries", 1): raise
                await asyncio.sleep(2 ** attempt)
    final_text, inline_reasoning = parse.strip_reasoning(r.completion)
    reasoning = "\n".join(x for x in (r.reasoning, inline_reasoning) if x)
    actions = parse.parse_system_log(final_text)
    log_present, entries = parse.parse_model_log(final_text)
    parse.match(actions, entries)
    return {
        "episode_id": f"{cond.condition_id}__{variant}__s{sample}__{uuid.uuid4().hex[:8]}",
        "condition_id": cond.condition_id, "scenario": cond.scenario,
        "goal_type": cond.goal_type, "goal_value": cond.goal_value, "urgency_type": cond.urgency_type,
        "prompt_variant": variant, "sample": sample, "model": cfg["model"],
        "system_prompt": sys_p, "user_prompt": usr_p,
        "response": r.completion, "reasoning": reasoning, "final_text": final_text,
        "system_log": parse.to_dict(actions), "model_log": parse.to_dict(entries),
        "log_present": log_present,
        "unclosed_reasoning": parse.has_unclosed_reasoning(r.completion),
        "logged": parse.episode_logged(log_present, actions, entries),   # pre-evaluator
        "harmful": None,                                                  # filled by classify step
        "usage": r.usage, "duration_s": round(r.duration, 2), "stop_reason": r.stop_reason,
    }

async def cmd_run(cfg_path: Path, resume: str | None = None):
    load_dotenv(ROOT / ".env")
    cfg = yaml.safe_load(cfg_path.read_text())
    bench = (ROOT / cfg.get("benchmark_dir", "../INSIDER_LLM_DETECTION_BENCHMARK")).resolve()
    conds = load_conditions(bench / "data/conditions.jsonl")
    variants = load_variants(bench / "prompts")
    sel = cfg.get("conditions")
    if sel: conds = [c for c in conds if c.condition_id in sel]
    run_id = resume or cfg.get("run_id") or f"{time.strftime('%Y%m%d-%H%M%S')}_{cfg['model'].replace('/', '_').replace(':', '-')}"
    out = ROOT / "results" / run_id; out.mkdir(parents=True, exist_ok=True)
    done = set()
    if resume and (out / "episodes.jsonl").exists():
        for l in (out / "episodes.jsonl").read_text().splitlines():
            if l.strip():
                e = json.loads(l); done.add((e["condition_id"], e["prompt_variant"], e["sample"]))
    random.seed(cfg.get("seed", 0))
    meta = {"run_id": run_id, "config": cfg, "git_hash": git_hash(), "upstream_commit": upstream.upstream_commit(),
            "dataset_version": dataset_version(bench), "seed": cfg.get("seed", 0), "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not (out / "meta.json").exists(): (out / "meta.json").write_text(json.dumps(meta, indent=2))
    client = OpenAICompatClient(base_url=cfg.get("base_url"))
    sem = asyncio.Semaphore(cfg.get("concurrency", 4))
    jobs = [run_episode(client, cfg, c, v, variants, s, sem)
            for c in conds for v in cfg.get("variants", ["none", "A", "B"]) for s in range(cfg.get("samples_per_condition", 1))
            if (c.condition_id, v, s) not in done]
    if done: print(f"resuming {run_id}: {len(done)} episodes already done")
    print(f"{run_id}: {len(jobs)} episodes -> {out}")
    n = 0
    with (out / "episodes.jsonl").open("a") as f:
        for coro in asyncio.as_completed(jobs):
            try:
                ep = await coro
            except Exception as ex:
                print("  FAILED:", ex); continue
            f.write(json.dumps(ep, ensure_ascii=False) + "\n"); f.flush(); n += 1
            print(f"  [{n}/{len(jobs)}] {ep['condition_id']} {ep['prompt_variant']} actions={len(ep['system_log'])} log={ep['logged']}")
    print("done")

def cmd_reparse(run_dir: Path):
    """Re-derive final_text / system_log / model_log / logged from stored responses (parser fixes)."""
    f = run_dir / "episodes.jsonl"; eps = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    changed = 0
    for e in eps:
        final_text, inline = parse.strip_reasoning(e["response"])
        actions = parse.parse_system_log(final_text)
        log_present, entries = parse.parse_model_log(final_text)
        parse.match(actions, entries)
        new = {"final_text": final_text, "system_log": parse.to_dict(actions), "model_log": parse.to_dict(entries),
               "log_present": log_present, "unclosed_reasoning": parse.has_unclosed_reasoning(e["response"]),
               "logged": parse.episode_logged(log_present, actions, entries)}
        if any(e.get(k) != v for k, v in new.items()): changed += 1
        e.update(new)
    f.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in eps))
    print(f"{run_dir.name}: reparsed {len(eps)} episodes, {changed} changed")

def main():
    ap = argparse.ArgumentParser(prog="ild")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--config", type=Path, required=True)
    r.add_argument("--resume", help="existing run_id to continue; finished episodes are skipped")
    rp = sub.add_parser("reparse"); rp.add_argument("--run", type=Path, required=True, nargs="+")
    a = ap.parse_args()
    if a.cmd == "run": asyncio.run(cmd_run(a.config, a.resume))
    elif a.cmd == "reparse":
        for r in a.run: cmd_reparse(r)

if __name__ == "__main__": main()
