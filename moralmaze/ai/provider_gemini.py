"""Google Gemini Provider using developmental prompts."""

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
    """Extract JSON from Gemini responses (may include code fences)."""
    text = re.sub(r"```json?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    return text.strip()


class GeminiProvider(AIProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self._client: Optional[object] = None
        self._fallback = MockProvider()
        try:
            import google.generativeai as genai

            if self.api_key:
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_output_tokens": 900,
                    },
                )
                print(f"[OK] Google Gemini initialized: {self.model}")
            else:
                print("Warning: No Gemini API Key provided, using Mock Provider")
        except Exception as e:
            print(f"Warning: Failed to initialize Gemini ({e}), using Mock Provider")

    @property
    def name(self) -> str:
        if self._client:
            return f"Google Gemini ({self.model})"
        return "Gemini Provider (fallback to Mock)"

    # ---------------- Question ----------------
    def get_question(self, age: int, stage: str, history_tags: list[str]) -> Question:
        if not self._client:
            return self._fallback.get_question(age, stage, history_tags)
        try:
            prompt = format_question_prompt(age, stage, history_tags)
            res = self._client.generate_content(
                [{"role": "user", "parts": [SYSTEM_PROMPT]}, {"role": "user", "parts": [prompt]}]
            )
            data = json.loads(extract_json(res.text))
            if "id" not in data:
                data["id"] = f"gmi_{age}_{int(os.urandom(2).hex(),16)}"
            return Question.model_validate(data)
        except Exception as e:
            print(f"Gemini question generation failed: {e}, falling back to Mock")
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
            res = self._client.generate_content(
                [{"role": "user", "parts": [SYSTEM_PROMPT]}, {"role": "user", "parts": [prompt]}]
            )
            data = json.loads(extract_json(res.text))
            return Review.model_validate(data)
        except Exception as e:
            print(f"Gemini review failed: {e}, falling back to Mock")
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
            res = self._client.generate_content(
                [{"role": "user", "parts": [SYSTEM_PROMPT]}, {"role": "user", "parts": [prompt]}]
            )
            data = json.loads(extract_json(res.text))
            return ValueDimensions.model_validate(data)
        except Exception as e:
            print(f"Gemini scoring failed: {e}")
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
            res = self._client.generate_content(
                [{"role": "user", "parts": [SYSTEM_PROMPT]}, {"role": "user", "parts": [prompt]}]
            )
            data = json.loads(extract_json(res.text))
            return data
        except Exception as e:
            print(f"Gemini voices failed: {e}")
            return None


def create_gemini_provider(api_key: Optional[str] = None, model: Optional[str] = None) -> GeminiProvider:
    """Factory for Gemini provider."""
    return GeminiProvider(api_key=api_key, model=model or "gemini-1.5-flash")
