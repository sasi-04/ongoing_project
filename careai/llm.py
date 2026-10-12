"""Optional local LLM (Ollama). Every caller must work when this returns None."""
import json, urllib.request
from . import config

_avail = None


def available() -> bool:
    global _avail
    if config.LLM_MODE == "off":
        return False
    if _avail is None:
        try:
            urllib.request.urlopen(config.OLLAMA_URL + "/api/tags", timeout=1.0)
            _avail = True
        except Exception:
            _avail = False
    return _avail


def generate(prompt: str, system: str = "", timeout: float = 60.0):
    """Return text from the local model or None if unavailable/failed."""
    if not available():
        return None
    body = json.dumps({"model": config.OLLAMA_MODEL, "prompt": prompt, "system": system,
                       "stream": False, "options": {"temperature": 0.2}}).encode()
    req = urllib.request.Request(config.OLLAMA_URL + "/api/generate", body,
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["response"].strip()
    except Exception:
        return None
