"""Central configuration. Override via environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.getenv("CAREAI_DB", str(DATA_DIR / "careai.db")))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("CAREAI_MODEL", "llama3.1:8b")
LLM_MODE = os.getenv("CAREAI_LLM", "auto")  # auto | on | off

ROUTER_THRESHOLD = 0.5
# Fusion weights for hybrid retrieval (vector, graph, rules). Tunable / learnable.
FUSION_WEIGHTS = {"vector": 0.45, "graph": 0.35, "rule": 0.20}
FEEDBACK_CLAMP = (0.3, 2.0)

# Keyword -> flag extraction (transparent, editable, no ML needed for MVP)
FLAG_KEYWORDS = {
    "anxiety": ["anxious", "anxiety", "panic", "worried", "fearful"],
    "sensory_overload": ["noise", "loud", "overwhelmed", "sensory", "lights", "covers ears"],
    "meltdown": ["meltdown", "tantrum", "outburst", "aggress"],
    "elopement": ["runs out", "elope", "leaves the room", "wanders"],
    "nonverbal": ["nonverbal", "non-verbal", "minimally verbal", "no spoken"],
    "decoding_difficulty": ["decod", "sound out", "letter reversal", "slow reading", "spelling errors"],
    "inattention": ["distract", "off-task", "inattentive", "loses focus", "fidget"],
    "impulsivity": ["blurts", "impulsiv", "interrupts", "can't wait"],
    "articulation": ["articulat", "mispronounc", "unclear speech", "lisp"],
    "fluency": ["stutter", "stammer", "disfluen"],
    "visual_tracking": ["loses place", "tracking", "skips lines", "visual crowding", "eye strain"],
    "transition_difficulty": ["transition", "change in routine", "schedule change"],
    "math_difficulty": ["number sense", "calculation", "dyscalculia", "math anxiety"],
    "handwriting": ["handwriting", "illegible", "dysgraphia", "pencil grip"],
}
