"""Groq Provider using Llama models for developmental dilemmas."""

import os
import json
import re
from typing import Optional

from .provider_base import AIProvider
from .provider_mock import MockProvider
from ..core.models import Question, Answer, Review, ValueDimensions
from .prompts import (
    SYSTEM_PROMPT,
    format_question_prompt,
    format_review_prompt,
    format_scoring_prompt,
    format_feedback_prompt,
    format_summary_prompt,
)


def extract_json(text: str) -> str:
    """Extract JSON from possible code fences."""
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    return text.strip()


class GroqProvider(AIProvider):
    """Groq-backed provider; defaults to llama-3.1-8b-instant."""

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.1-8b-instant"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        self._client: Optional[object] = None
        self._fallback = MockProvider()
        try:
            from groq import Groq

            if self.api_key:
                self._client = Groq(api_key=self.api_key)
            else:
                print("Warning: No GROQ_API_KEY provided, using Mock Provider")
        except Exception as e:
            print(f"Warning: Failed to initialize Groq ({e}), using Mock Provider")

    @property
    def name(self) -> str:
        if self._client:
            return f"Groq ({self.model})"
        return "Groq Provider (fallback to Mock)"

    # ---------------- Question ----------------
    def get_question(self, age: int, stage: str, history_tags: list[str]) -> Question:
        if not self._client:
            return self._fallback.get_question(age, stage, history_tags)
        try:
            prompt = format_question_prompt(age, stage, history_tags)
            res = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            content = res.choices[0].message.content
            data = json.loads(extract_json(content))
            if "id" not in data:
                data["id"] = f"groq_{age}_{int(os.urandom(2).hex(),16)}"
            return Question.model_validate(data)
        except Exception as e:
            print(f"Groq question generation failed: {e}, falling back to Mock")
            return self._fallback.get_question(age, stage, history_tags)

    # ---------------- Legacy review ----------------
    def review(self, age: int, question: Question, answer: Answer) -> Review:
        if not self._client:
            return self._fallback.review(age, question, answer)
        try:
            answer_text = ""
            if answer.choice_id is not None and question.options:
                if 0 <= answer.choice_id < len(question.options):
                    answer_text = f"Choice: {question.options[answer.choice_id]}"
            if answer.free_text:
                answer_text += f" Free: {answer.free_text}"
            prompt = format_review_prompt(
                age=age,
                question_prompt=question.prompt,
                question_tags=question.tags or [],
                difficulty=question.difficulty,
                answer_text=answer_text or "No answer",
            )
            res = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=400,
            )
            content = res.choices[0].message.content
            data = json.loads(extract_json(content))
            return Review.model_validate(data)
        except Exception as e:
            print(f"Groq review failed: {e}, falling back to Mock")
            return self._fallback.review(age, question, answer)

    # ---------------- Five-value scoring ----------------
    def score_values(
        self, age: int, question: Question, answer: Answer
    ) -> ValueDimensions | None:
        if not self._client:
            return None
        try:
            answer_text = ""
            if answer.choice_id is not None and question.options:
                if 0 <= answer.choice_id < len(question.options):
                    answer_text = f"Choice: {question.options[answer.choice_id]}"
            if answer.free_text:
                answer_text += f" Free: {answer.free_text}"
            prompt = format_scoring_prompt(
                age=age,
                question_prompt=question.prompt,
                question_tags=question.tags or [],
                answer_text=answer_text or "No answer",
            )
            res = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=300,
            )
            content = res.choices[0].message.content
            data = json.loads(extract_json(content))
            return ValueDimensions.model_validate(data)
        except Exception as e:
            print(f"Groq scoring failed: {e}")
            return None

    # ---------------- Multi-voice feedback ----------------
    def feedback_voices(
        self, age: int, question: Question, answer: Answer
    ) -> dict | None:
        if not self._client:
            return None
        try:
            answer_text = ""
            if answer.choice_id is not None and question.options:
                if 0 <= answer.choice_id < len(question.options):
                    answer_text = f"Choice: {question.options[answer.choice_id]}"
            if answer.free_text:
                answer_text += f" Free: {answer.free_text}"
            prompt = format_feedback_prompt(
                age=age,
                question_prompt=question.prompt,
                question_tags=question.tags or [],
                answer_text=answer_text or "No answer",
            )
            res = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=400,
            )
            content = res.choices[0].message.content
            return json.loads(extract_json(content))
        except Exception as e:
            print(f"Groq voices failed: {e}")
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
        if not self._client:
            return None
        try:
            prompt = format_summary_prompt(
                age=age,
                stage=stage,
                value_dimensions=value_dimensions,
                decisions=decisions,
                history_tags=history_tags,
            )
            res = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=400,
            )
            content = res.choices[0].message.content
            data = json.loads(extract_json(content))
            return data.get("summary")
        except Exception as e:
            print(f"Groq summary failed: {e}")
            return None


def create_groq_provider(api_key: Optional[str] = None, model: Optional[str] = None) -> GroqProvider:
    return GroqProvider(api_key=api_key, model=model or "llama-3.1-8b-instant")
