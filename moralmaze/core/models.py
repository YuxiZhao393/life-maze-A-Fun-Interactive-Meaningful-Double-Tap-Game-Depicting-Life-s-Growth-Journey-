"""Data models (Pydantic) for game state and history."""

from typing import Optional, Dict
from pydantic import BaseModel, Field


class ValueDimensions(BaseModel):
    """Five-value developmental system."""

    empathy: int = Field(default=0, ge=-999, le=999, description="Empathy score")
    integrity: int = Field(default=0, ge=-999, le=999, description="Integrity score")
    courage: int = Field(default=0, ge=-999, le=999, description="Courage score")
    responsibility: int = Field(default=0, ge=-999, le=999, description="Responsibility score")
    independence: int = Field(default=0, ge=-999, le=999, description="Independence score")

    def add_delta(self, delta: "ValueDimensions") -> "ValueDimensions":
        return ValueDimensions(
            empathy=self.empathy + delta.empathy,
            integrity=self.integrity + delta.integrity,
            courage=self.courage + delta.courage,
            responsibility=self.responsibility + delta.responsibility,
            independence=self.independence + delta.independence,
        )


class Question(BaseModel):
    """Moral dilemma question."""

    id: str = Field(..., description="Unique question id")
    prompt: str = Field(..., description="Scenario text")
    options: list[str] = Field(default_factory=list, description="Options (can be empty)")
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0, description="Difficulty 0~1")
    tags: Optional[list[str]] = Field(default=None, description="Topic tags")


class Answer(BaseModel):
    """Player answer."""

    choice_id: Optional[int] = Field(default=None, description="Chosen option index")
    free_text: Optional[str] = Field(default=None, description="Free text answer")

    def is_empty(self) -> bool:
        return self.choice_id is None and not self.free_text


class Review(BaseModel):
    """AI review result."""

    growth_delta: int = Field(..., ge=2, le=10, description="Positive growth delta (2~10)")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Match score 0~1")
    feedback: str = Field(..., description="Feedback text")


class DecisionRecord(BaseModel):
    """Legacy decision history (kept for backward compatibility)."""

    question: Question
    answer: Answer
    review: Review
    age_at_decision: int = Field(..., description="Age when decision was made")
    stage_at_decision: str = Field(..., description="Life stage when decision was made")


class GrowthRecord(BaseModel):
    """Structured growth history for the five-value system."""

    question_id: str
    prompt: str
    age: int
    stage: str
    value_delta: ValueDimensions
    perspectives: Dict[str, str] = Field(default_factory=dict, description="multi-voice feedback snippets")
    notes: Optional[str] = Field(default=None, description="optional narrative note for the run")


class SaveData(BaseModel):
    """Save data payload."""

    age: int = Field(default=10, description="Current age")
    stage: str = Field(default="preteen", description="Current life stage")
    history: list[DecisionRecord] = Field(default_factory=list, description="Legacy decision history")
    value_dimensions: ValueDimensions = Field(default_factory=ValueDimensions, description="Five-value system state")
    growth_history: list[GrowthRecord] = Field(default_factory=list, description="Structured growth history for values")
    seed: int = Field(..., description="Maze seed")
    total_growth: int = Field(default=0, description="Legacy cumulative growth")
    hero_health: int = Field(default=100, ge=0, le=100, description="Hero health percentage")
    jump_charges: int = Field(default=2, ge=0, description="Hero jump charges")
    jump_bonus_awarded: int = Field(default=0, ge=0, description="Extra jump bonuses already granted")
    ally_jump_charges: int = Field(default=2, ge=0, description="Ally jump charges")
    ally_last_jump_bonus_ts: float | None = Field(default=None, description="Timestamp of last ally jump bonus")
    ally_freeze_charges: int = Field(default=0, ge=0, description="Ally freeze charges")
    ally_freeze_initial_bonus_awarded: bool = Field(default=False, description="Whether initial freeze bonus granted")
    ally_freeze_last_bonus_ts: float | None = Field(default=None, description="Timestamp of last freeze bonus")
    ally_expand_charges: int = Field(default=0, ge=0, description="Ally frontier charges")
    ally_expand_initial_bonus_awarded: bool = Field(default=False, description="Whether initial frontier bonus granted")
    ally_expand_last_bonus_ts: float | None = Field(default=None, description="Timestamp of last frontier bonus")
    ally_lift_charges: int = Field(default=0, ge=0, description="Ally lift charges")
    ally_lift_initial_bonus_awarded: bool = Field(default=False, description="Whether initial lift bonus granted")
    ally_lift_last_bonus_ts: float | None = Field(default=None, description="Timestamp of last lift bonus")
    ally_blink_charges: int = Field(default=1, ge=0, description="Ally blink charges")
    ally_blink_last_bonus_ts: float | None = Field(default=None, description="Timestamp of last blink bonus")
    ally_position: tuple[int, int] | None = Field(default=None, description="Stored ally position")
    ally_trap_charges: int = Field(default=1, ge=0, description="Ally trap charges")
    ally_trap_last_bonus_ts: float | None = Field(default=None, description="Timestamp of last trap bonus")
    traps: list[dict] = Field(default_factory=list, description="Placed traps (mine/medkit)")
    hero_escape_charges: int = Field(default=0, ge=0, description="Hero escape skill charges")
    hero_escape_last_age: int = Field(default=0, description="Last age checkpoint when escape was granted")
    active_decisions: list[tuple[int, int]] = Field(default_factory=list, description="Dynamic active decision coordinates")
    active_decisions: list[tuple[int, int]] = Field(default_factory=list, description="Dynamic active decision coordinates")
    shield_charges: int = Field(default=1, ge=0, description="Hero shield charges")
    shield_last_age: int = Field(default=0, ge=0, description="Last age when shield was granted")
    shield_active_until: float | None = Field(default=None, description="Timestamp until which shield is active")

    class Config:
        json_schema_extra = {
            "example": {
                "age": 15,
                "stage": "teen",
                "history": [],
                "value_dimensions": {
                    "empathy": 0,
                    "integrity": 0,
                    "courage": 0,
                    "responsibility": 0,
                    "independence": 0,
                },
                "growth_history": [],
                "seed": 20251103,
                "total_growth": 0,
                "jump_charges": 3,
                "jump_bonus_awarded": 1,
                "ally_jump_charges": 2,
                "ally_last_jump_bonus_ts": 0.0,
                "ally_freeze_charges": 1,
                "ally_freeze_initial_bonus_awarded": True,
                "ally_freeze_last_bonus_ts": 120.0,
                "ally_expand_charges": 0,
                "ally_expand_initial_bonus_awarded": False,
                "ally_expand_last_bonus_ts": 0.0,
            }
        }
