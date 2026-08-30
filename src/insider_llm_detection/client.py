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

class OpenAICompatClient:
    def __init__(self, base_url: str | None = None, api_key: str = "ollama"):
        self.client = AsyncOpenAI(base_url=base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                                  api_key=api_key)

    async def __call__(self, model_id: str, messages, max_tokens: int = 4000, temperature: float = 1.0, **kw) -> LLMResponse:
        t = time.time()
        msgs = [{"role": (m.role.value if hasattr(m.role, "value") else m.role), "content": m.content}
                if not isinstance(m, dict) else m for m in messages]
        r = await self.client.chat.completions.create(model=model_id, messages=msgs,
                                                      max_tokens=max_tokens, temperature=temperature)
        m = r.choices[0].message
        reasoning = getattr(m, "reasoning", None) or (m.model_extra or {}).get("reasoning", "") or ""
        return LLMResponse(model_id=model_id, completion=m.content or "", reasoning=reasoning,
                           stop_reason=r.choices[0].finish_reason,
                           usage=dict(r.usage) if r.usage else {}, duration=time.time() - t)
