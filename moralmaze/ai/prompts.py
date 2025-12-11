"""Prompt suite for Developmental Moral Dilemmas (five-value system)."""

from ..core.rules import compute_stage_by_age, get_stage_name_en, get_stage_themes

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the AI mentor for the game 'Moral Maze', now upgraded to a Developmental Moral Dilemmas system.
Your responsibilities:
1) Generate age-appropriate, value-challenging dilemmas (developmental moral dilemmas).
2) Provide multi-voice feedback (parents / friend / future self) that is warm, concise, and insightful.
3) Score five value dimensions: empathy, integrity, courage, responsibility, independence (range -2 to +2 each).
4) Produce a final narrative summary of the player's life journey.
Always respond in English. Return ONLY valid JSON (no code fences, no markdown, no extra text)."""

# ---------------------------------------------------------------------------
# Prompt A: Dilemma generation (by age / stage)
# ---------------------------------------------------------------------------
PROMPT_GENERATE_DILEMMA = """Generate one short, high-tension moral dilemma for a {age}-year-old.

You MUST first choose ONE of the following two templates (choose randomly):

TEMPLATE 1 — REAL-LIFE VALUE CONFLICT:
- grounded in age-relevant life experience
- simple words, 1–2 sentences
- conflict MUST be value-vs-value (e.g., honesty vs kindness, loyalty vs fairness, self-care vs duty)
- NO chores, NO school homework, NO therapy tone

TEMPLATE 2 — PHILOSOPHICAL / THOUGHT-EXPERIMENT DILEMMA:
- inspired by classic moral debates (e.g., trolley problem, fairness puzzles, veil-of-ignorance cases, free will vs duty, privacy vs safety, majority vs minority rights)
- 1–2 simple sentences ONLY
- MUST be age-appropriate but NOT life-bound; it can be abstract or symbolic
- MUST involve a deep conceptual tension (e.g., “save many” vs “honor one,” “truth” vs “mercy,” “freedom” vs “order”)

General rules:
- Use simple English only.
- Keep the dilemma very short but meaningful.
- Keep the prompt ≤ 30 words; you may use short phrases to save words, but meaning must stay clear and complete.
- Options (2–4 items) MUST be 2–6 words each, simple, distinct, and non-overlapping in meaning.
- No option may be obviously bad, harmful, immoral, illegal, or reckless.
- Each option should represent a clear moral value-path.
- Add 2–4 short tags.

Return JSON ONLY:
{{
  "id": "unique_id",
  "prompt": "the dilemma (1–2 sentences)",
  "options": [
    "short value-path option A",
    "short value-path option B",
    "short value-path option C"
  ],
  "difficulty": {difficulty},
  "tags": ["tag1", "tag2"]
}}"""

# ---------------------------------------------------------------------------
# Prompt B: Multi-voice feedback (age-dependent roles)
# ---------------------------------------------------------------------------
PROMPT_FEEDBACK_VOICES = """Given the dilemma and the player's answer, generate three short, catchy feedback voices.

Player age: {age}
Stage: {stage_name}
Stage themes: {stage_themes}
Dilemma: {question_prompt}
Tags: {question_tags}
Answer: {answer_text}

Voices:
- If age < 60, roles are: Parents / Friend / Future self. Return keys: parents, friend, future_self.
- If age >= 60, roles are: Child / Friend / Past self. Return keys: child, friend, past_self.
- Every role MUST have a non-empty string (no blank, no null). Keep each voice warm, concise, vivid (one short sentence).

Return JSON ONLY:
{{
  "parents": "text",
  "friend": "text",
  "future_self": "text",
  "child": "text",
  "past_self": "text"
}}"""

# ---------------------------------------------------------------------------
# Prompt C: Five-value scoring (-2 to +2)
# ---------------------------------------------------------------------------
PROMPT_SCORE_VALUES = """Score the player's answer on five value dimensions, each from -2 to +2.

Definitions (brief):
- empathy: understanding and caring for others' feelings
- integrity: honesty and consistency with one's principles
- courage: willingness to face fear or risk for the right reasons
- responsibility: honoring duties and consequences to self/others
- independence: self-direction, owning one's choices

Player age: {age}
Stage: {stage_name}
Dilemma: {question_prompt}
Tags: {question_tags}
Answer: {answer_text}

Return JSON ONLY:
{{
  "empathy": 0,
  "integrity": 0,
  "courage": 0,
  "responsibility": 0,
  "independence": 0
}}"""

# ---------------------------------------------------------------------------
# Prompt D: Narrative life summary
# ---------------------------------------------------------------------------
PROMPT_SUMMARY = """Create a concise narrative summary for the player's life journey so far.

