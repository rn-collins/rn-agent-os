"""Model router — local-first, frontier fallback, risk-tiered.

Policy:
  - routine tasks  -> local (Ollama) first; frontier only if local unavailable.
  - high-stakes tasks (client-facing claims/disclosure language) -> prefer frontier if a key is
    set; else local; else the deterministic 'stub' (so the engine never hard-fails offline).

The agents in this repo are rule-based and do not REQUIRE an LLM; the router is used for optional
enrichment and for the audit-narrative polish. Everything degrades gracefully with zero keys.
"""
from __future__ import annotations
import os, json


class ModelRouter:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.allow_frontier = os.getenv("ALLOW_FRONTIER", "1") == "1"

    # ---- provider availability -------------------------------------------
    def _local_up(self) -> bool:
        try:
            import httpx
            httpx.get(f"{self.ollama_host}/api/tags", timeout=1.5)
            return True
        except Exception:
            return False

    def providers(self) -> list[str]:
        p = []
        if self._local_up():
            p.append("local")
        if self.allow_frontier and self.anthropic_key:
            p.append("anthropic")
        if self.allow_frontier and self.openai_key:
            p.append("openai")
        return p

    def available(self) -> bool:
        return bool(self.providers())

    # ---- routing ----------------------------------------------------------
    def _order(self, complexity: str) -> list[str]:
        p = self.providers()
        if complexity == "high":
            # frontier first for high-stakes, then local
            front = [x for x in p if x in ("anthropic", "openai")]
            local = [x for x in p if x == "local"]
            return front + local + ["stub"]
        # routine: local first
        local = [x for x in p if x == "local"]
        front = [x for x in p if x in ("anthropic", "openai")]
        return local + front + ["stub"]

    def complete(self, prompt: str, complexity: str = "routine", want_json: bool = False,
                 max_attempts: int = 2) -> dict:
        last_err = None
        for provider in self._order(complexity):
            for _ in range(max_attempts if provider != "stub" else 1):
                try:
                    text = self._call(provider, prompt, want_json)
                    return {"provider": provider, "text": text,
                            "json": _try_json(text) if want_json else None}
                except Exception as e:  # noqa
                    last_err = f"{provider}:{e.__class__.__name__}"
        return {"provider": "none", "text": "", "error": last_err}

    def _call(self, provider: str, prompt: str, want_json: bool) -> str:
        if provider == "stub":
            # deterministic offline provider: never fails; used when nothing else is up
            return json.dumps({"note": "stub-response (no model configured)"}) if want_json else \
                "[stub] no model configured; rule-based agents produced the result."
        import httpx
        if provider == "local":
            r = httpx.post(f"{self.ollama_host}/api/generate",
                           json={"model": self.ollama_model, "prompt": prompt,
                                 "stream": False, **({"format": "json"} if want_json else {})},
                           timeout=60)
            r.raise_for_status()
            return r.json()["response"]
        if provider == "anthropic":
            r = httpx.post("https://api.anthropic.com/v1/messages",
                           headers={"x-api-key": self.anthropic_key,
                                    "anthropic-version": "2023-06-01"},
                           json={"model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                                 "max_tokens": 1024,
                                 "messages": [{"role": "user", "content": prompt}]},
                           timeout=60)
            r.raise_for_status()
            return r.json()["content"][0]["text"]
        if provider == "openai":
            r = httpx.post("https://api.openai.com/v1/chat/completions",
                           headers={"Authorization": f"Bearer {self.openai_key}"},
                           json={"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                                 "messages": [{"role": "user", "content": prompt}]},
                           timeout=60)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        raise ValueError(provider)


def _try_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


if __name__ == "__main__":
    mr = ModelRouter()
    print("providers:", mr.providers() or ["(none — will use stub)"])
    print(mr.complete("Say ok.", complexity="routine"))
