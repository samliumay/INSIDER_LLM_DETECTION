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
    try:
        h = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        return h + ("-dirty" if git_dirty(path) else "")
    except Exception: return "unknown"

def git_dirty(path) -> bool:
    try:
        return bool(subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True).strip())
    except Exception:
        return False

def dataset_version(bench: Path):
    try: return subprocess.check_output(["git", "-C", str(bench), "describe", "--tags", "--always", "--dirty"], text=True).strip()
    except Exception: return "unknown"

def model_digest(base_url: str | None, model: str) -> str:
    """Ollama tags (`:cloud` included) are mutable; the digest pins the actual weights.
    A digest change mid-study means a different model (decisions.md 2026-08-31)."""
    import urllib.request
    try:
        root = (base_url or "http://localhost:11434/v1").split("/v1")[0]
        with urllib.request.urlopen(root + "/api/tags", timeout=10) as r:
            for m in json.load(r).get("models", []):
                if m.get("name") == model or m.get("model") == model:
                    return m.get("digest", "unknown")
    except Exception:
        pass
    return "unknown"

async def run_episode(client, cfg, cond, variant, variants, sample, sem):
    sys_p = build_system_prompt(cond, variant, variants)
    usr_p = build_user_prompt(cond)
    async with sem:
        for attempt in range(cfg.get("retries", 1) + 1):
            try:
                r = await client(cfg["model"], [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}],
                                 max_tokens=cfg.get("max_tokens", 4000), temperature=cfg.get("temperature", 1.0),
                                 seed=cfg.get("seed", 0) + sample)
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
        "logged": parse.episode_logged(log_present, actions, entries,
                                       instructed=variant in ("A", "B")),   # pre-evaluator
        "harmful": None,                                                  # filled by classify step
        "usage": r.usage, "duration_s": round(r.duration, 2), "stop_reason": r.stop_reason,
    }

async def cmd_run(cfg_path: Path, resume: str | None = None, allow_dirty: bool = False):
    load_dotenv(ROOT / ".env")
    cfg = yaml.safe_load(cfg_path.read_text())
    bench = (ROOT / cfg.get("benchmark_dir", "../INSIDER_LLM_DETECTION_BENCHMARK")).resolve()
    # Reproducibility comes from config + commit + seed: a run from a dirty tree cannot be
    # reconstructed from git, so refuse unless explicitly allowed (and then stamp the run).
    dirty = [name for name, p in (("code", ROOT), ("benchmark", bench)) if git_dirty(p)]
    if dirty and not allow_dirty:
        sys.exit(f"refusing to run: uncommitted changes in {' and '.join(dirty)} repo(s). "
                 f"Commit first, or pass --allow-dirty to mark the run non-reportable.")
    conds = load_conditions(bench / "data/conditions.jsonl")
    variants = load_variants(bench / "prompts")
    sel = cfg.get("conditions")
    if sel: conds = [c for c in conds if c.condition_id in sel]
    run_id = resume or cfg.get("run_id") or f"{time.strftime('%Y%m%d-%H%M%S')}_{cfg['model'].replace('/', '_').replace(':', '-')}"
    out = ROOT / "results" / run_id; out.mkdir(parents=True, exist_ok=True)
    done = set()
    if resume:
        if (out / "meta.json").exists():
            old_cfg = json.loads((out / "meta.json").read_text()).get("config")
            if old_cfg != cfg:
                sys.exit(f"refusing to resume {run_id}: config differs from the one in meta.json. "
                         f"Start a new run, or restore the original config.")
        if (out / "episodes.jsonl").exists():
            for l in (out / "episodes.jsonl").read_text().splitlines():
                if l.strip():
                    e = json.loads(l); done.add((e["condition_id"], e["prompt_variant"], e["sample"]))
    random.seed(cfg.get("seed", 0))
    meta = {"run_id": run_id, "config": cfg, "git_hash": git_hash(), "upstream_commit": upstream.upstream_commit(),
            "dataset_version": dataset_version(bench), "seed": cfg.get("seed", 0),
            "model_digest": model_digest(cfg.get("base_url"), cfg["model"]),
            "allow_dirty": bool(dirty), "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not (out / "meta.json").exists(): (out / "meta.json").write_text(json.dumps(meta, indent=2))
    api_key = os.environ.get(cfg["api_key_env"]) if cfg.get("api_key_env") else "ollama"
    if not api_key:
        sys.exit(f"refusing to run: {cfg['api_key_env']} is not set (add it to .env)")
    client = OpenAICompatClient(base_url=cfg.get("base_url"), api_key=api_key)
    sem = asyncio.Semaphore(cfg.get("concurrency", 4))

    async def guarded(c, v, s):
        try:
            return await run_episode(client, cfg, c, v, variants, s, sem)
        except Exception as ex:
            return {"_failed": True, "condition_id": c.condition_id, "prompt_variant": v,
                    "sample": s, "error": repr(ex)}
    jobs = [guarded(c, v, s)
            for c in conds for v in cfg.get("variants", ["none", "A", "B"]) for s in range(cfg.get("samples_per_condition", 1))
            if (c.condition_id, v, s) not in done]
    if done: print(f"resuming {run_id}: {len(done)} episodes already done")
    print(f"{run_id}: {len(jobs)} episodes -> {out}")
    n = failed = 0
    with (out / "episodes.jsonl").open("a") as f, (out / "failures.jsonl").open("a") as ff:
        for coro in asyncio.as_completed(jobs):
            ep = await coro
            if ep.get("_failed"):
                failed += 1
                ff.write(json.dumps(ep, ensure_ascii=False) + "\n"); ff.flush()
                print(f"  FAILED {ep['condition_id']} {ep['prompt_variant']} s{ep['sample']}: {ep['error']}")
                continue
            f.write(json.dumps(ep, ensure_ascii=False) + "\n"); f.flush(); n += 1
            print(f"  [{n}/{len(jobs)}] {ep['condition_id']} {ep['prompt_variant']} actions={len(ep['system_log'])} log={ep['logged']}")
    print(f"done: {n} ok, {failed} failed" + (f" (see {out / 'failures.jsonl'})" if failed else ""))

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
               "logged": parse.episode_logged(log_present, actions, entries,
                                              instructed=e.get("prompt_variant") in ("A", "B"))}
        if any(e.get(k) != v for k, v in new.items()): changed += 1
        e.update(new)
    f.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in eps))
    print(f"{run_dir.name}: reparsed {len(eps)} episodes, {changed} changed")

def main():
    ap = argparse.ArgumentParser(prog="ild")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--config", type=Path, required=True)
    r.add_argument("--resume", help="existing run_id to continue; finished episodes are skipped")
    r.add_argument("--allow-dirty", action="store_true",
                   help="run despite uncommitted changes; the run is stamped non-reportable")
    rp = sub.add_parser("reparse"); rp.add_argument("--run", type=Path, required=True, nargs="+")
    a = ap.parse_args()
    if a.cmd == "run": asyncio.run(cmd_run(a.config, a.resume, a.allow_dirty))
    elif a.cmd == "reparse":
        for r in a.run: cmd_reparse(r)

if __name__ == "__main__": main()
