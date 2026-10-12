from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

CONDITIONS = ["asd", "adhd", "dyslexia", "speech_language", "sld_math", "sld_writing"]


class Demographics(BaseModel):
    """Optional. Used ONLY by the bias audit (counterfactual tests), never for recommendations."""
    gender: Optional[str] = None
    ethnicity: Optional[str] = None
    ses: Optional[str] = None
    primary_language: Optional[str] = "en"


class StudentCase(BaseModel):
    student_id: str  # pseudonymous ID, never a real name
    age: int = Field(ge=1, le=120)
    grade: Optional[str] = None
    conditions: list[str] = []
    medical_notes: str = ""
    academic: dict[str, float] = {}  # subject -> score 0-100
    academic_history: dict[str, list[float]] = {}  # subject -> chronological scores
    behavior_notes: list[str] = []
    speech_notes: str = ""
    vision_notes: str = ""
    attendance_rate: Optional[float] = None  # 0-1
    incidents_last_30d: int = 0
    demographics: Demographics = Demographics()
    vision_telemetry: Optional[dict] = None
    speech_telemetry: Optional[dict] = None
    vitals_baseline: Optional[dict] = None


class Recommendation(BaseModel):
    id: str
    intervention_id: str
    text: str
    category: str  # accommodation | strategy | service | goal_support
    topic: str = ""
    stance: str = ""
    source_agent: str
    confidence: float
    components: dict = {}
    evidence: list[dict] = []
    status: str = "proposed"  # proposed | resolved | blocked


class AgentOutput(BaseModel):
    agent: str
    findings: dict = {}
    recommendations: list[Recommendation] = []
    confidence: float = 0.0
    notes: list[str] = []


class Goal(BaseModel):
    id: str
    domain: str
    baseline: float
    target: float
    timeframe_weeks: int
    measure: str
    statement: str
    predicted_gain: Optional[float] = None
