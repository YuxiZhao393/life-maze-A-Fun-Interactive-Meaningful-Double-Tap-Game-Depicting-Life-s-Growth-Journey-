# Moral Maze · Prototype A

An experimental blend of moral dilemmas and a shifting WebGL maze. Frontend: **Astray + Three.js + Box2D**. Backend: **FastAPI** with AI evaluation (default Groq `llama-3.1-8b-instant`).

Key beats:
- 🌀 Maze walls drift/vanish/regrow; paths keep changing.
- 🧠 Enter glow rings to face AI-generated dilemmas (real-life or philosophical templates, ≤30 words, 2–4 ultra-short options).
- 📈 Age, stage, and growth evolve with your answers; health drops to 0 triggers end-of-life timeline.
- 🟡 Hero & 🔵 Buddy each have rechargeable skills; all counts stay in sync with backend.
- 💾 Local JSON save with continue/restart prompt; state persists (charges, age, progress).
- 🎯 Win/Lose: reaching age 90 = Hero succeeds; HP ≤ 0 or going out-of-bounds ends the life run in failure.
- 🤝 Two-player loop: one controls Hero (survive, grow), the other controls Buddy (can help or hinder with skills like freeze/lift/trap/frontier/blink).

---

## Getting Started (conda)

```bash
conda create -n moralmaze python=3.10 -y
conda activate moralmaze

pip install -r requirements.txt

# API keys (choose what you use)
# In project root create .env and fill keys. Example:
# GROQ_API_KEY=your_groq_key
# GROQ_MODEL=llama-3.1-8b-instant
# OPENAI_API_KEY=your_openai_key
# GEMINI_API_KEY=your_gemini_key
# OLLAMA_ENDPOINT=http://localhost:11434
echo "GROQ_API_KEY=your_groq_key" > .env
echo "GROQ_MODEL=llama-3.1-8b-instant" >> .env
# add optional keys as needed

python run.py
```

- FastAPI: `http://127.0.0.1:8000`
- Web UI auto-opens; if not, open the address manually.
- API docs: `http://127.0.0.1:8000/docs`

---

## Controls (gamepad-first)
- Move: left stick / D-pad.
- Hero Jump: hold A + direction (2–5 tiles, vault walls).
- Hero Shield: X (10s block).
- Hero Escape: B (break freeze/lift when charges available).
- Buddy Freeze: X.
- Buddy Frontier: Y.
- Buddy Dissolve: RT.
- Buddy Lift: B (grab → A throws 2–3 tiles, B rolls to wall; out-of-bounds is lethal).
- Buddy Trap: LT = mine, LB = medkit.
- Buddy Blink: RB.
- Enter dilemmas: step into yellow glow, then choose option and Submit.

---

## Skills & Effects

### Hero (Yellow)
- Jump (A): starts with 2 charges; +1 every 5 age; leaps 2–5 tiles over walls.
- Shield (X): 10s protection; minimum 1 charge; recharges over time.
- Escape (B): break freeze/lift; at least 1 charge granted by age rules.
- Health: starts 100%. Freeze hit = -5% HP; traps may damage/heal. HP ≤ 0 triggers immediate death + timeline summary.

### Buddy (Blue)
- Jump (A): separate ally jump charges; recharges over time.
- Freeze (X): initial delay 10s then +2 bonus; recharge 30s/charge; max 3. On hit: freeze hero 5s and -5% HP.
- Frontier (Y): initial delay 10s +2 bonus; recharge 20s; max 5; opens a path forward.
- Dissolve (RT): recharge 15s; default 1–2 max (server cap 2); temporarily removes a decision node.
- Lift (B): max 2; recharge 20s. Grab hero, aim; A throws 2–3 tiles, B rolls until wall (OOB kills).
- Trap (LT/LB): max 2; recharge 20s; duration 60s.
  - LT mine: 80% -30 HP / 20% +20 HP.
  - LB medkit: 80% +20 HP / 20% -30 HP.
- Blink (RB): starts 1, max 2, recharge 20s; short teleport.

---

## Dilemmas & AI
- Prompts alternate between real-life value conflicts and philosophical thought experiments; ≤30 words, 2–4 short options; options aren’t “good vs bad”.
- AI review returns multi-voice feedback, value scores, and growth delta; updates HUD (age/stage/traits).
- Default provider: Groq `llama-3.1-8b-instant` (configurable via env).

---

## Save / Flow
- Save file: `save/profile.json`.
- On launch: prompt to Continue or Restart if save exists.
- End conditions: reach goal age or HP ≤ 0 → timeline recap (all dilemmas, answers, feedback, growth).

---

## Structure
```
.
├── run.py                  # Launch FastAPI + web frontend
├── save/                   # Local save data
├── moralmaze/
│   ├── core/               # Maze/state/save/rules
│   ├── ai/                 # Providers (Mock/OpenAI/Ollama/Gemini/Groq)
│   └── server/             # GameController + FastAPI API
└── web/
    └── astray/             # Three.js/Box2D/Custom UI
```

---

## Config (config.yaml)
```yaml
maze:
  width: 24
  height: 18
  seed: 20251103

age:
  start: 10
  goal: 60

ai:
  provider: "auto"        # auto / mock / openai / ollama / gemini / groq

server:
  host: 127.0.0.1
  port: 8000
  auto_open_browser: true
  static_root: ./web/astray
```

---

## Roadmap / Future Ideas
- **Smarter dilemmas & reviews**: refine prompts, add diversity/consistency checks, tune scoring/feedback quality.
- **Age-tier subquests**: gate dilemmas behind age-appropriate micro-tasks or milestones per life stage.
- **Global events**: e.g., random bombs that damage the hero if sharing a row/column, or timed hazards that reshape the maze.
- **More AI knobs**: allow per-run provider/model selection (e.g., switch Groq model) and adjustable creativity/temperature.
- **Juice & UX**: richer hit/skill VFX, clearer cooldown UI, and better gamepad onboarding.

---

## License
- Project: MIT License.
- Astray assets in `web/astray` retain MIT notices; ensure any custom art/audio you add is properly licensed.
