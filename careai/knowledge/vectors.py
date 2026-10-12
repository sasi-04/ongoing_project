"""Vector index with pluggable backends.
 - dense: Ollama embeddings (default model nomic-embed-text), cached on disk
 - tfidf: dependency-free fallback
Selected via CAREAI_EMBED=auto|dense|tfidf. To use Chroma/pgvector, implement the same two methods
(scores, max_sim) and return it from make_index().
"""
import hashlib, json, math, os, re, urllib.request
from collections import Counter
from .. import config

_TOK = re.compile(r"[a-z0-9]+")
EMBED_MODEL = os.getenv("CAREAI_EMBED_MODEL", "nomic-embed-text")
EMBED_MODE = os.getenv("CAREAI_EMBED", "auto")
_CACHE_PATH = config.DATA_DIR / ".embed_cache.json"
_cache = None


def _tok(s):
    return _TOK.findall(s.lower())


class TfidfIndex:
    kind = "tfidf"

    def __init__(self, docs: dict):
        self.ids = list(docs)
        toks = {i: _tok(t) for i, t in docs.items()}
        df = Counter(w for ts in toks.values() for w in set(ts))
        n = len(docs)
        self.idf = {w: math.log((1 + n) / (1 + c)) + 1 for w, c in df.items()}
        self.vecs = {i: self._vec(ts) for i, ts in toks.items()}

    def _vec(self, ts):
        tf = Counter(ts)
        v = {w: c * self.idf.get(w, 0.0) for w, c in tf.items() if w in self.idf}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    def scores(self, query):
        q = self._vec(_tok(query))
        return {i: sum(x * v.get(w, 0.0) for w, x in q.items()) for i, v in self.vecs.items()}

    def max_sim(self, query):
        s = self.scores(query)
        return max(s.values(), default=0.0)


def _embed(text):
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(_CACHE_PATH))
        except Exception:
            _cache = {}
    key = EMBED_MODEL + hashlib.sha1(text.encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    body = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(config.OLLAMA_URL + "/api/embeddings", body, {"Content-Type": "application/json"})
    v = json.loads(urllib.request.urlopen(req, timeout=30).read())["embedding"]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    _cache[key] = [x / n for x in v]
    return _cache[key]


def save_cache():
    if _cache:
        try:
            json.dump(_cache, open(_CACHE_PATH, "w"))
        except Exception:
            pass


_ollama_available = None


def _probe_ollama():
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available
    try:
        req = urllib.request.Request(config.OLLAMA_URL + "/api/tags")
        with urllib.request.urlopen(req, timeout=0.3) as resp:
            _ollama_available = (resp.status == 200)
    except Exception:
        _ollama_available = False
    return _ollama_available


class DenseIndex:
    kind = "dense"

    def __init__(self, docs: dict):
        self.vecs = {i: _embed(t) for i, t in docs.items()}
        save_cache()

    def scores(self, query):
        q = _embed(query)
        return {i: sum(a * b for a, b in zip(q, v)) for i, v in self.vecs.items()}

    def max_sim(self, query):
        return max(self.scores(query).values(), default=0.0)


def make_index(docs: dict):
    if EMBED_MODE == "dense" or (EMBED_MODE != "tfidf" and _probe_ollama()):
        try:
            return DenseIndex(docs)
        except Exception:
            if EMBED_MODE == "dense":
                raise
    return TfidfIndex(docs)

