"""OpenAI-compatible client (Ollama by default). Duck-types the upstream ModelClient
so the upstream classifiers can use it: `await client(model_id, messages, ...) -> LLMResponse`."""
import os, time
from dataclasses import dataclass, field
from openai import AsyncOpenAI

@dataclass
class LLMResponse:
    model_id: str
    completion: str
    reasoning: str = ""
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    duration: float = 0.0
    api_model: str = ""           # model id the provider *returned* (code review 2026-09-01)
    provider: str = ""            # upstream provider when routed (OpenRouter), else ""

def _msgs(messages):
    return [{"role": (m.role.value if hasattr(m.role, "value") else m.role), "content": m.content}
            if not isinstance(m, dict) else m for m in messages]

class OpenAICompatClient:
    def __init__(self, base_url: str | None = None, api_key: str = "ollama", timeout: float = 1800.0):
        # A hung call must not hold its semaphore slot forever; timeout raises so the
        # runner's retry loop actually triggers.
        self.client = AsyncOpenAI(base_url=base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                                  api_key=api_key, timeout=timeout)

    async def __call__(self, model_id: str, messages, max_tokens: int = 4000, temperature: float = 1.0,
                       seed: int | None = None, **kw) -> LLMResponse:
        t = time.time()
        extra = {"seed": seed} if seed is not None else {}
        r = await self.client.chat.completions.create(model=model_id, messages=_msgs(messages),
                                                      max_tokens=max_tokens, temperature=temperature, **extra)
        m = r.choices[0].message
        reasoning = getattr(m, "reasoning", None) or (m.model_extra or {}).get("reasoning", "") or ""
        provider = (r.model_extra or {}).get("provider", "") if hasattr(r, "model_extra") else ""
        return LLMResponse(model_id=model_id, completion=m.content or "", reasoning=reasoning,
                           stop_reason=r.choices[0].finish_reason,
                           usage=r.usage.model_dump() if r.usage else {}, duration=time.time() - t,
                           api_model=getattr(r, "model", "") or "", provider=provider or "")
