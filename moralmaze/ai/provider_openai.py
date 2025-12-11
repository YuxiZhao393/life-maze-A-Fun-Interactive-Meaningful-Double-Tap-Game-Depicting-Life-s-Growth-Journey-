"""OpenAI Provider using new developmental prompts."""

import os
import json
import re
from typing import Optional

from .provider_base import AIProvider
from .provider_mock import MockProvider
from ..core.models import Question, Answer, Review, ValueDimensions
from .prompts import (
    format_question_prompt,
    format_review_prompt,
    format_feedback_prompt,
    format_scoring_prompt,
    SYSTEM_PROMPT,
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


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client: Optional[object] = None
        self._fallback = MockProvider()
        try:
            from openai import OpenAI

            if self.api_key:
                self._client = OpenAI(api_key=self.api_key)
            else:
                print("Warning: No OpenAI API Key provided, using Mock Provider")
        except Exception as e:
            print(f"Warning: Failed to initialize OpenAI ({e}), using Mock Provider")

    @property
    def name(self) -> str:
        if self._client:
            return f"OpenAI Provider ({self.model})"
        return "OpenAI Provider (fallback Mock)"

    # ---------------- Question ----------------
    def get_question(self, age: int, stage: str, history_tags: list[str]) -> Question:
        if not self._client:
            return self._fallback.get_question(age, stage, history_tags)
        try:
            prompt = format_question_prompt(age, stage, history_tags)
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(extract_json(content))
            if "id" not in data:
                data["id"] = f"gpt_{age}_{int(os.urandom(2).hex(),16)}"
            return Question.model_validate(data)
        except Exception as e:
            print(f"OpenAI question generation failed: {e}, falling back to Mock")
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
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(extract_json(content))
            return Review.model_validate(data)
        except Exception as e:
            print(f"OpenAI review failed: {e}, falling back to Mock")
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
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(extract_json(content))
            return ValueDimensions.model_validate(data)
        except Exception as e:
            print(f"OpenAI scoring failed: {e}")
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
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(extract_json(content))
        except Exception as e:
            print(f"OpenAI voices failed: {e}")
            return None


def create_openai_provider(api_key: Optional[str] = None, model: Optional[str] = None) -> OpenAIProvider:
    """Factory for OpenAI provider."""
    return OpenAIProvider(api_key=api_key, model=model or "gpt-3.5-turbo")
