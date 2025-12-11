"""Base class for AI Providers."""

from abc import ABC, abstractmethod
from ..core.models import Question, Answer, Review, ValueDimensions


class AIProvider(ABC):
    """Unified interface for AI providers."""

    @abstractmethod
    def get_question(self, age: int, stage: str, history_tags: list[str]) -> Question:
        """Generate a moral dilemma question."""
        raise NotImplementedError

    @abstractmethod
    def review(self, age: int, question: Question, answer: Answer) -> Review:
        """Review a player's answer (legacy growth/match/feedback)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    # Optional richer outputs; override when available
    def score_values(
        self, age: int, question: Question, answer: Answer
    ) -> ValueDimensions | None:
        return None

    def feedback_voices(
        self, age: int, question: Question, answer: Answer
    ) -> dict | None:
        return None

    def life_summary(
        self,
        *,
        age: int,
        stage: str,
        value_dimensions: dict,
        decisions: int,
        history_tags: list[str],
    ) -> str | None:
        """Optional narrative life summary."""
        return None