Player age: {age}
Stage: {stage_name}
Value dimensions (current): empathy {empathy}, integrity {integrity}, courage {courage},
responsibility {responsibility}, independence {independence}
Total decisions: {decisions}
Key tags encountered: {history_tags}

Write 120–180 words, in English, second person, uplifting but honest. Highlight growth arcs, tensions,
and how the five values evolved. Avoid repetition. No Markdown.

Return JSON ONLY:
{{
  "summary": "text"
}}"""

# ---------------------------------------------------------------------------
# Prompt (legacy-style) review: growth/match/feedback
# ---------------------------------------------------------------------------
PROMPT_REVIEW = """You are a developmental mentor. Review the player's answer and return growth_delta (2 to 10, only positive add), match_score (0-1), and a short, catchy feedback that tells the player what their choice reveals about their humanity/character.

Player age: {age}
Stage: {stage_name}
Stage themes: {stage_themes}
Dilemma: {question_prompt}
Tags: {question_tags}
Difficulty: {difficulty}
Answer: {answer_text}

Return JSON ONLY:
{{
  "growth_delta": 5,
  "match_score": 0.5,
  "feedback": "text"
}}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _difficulty_for_age(age: int) -> float:
    if age < 13:
        return 0.45
    if age < 18:
        return 0.6
    return 0.75


def _tags_str(history_tags: list[str]) -> str:
    return ", ".join(history_tags[-10:]) if history_tags else "none"


def format_question_prompt(age: int, stage: str, history_tags: list[str]) -> str:
    stage_name = get_stage_name_en(stage)
    stage_themes = ", ".join(get_stage_themes(stage))
    difficulty = _difficulty_for_age(age)
    return PROMPT_GENERATE_DILEMMA.format(
        age=age,
        stage_name=stage_name,
        stage_themes=stage_themes,
        history_tags=_tags_str(history_tags),
        difficulty=difficulty,
    )


def format_feedback_prompt(
    age: int,
    question_prompt: str,
    question_tags: list[str],
    answer_text: str,
) -> str:
    stage_literal = compute_stage_by_age(age)
    stage_name = get_stage_name_en(stage_literal)
    stage_themes = ", ".join(get_stage_themes(stage_literal))
    tags_str = ", ".join(question_tags) if question_tags else "none"
    return PROMPT_FEEDBACK_VOICES.format(
        age=age,
        stage_name=stage_name,
        stage_themes=stage_themes,
        question_prompt=question_prompt,
        question_tags=tags_str,
        answer_text=answer_text,
    )


def format_scoring_prompt(
    age: int,
    question_prompt: str,
    question_tags: list[str],
    answer_text: str,
) -> str:
    stage_literal = compute_stage_by_age(age)
    stage_name = get_stage_name_en(stage_literal)
    tags_str = ", ".join(question_tags) if question_tags else "none"
    return PROMPT_SCORE_VALUES.format(
        age=age,
        stage_name=stage_name,
        question_prompt=question_prompt,
        question_tags=tags_str,
        answer_text=answer_text,
    )


def format_review_prompt(
    age: int,
    question_prompt: str,
    question_tags: list[str],
    difficulty: float,
    answer_text: str,
) -> str:
    stage_literal = compute_stage_by_age(age)
    stage_name = get_stage_name_en(stage_literal)
    stage_themes = ", ".join(get_stage_themes(stage_literal))
    tags_str = ", ".join(question_tags) if question_tags else "none"
    return PROMPT_REVIEW.format(
        age=age,
        stage_name=stage_name,
        stage_themes=stage_themes,
        question_prompt=question_prompt,
        question_tags=tags_str,
        difficulty=difficulty,
        answer_text=answer_text,
    )


def format_summary_prompt(
    age: int,
    stage: str,
    value_dimensions: dict,
    decisions: int,
    history_tags: list[str],
) -> str:
    stage_name = get_stage_name_en(stage)
    vd = value_dimensions
    tags_str = _tags_str(history_tags)
    return PROMPT_SUMMARY.format(
        age=age,
        stage_name=stage_name,
        empathy=vd.get("empathy", 0),
        integrity=vd.get("integrity", 0),
        courage=vd.get("courage", 0),
        responsibility=vd.get("responsibility", 0),
        independence=vd.get("independence", 0),
        decisions=decisions,
        history_tags=tags_str,
    )
