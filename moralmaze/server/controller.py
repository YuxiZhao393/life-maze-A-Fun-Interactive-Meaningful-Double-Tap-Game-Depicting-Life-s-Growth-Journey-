"""Game backend controller.

Manages core state, maze, AI provider interactions, and exposes helpers for the API.
Clean ASCII version to avoid encoding issues.
"""

from __future__ import annotations

import random
import threading
from typing import Dict, List, Optional, Tuple
import time

from ..ai.provider_base import AIProvider
from ..ai import scenarios as scenario_store
from ..core import save
from ..core.maze import Cell, Maze, generate_maze
from ..core.models import (
    Answer,
    DecisionRecord,
    Question,
    Review,
    ValueDimensions,
    GrowthRecord,
)
from ..core.rules import compute_stage_by_age, get_stage_name_en
from ..core.state import GameState, Settings


DIR_TO_DELTA = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}

OPPOSITE_DIRECTION = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}


class GameController:
    """Wrap game flow and provide data to the web layer."""

    def __init__(
        self,
        *,
        settings: Settings,
        state: GameState,
        maze: Maze,
        ai_provider: AIProvider,
    ) -> None:
        self.settings = settings
        self.state = state
        self.maze = maze
        self.ai_provider = ai_provider

        if not getattr(self.state, "current_position", None):
            self.state.current_position = self.maze.start_pos

        # active decision coords (tuples)
        if not hasattr(self.state, "active_decisions"):
            self.state.active_decisions = set()
        if not self.state.active_decisions:
            self._init_active_decisions()

        self._lock = threading.Lock()
        self._active_questions: Dict[str, Question] = {}

        # Build wall grid for Astray renderer
        self._wall_grid, self._grid_size = self._build_wall_grid()
        self._sync_jump_charges_with_state()
        self._sync_ally_state()
        self._sync_freeze_state()
        self._sync_expand_state()
        self._replenish_lift_charges()
        self._replenish_lift_charges()
        self._sync_dissolve_state()
        self._replenish_dissolve_charges()
        self._expire_dissolved_nodes()
        self._sync_trap_state()
        self._replenish_trap_charges()
        self._expire_traps()
        self._sync_blink_state()
        self._replenish_blink_charges()
        self._sync_escape_state()
        self._sync_shield_state()

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------
    def get_state_payload(self) -> dict:
        """State payload for HUD/UI."""
        self._replenish_ally_jump_charges()
        self._replenish_freeze_charges()
        self._replenish_expand_charges()
        self._replenish_lift_charges()
        self._replenish_dissolve_charges()
        self._expire_dissolved_nodes()
        self._replenish_trap_charges()
        self._expire_traps()
        self._sync_shield_state()
        freeze_state = {
            "charges": getattr(self.state, "ally_freeze_charges", 0),
            "initial_delay": 10,
            "interval": 30,
            "initial_granted": getattr(
                self.state, "ally_freeze_initial_bonus_awarded", False
            ),
            "max_charges": 3,
        }
        expand_state = {
            "charges": getattr(self.state, "ally_expand_charges", 0),
            "initial_delay": 10,
            "interval": 20,
            "initial_granted": getattr(
                self.state, "ally_expand_initial_bonus_awarded", False
            ),
            "burst_amount": 2,
            "max_charges": 5,
            "restore_duration": 20,
        }
        dissolve_state = {
            "charges": getattr(self.state, "ally_dissolve_charges", 1),
            "interval": 15,
            "max_charges": getattr(self.state, "ally_dissolve_max_charges", 2),
            "active": [
                {"x": x, "y": y, "restore_at": ts}
                for (x, y), ts in getattr(self.state, "dissolved_nodes", {}).items()
            ],
        }
        lift_state = {
            "charges": getattr(self.state, "ally_lift_charges", 0),
            "initial_delay": 0,
            "interval": 20,
            "initial_granted": getattr(
                self.state, "ally_lift_initial_bonus_awarded", False
            ),
            "max_charges": 2,
        }
        trap_state = {
            "charges": getattr(self.state, "ally_trap_charges", 0),
            "interval": 20,
            "max_charges": 2,
            "traps": getattr(self.state, "traps", []),
        }
        shield_state = {
            "charges": getattr(self.state, "shield_charges", 0),
            "active_until": getattr(self.state, "shield_active_until", None),
            "duration": 10,
        }
        return {
            "age": self.state.age,
            "stage": self.state.stage,
            "stage_name": get_stage_name_en(self.state.stage),
            "total_growth": self.state.total_growth,
            "hero_health": getattr(self.state, "hero_health", 100),
            "shield": shield_state,
            "hero_escape_charges": getattr(self.state, "hero_escape_charges", 0),
            "value_dimensions": self.state.value_dimensions.model_dump(),
            "goal_age": self.settings.goal_age,
            "ai_provider": self.ai_provider.name,
            "current_position": {
                "x": self.state.current_position[0],
                "y": self.state.current_position[1],
            },
            "ally_position": self.state.ally_position
            if getattr(self.state, "ally_position", None)
            else None,
            "active_decisions": [
                {"x": x, "y": y} for (x, y) in sorted(self.state.active_decisions)
            ],
            "has_progress": self._has_progress(),
            "jump_charges": getattr(self.state, "jump_charges", 0),
            "ally_state": {
                "jump_charges": getattr(self.state, "ally_jump_charges", 0),
                "recharge_interval": 120,
                "freeze": freeze_state,
                "expand": expand_state,
                "dissolve": dissolve_state,
                "lift": lift_state,
                "blink": {
                    "charges": getattr(self.state, "ally_blink_charges", 1),
                    "interval": 20,
                    "max_charges": 2,
                },
                "trap": trap_state,
            },
        }

    def get_maze_payload(self) -> dict:
        """Serialized maze for the frontend renderer."""
        cells = [
            {
                "x": cell.x,
                "y": cell.y,
                "walls": cell.walls,
                "decision_node": cell.decision_node,
            }
            for row in self.maze.grid
            for cell in row
        ]
        decision_nodes = [
            {
                "x": cell.x,
                "y": cell.y,
                "visited": (cell.x, cell.y) in self.state.visited_nodes,
            }
            for row in self.maze.grid
            for cell in row
            if cell.decision_node
            and (cell.x, cell.y) not in getattr(self.state, "dissolved_nodes", {})
        ]

        return {
            "width": self.maze.width,
            "height": self.maze.height,
            "seed": self.maze.seed,
            "start": {"x": self.maze.start_pos[0], "y": self.maze.start_pos[1]},
            "cells": cells,
            "decision_nodes": decision_nodes,
            "active_decisions": [
                {"x": x, "y": y} for (x, y) in sorted(self.state.active_decisions)
            ],
            "traps": self._visible_traps_payload(),
            "wall_grid": self._wall_grid,
            "grid_size": {"width": self._grid_size[0], "height": self._grid_size[1]},
        }

    def restart_game(self) -> Tuple[dict, dict]:
        with self._lock:
            new_state = GameState()
            new_state.age = self.settings.start_age
            new_state.stage = compute_stage_by_age(new_state.age)
            seed = random.randint(1, 999_999)
            self.maze = generate_maze(
                width=self.settings.maze_width,
                height=self.settings.maze_height,
                seed=seed,
            )
            new_state.seed = self.maze.seed
            new_state.current_position = self.maze.start_pos
            new_state.ally_position = (min(self.maze.width - 1, self.maze.start_pos[0] + 1), self.maze.start_pos[1])
        self.state = new_state
        self._wall_grid, self._grid_size = self._build_wall_grid()
        self._sync_jump_charges_with_state()
        self._sync_ally_state()
        self._sync_freeze_state()
        self._sync_expand_state()
        self._replenish_lift_charges()
        self._sync_escape_state()
        self._init_active_decisions()
        save.save_now(self.state, self.settings.save_path)
        return self.get_state_payload(), self.get_maze_payload()

    def place_trap(self, trap_type: str, x: int, y: int) -> dict:
        """Place a hidden trap (mine/medkit) at the given coordinates (ally position)."""
        trap_type = trap_type.lower()
        if trap_type not in {"mine", "medkit"}:
            raise ValueError("invalid trap type")
        with self._lock:
            self._replenish_trap_charges()
            charges = getattr(self.state, "ally_trap_charges", 0)
            if charges <= 0:
                raise ValueError("No trap charges left")
            if not (0 <= x < self.maze.width and 0 <= y < self.maze.height):
                raise ValueError("Out of bounds")
            # remove existing trap on same tile
            traps = getattr(self.state, "traps", [])
            traps = [t for t in traps if not (t.get("x") == x and t.get("y") == y)]
            now = time.time()
            trap = {
                "type": trap_type,
                "x": x,
                "y": y,
                "placed_at": now,
                "reveal_at": now + 30,
                "expires_at": now + 60,
            }
            traps.append(trap)
            self.state.traps = traps
            self.state.ally_trap_charges = charges - 1
            self.state.ally_trap_last_bonus_ts = now
            save.save_now(self.state, self.settings.save_path)
            return {
                "remaining_charges": self.state.ally_trap_charges,
                "traps": self._visible_traps_payload(),
                "hero_health": getattr(self.state, "hero_health", 100),
            }

    def move_player(self, target_x: int, target_y: int) -> dict:
        """Attempt to move player; return validity and decision trigger."""
        with self._lock:
            self._expire_traps()
            current_x, current_y = self.state.current_position
            dx = target_x - current_x
            dy = target_y - current_y
            if abs(dx) + abs(dy) != 1:
                return {
                    "valid": False,
                    "position": {"x": current_x, "y": current_y},
                    "reason": "invalid_step",
                }

            direction = self._direction_from_delta(dx, dy)
            current_cell = self.maze.get_cell(current_x, current_y)
            next_cell = self.maze.get_cell(target_x, target_y)
            if not current_cell or not next_cell:
                return {
                    "valid": False,
                    "position": {"x": current_x, "y": current_y},
                    "reason": "out_of_bounds",
                }

            if not self.maze.can_move(current_cell, direction):
                return {
                    "valid": False,
                    "position": {"x": current_x, "y": current_y},
                    "reason": "blocked",
                }

            self.state.current_position = (target_x, target_y)

            decision_required = next_cell.decision_node
            first_visit = False
            # Use dynamic active_decisions to gate decision trigger
            decision_required = (target_x, target_y) in self.state.active_decisions
            if decision_required:
                first_visit = self.state.mark_node_visited(target_x, target_y)

            trap_event = self._apply_trap_trigger(target_x, target_y)

            return {
                "valid": True,
                "position": {"x": target_x, "y": target_y},
                "decision_required": decision_required and first_visit,
                "decision_node": decision_required,
                "visited_before": not first_visit if decision_required else False,
                "trap_event": trap_event,
                "hero_health": getattr(self.state, "hero_health", 100),
            }

    def apply_wall_mutations(self, mutations: List[dict]) -> dict:
        """Sync wall openings/closures; keep data structures consistent."""
        if not mutations:
            return {"applied": False}

        with self._lock:
            applied = False
            for mutation in mutations:
                if self._apply_wall_mutation(mutation):
                    applied = True
            if applied:
                self._wall_grid, self._grid_size = self._build_wall_grid()
        return {"applied": applied}

    def jump_player(self, direction: str) -> dict:
        """Handle player jump request."""
        if not direction:
            return {
                "success": False,
                "reason": "invalid_direction",
                "remaining_charges": getattr(self.state, "jump_charges", 0),
            }
        direction = direction.lower()
        if direction not in DIR_TO_DELTA:
            return {
                "success": False,
                "reason": "invalid_direction",
                "remaining_charges": getattr(self.state, "jump_charges", 0),
            }

        with self._lock:
            charges = getattr(self.state, "jump_charges", 0)
            if charges <= 0:
                return {
                    "success": False,
                    "reason": "no_charges",
                    "remaining_charges": 0,
                }

            dx, dy = DIR_TO_DELTA[direction]
            current_x, current_y = self.state.current_position
            candidates = []
            for distance in range(2, 4):
                tx = current_x + dx * distance
                ty = current_y + dy * distance
                if 0 <= tx < self.maze.width and 0 <= ty < self.maze.height:
                    if self.maze.get_cell(tx, ty):
                        candidates.append((tx, ty, distance))
            if not candidates:
                return {
                    "success": False,
                    "reason": "no_destination",
                    "remaining_charges": charges,
                }

            target_x, target_y, distance = random.choice(candidates)
            target_cell = self.maze.get_cell(target_x, target_y)
            if not target_cell:
                return {
                    "success": False,
                    "reason": "invalid_target",
                    "remaining_charges": charges,
                }

            self.state.current_position = (target_x, target_y)
            self.state.jump_charges = max(0, self.state.jump_charges - 1)
            decision_required = target_cell.decision_node
            first_visit = False
            decision_required = (target_x, target_y) in self.state.active_decisions
            if decision_required:
                first_visit = self.state.mark_node_visited(target_x, target_y)

            save.save_now(self.state, self.settings.save_path)

            return {
                "success": True,
                "position": {"x": target_x, "y": target_y},
                "jump_distance": distance,
                "remaining_charges": self.state.jump_charges,
                "decision_required": decision_required and first_visit,
                "decision_node": decision_required,
                "visited_before": (not first_visit) if decision_required else False,
                "state": self.get_state_payload(),
            }

    def sync_position(self, target_x: int, target_y: int) -> dict:
        """Force-sync player position (used for rolling/teleport)."""
        with self._lock:
            if not (0 <= target_x < self.maze.width and 0 <= target_y < self.maze.height):
                raise ValueError("out_of_bounds")
            self.state.current_position = (target_x, target_y)
            save.save_now(self.state, self.settings.save_path)
            return {"position": {"x": target_x, "y": target_y}, "state": self.get_state_payload()}

    def start_decision(self, x: int, y: int) -> dict:
        """Generate a decision question; freeze player movement while active."""
        with self._lock:
            cell = self.maze.get_cell(x, y)
            # allow dynamic active decisions even if original cell wasn't a decision_node
            if (x, y) not in self.state.active_decisions:
                raise ValueError("Current position is not an active decision node")
            # consume this active decision to prevent duplicate triggers until next sync
            self.state.active_decisions.discard((x, y))
            current_age = self.state.age
            current_stage = self.state.stage
            history_tags = self.state.get_history_tags()

        # Try provider first; fallback to local scenarios
        question: Question
        try:
            question = self.ai_provider.get_question(
                age=current_age,
                stage=current_stage,
                history_tags=history_tags,
            )
        except Exception as e:
            print(f"[Provider] question generation failed, using local scenario. ({e})")
            scenario_list = scenario_store.pick_for_stage(current_stage)
            if scenario_list:
                chosen = random.choice(scenario_list)
                question = Question(
                    id=chosen["id"],
                    prompt=chosen["prompt"],
                    options=chosen.get("options", []),
                    difficulty=chosen.get("difficulty", 0.5),
                    tags=chosen.get("tags", []),
                )
            else:
                # ultimate fallback: simple mock question
                question = Question(
                    id=f"local_{current_stage}_{random.randint(1000,9999)}",
                    prompt="A friend asks you to break a rule to help them. What do you do?",
                    options=["Refuse", "Accept", "Seek help"],
                    difficulty=0.5,
                    tags=["responsibility", "integrity"],
                )

        with self._lock:
            self._active_questions[question.id] = question

        return self._serialize_question(question)

    def start_lift(self, hero: tuple[int, int], ally: tuple[int, int]) -> dict:
        """Begin lift: verify distance, consume charge, return allowed info."""
        with self._lock:
            self._replenish_lift_charges()
            charges = getattr(self.state, "ally_lift_charges", 0)
            if charges <= 0:
                raise ValueError("No lift charges left")
            hx, hy = hero
            ax, ay = ally
            dx = hx - ax
            dy = hy - ay
            # Only allow straight-line grabs (same row or column) within 2 tiles
            if not ((dy == 0 and abs(dx) <= 2) or (dx == 0 and abs(dy) <= 2)):
                raise ValueError("Out of reach – ally boost whiffs")
            self.state.ally_lift_charges = max(0, charges - 1)
            self.state.ally_lift_last_bonus_ts = time.time()
            save.save_now(self.state, self.settings.save_path)
            return {
                "ok": True,
                "remaining_charges": self.state.ally_lift_charges,
            }

    def throw_lift(self, ally: tuple[int, int], direction: str) -> dict:
        """Throw hero from ally position in given direction 1-2 tiles; allow out-of-bounds death."""
        direction = direction.lower()
        if direction not in DIR_TO_DELTA:
            raise ValueError("Invalid direction")
        # Always throw hero from ally tile (blue -> yellow)
        ax, ay = ally
        dx, dy = DIR_TO_DELTA[direction]
        dist = random.choice((2, 3))
        tx = ax + dx * dist
        ty = ay + dy * dist
        in_bounds = 0 <= tx < self.maze.width and 0 <= ty < self.maze.height
        target = (tx, ty)
        target_cell = self.maze.get_cell(tx, ty) if in_bounds else None

        with self._lock:
            hero_dead = False
            if target_cell:
                self.state.current_position = target
                decision_required = target in self.state.active_decisions
                first_visit = False
                if decision_required:
                    first_visit = self.state.mark_node_visited(*target)
                    self.state.active_decisions.discard(target)
            else:
                # Out of bounds or invalid cell -> death
                self.state.current_position = target
                hero_dead = True
                self.state.hero_health = 0
                decision_required = False
                first_visit = False
            save.save_now(self.state, self.settings.save_path)
            return {
                "position": {"x": target[0], "y": target[1]},
                "roll_direction": direction,
                "decision_required": decision_required and first_visit,
                "decision_node": decision_required,
                "visited_before": (not first_visit) if decision_required else False,
                "hero_dead": hero_dead,
                "hero_health": getattr(self.state, "hero_health", 0),
                "state": self.get_state_payload(),
            }

    def dissolve_node(self, x: int, y: int) -> dict:
        """Dissolve a decision node temporarily."""
        with self._lock:
            self._replenish_dissolve_charges()
            charges = getattr(self.state, "ally_dissolve_charges", 0)
            if charges <= 0:
                raise ValueError("No dissolve charges left")
            if (x, y) not in self.state.active_decisions and (x, y) not in self.state.decision_nodes:
                raise ValueError("Not a decision node")
            restore_at = time.time() + 15
            dissolved = getattr(self.state, "dissolved_nodes", {})
            dissolved[(x, y)] = restore_at
            self.state.dissolved_nodes = dissolved
            self.state.ally_dissolve_charges = charges - 1
            self.state.ally_dissolve_last_bonus_ts = time.time()
            # temporarily remove from active_decisions
            self.state.active_decisions.discard((x, y))
            save.save_now(self.state, self.settings.save_path)
            return {
                "ok": True,
                "remaining_charges": self.state.ally_dissolve_charges,
                "restore_at": restore_at,
                "dissolved": [{"x": dx, "y": dy, "restore_at": ts} for (dx, dy), ts in dissolved.items()],
                "state": self.get_state_payload(),
            }

    def submit_decision(
        self,
        *,
        question_id: str,
        choice_id: Optional[int],
        free_text: Optional[str],
    ) -> dict:
        """Submit answer; return review and updated state."""
        answer = Answer(choice_id=choice_id, free_text=free_text)
        if answer.is_empty():
            raise ValueError("Missing decision answer")

        with self._lock:
            question = self._active_questions.get(question_id)
            if not question:
                raise ValueError("Question not found; please re-trigger decision.")
            current_age = self.state.age
            current_stage = self.state.stage

        review = self.ai_provider.review(
            age=current_age,
            question=question,
            answer=answer,
        )
        # Optional richer calls
        provider_values = self.ai_provider.score_values(current_age, question, answer)
        provider_voices = self.ai_provider.feedback_voices(current_age, question, answer)

        with self._lock:
            stored_question = self._active_questions.pop(question_id, None) or question

            record = DecisionRecord(
                question=stored_question,
                answer=answer,
                review=review,
                age_at_decision=self.state.age,
                stage_at_decision=self.state.stage,
            )

            self.state.append_decision(record)
            self.state.apply_growth(review.growth_delta)
            value_delta = provider_values or self._build_value_delta(
                stored_question, review, answer
            )
            self.state.apply_value_delta(value_delta)
            default_voices = self._build_default_voices(
                current_age, stored_question, answer, value_delta
            )
            voices = self._normalize_voices(current_age, provider_voices, default_voices)
            growth_rec = GrowthRecord(
                question_id=stored_question.id,
                prompt=stored_question.prompt,
                age=self.state.age,
                stage=self.state.stage,
                value_delta=value_delta,
                perspectives=voices,
                notes=None,
            )
            self.state.append_growth_record(growth_rec)
            self._grant_jump_bonus_if_needed()
            self._grant_escape_by_age()
            self._grant_shield_bonus_if_needed()
            save.save_now(self.state, self.settings.save_path)

        return {
            "question": self._serialize_question(stored_question),
            "answer": self._serialize_answer(answer, stored_question),
            "review": self._serialize_review(review),
            "value_delta": value_delta.model_dump(),
            "value_dimensions": self.state.value_dimensions.model_dump(),
            "voices": voices,
            "state": self.get_state_payload(),
            "game_complete": self.state.is_goal_reached(self.settings.goal_age),
        }

    def get_timeline_payload(self) -> dict:
        """Return decision history payload for recap."""
        records = [
            {
                "index": idx + 1,
                "age": record.age_at_decision,
                "stage": record.stage_at_decision,
                "stage_name": get_stage_name_en(record.stage_at_decision),
                "question": self._serialize_question(record.question),
                "answer": self._serialize_answer(record.answer, record.question),
                "review": self._serialize_review(record.review),
            }
            for idx, record in enumerate(self.state.history)
        ]
        return {
            "summary": {
                "final_age": self.state.age,
                "stage": self.state.stage,
                "stage_name": get_stage_name_en(self.state.stage),
                "total_growth": self.state.total_growth,
                "value_dimensions": self.state.value_dimensions.model_dump(),
                "decisions": len(self.state.history),
                "narrative": self._build_life_summary(),
            },
            "records": records,
            "growth_history": [
                {
                    "question_id": rec.question_id,
                    "prompt": rec.prompt,
                    "age": rec.age,
                    "stage": rec.stage,
                    "value_delta": rec.value_delta.model_dump(),
                    "perspectives": rec.perspectives,
                    "notes": rec.notes,
                }
                for rec in getattr(self.state, "growth_history", [])
            ],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _direction_from_delta(self, dx: int, dy: int) -> str:
        if dx == 1:
            return "east"
        if dx == -1:
            return "west"
        if dy == 1:
            return "south"
        return "north"

    def _apply_trap_trigger(self, x: int, y: int) -> Optional[dict]:
        traps = getattr(self.state, "traps", [])
        hit_index = None
        for idx, trap in enumerate(traps):
            if trap.get("x") == x and trap.get("y") == y:
                hit_index = idx
                break
        if hit_index is None:
            return None
        trap = traps.pop(hit_index)
        self.state.traps = traps
        roll = random.random()
        damage_main = trap.get("type") == "mine"
        heal_main = trap.get("type") == "medkit"
        effect = "damage" if (damage_main and roll < 0.8) or (heal_main and roll >= 0.8) else "heal"
        amount = 30 if effect == "damage" else 20
        shield_active = False
        active_until = getattr(self.state, "shield_active_until", None)
        if active_until and active_until > time.time():
            shield_active = True
        current = getattr(self.state, "hero_health", 100)
        if not shield_active:
            if effect == "damage":
                current = max(0, current - amount)
            else:
                current = min(100, current + amount)
            self.state.hero_health = current
            if current <= 0:
                self.state.hero_health = 0
        return {
            "type": trap.get("type"),
            "effect": effect,
            "amount": amount,
            "hero_health": self.state.hero_health,
            "shield_active": shield_active,
        }

    def apply_freeze_hit(self, damage_percent: float | None = None) -> dict:
        """Apply a small health penalty when the ally freeze succeeds."""
        with self._lock:
            self._sync_trap_state()
            percent = 5.0 if damage_percent is None else max(0.0, float(damage_percent))
            damage = max(1, int(round(100 * (percent / 100.0))))
            current = getattr(self.state, "hero_health", 100)
            new_health = max(0, current - damage)
            self.state.hero_health = new_health
            save.save_now(self.state, self.settings.save_path)
            return {"hero_health": new_health, "damage": damage}

    def escape_hero(self, x: int | None = None, y: int | None = None) -> dict:
        """Hero escapes freeze or lift grab if possible, and can optionally snap to provided cell."""
        self._grant_escape_by_age()
        charges = getattr(self.state, "hero_escape_charges", 0)
        if charges <= 0:
            raise ValueError("No escape charges")
        self.state.hero_escape_charges = charges - 1
        # Optional reposition to keep server/client in sync when breaking free from lift
        if x is not None and y is not None:
            if 0 <= x < self.maze.width and 0 <= y < self.maze.height:
                self.state.current_position = (x, y)
        # reset server-side frozen indicator if present
        if hasattr(self, "hero_frozen"):
            self.hero_frozen = False
        save.save_now(self.state, self.settings.save_path)
        return {
            "remaining_charges": self.state.hero_escape_charges,
            "hero_frozen": False,
            "position": {
                "x": self.state.current_position[0],
                "y": self.state.current_position[1],
            },
        }

    def activate_shield(self) -> dict:
        """Activate hero shield for a limited time."""
        self._grant_shield_bonus_if_needed()
        charges = getattr(self.state, "shield_charges", 0)
        if charges <= 0:
            raise ValueError("No shield charges")
        duration = 10
        self.state.shield_charges = charges - 1
        self.state.shield_active_until = time.time() + duration
        save.save_now(self.state, self.settings.save_path)
        return {
            "remaining_charges": self.state.shield_charges,
            "active_until": self.state.shield_active_until,
            "duration": duration,
        }

    def blink_ally(self) -> dict:
        """Teleport ally near hero within 3 tiles (manhattan)."""
        self._replenish_blink_charges()
        charges = getattr(self.state, "ally_blink_charges", 0)
        if charges <= 0:
            raise ValueError("No blink charges left")
        hx, hy = self.state.current_position
        candidates = []
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if abs(dx) + abs(dy) == 0 or abs(dx) + abs(dy) > 3:
                    continue
                tx, ty = hx + dx, hy + dy
                if 0 <= tx < self.maze.width and 0 <= ty < self.maze.height:
                    if self.maze.get_cell(tx, ty):
                        candidates.append((tx, ty))
        if not candidates:
            raise ValueError("No valid blink target")
        target = random.choice(candidates)
        self.state.ally_position = target
        self.state.ally_blink_charges = charges - 1
        self.state.ally_blink_last_bonus_ts = time.time()
        save.save_now(self.state, self.settings.save_path)
        return {
            "position": {"x": target[0], "y": target[1]},
            "remaining_charges": self.state.ally_blink_charges,
        }

    def _serialize_question(self, question: Question) -> dict:
        return {
            "id": question.id,
            "prompt": question.prompt,
            "options": question.options,
            "difficulty": question.difficulty,
            "tags": question.tags or [],
        }

    def _serialize_answer(self, answer: Answer, question: Question) -> dict:
        choice_text = None
        if answer.choice_id is not None and question.options:
            if 0 <= answer.choice_id < len(question.options):
                choice_text = question.options[answer.choice_id]
        return {
            "choice_id": answer.choice_id,
            "choice_text": choice_text,
            "free_text": answer.free_text,
        }

    def _serialize_review(self, review: Review) -> dict:
        return {
            "growth_delta": review.growth_delta,
            "match_score": review.match_score,
            "feedback": review.feedback,
        }

    def _build_value_delta(
        self, question: Question, review: Review, answer: Answer
    ) -> ValueDimensions:
        base = max(-2, min(2, int(review.growth_delta)))
        tags = {t.lower() for t in (question.tags or [])}

        def bump(flag: bool) -> int:
            if base > 0 and flag:
                return min(2, base)
            if base < 0 and flag:
                return max(-2, base)
            return 0

        # Default bias if no tags matched
        vd = ValueDimensions(
            empathy=bump("empathy" in tags),
            integrity=bump("integrity" in tags),
            courage=bump("courage" in tags),
            responsibility=bump("responsibility" in tags),
            independence=bump("independence" in tags),
        )
        if all(getattr(vd, k) == 0 for k in vd.model_fields):
            vd.responsibility = base
        return vd

    def _build_voices(
        self, question: Question, answer: Answer, value_delta: ValueDimensions
    ) -> Dict[str, str]:
        choice_text = None
        if answer.choice_id is not None and question.options:
            if 0 <= answer.choice_id < len(question.options):
                choice_text = question.options[answer.choice_id]
        ans = answer.free_text or choice_text or "your move"
        delta_summary = (
            f"E{value_delta.empathy:+} I{value_delta.integrity:+} "
            f"Cg{value_delta.courage:+} R{value_delta.responsibility:+} "
            f"In{value_delta.independence:+}"
        )
        return {
            "parents": f"We see you chose {ans}. Hold to your principles and care for others—grow with grace. [{delta_summary}]",
            "friend": f"Bold pick! Let’s keep it real and kind. We’ve got your back. [{delta_summary}]",
            "future_self": f"This step shapes who you become—balance heart and spine. Keep learning. [{delta_summary}]",
        }

    def _build_default_voices(
        self,
        age: int,
        question: Question,
        answer: Answer,
        value_delta: ValueDimensions,
    ) -> Dict[str, str]:
        base = self._build_voices(question, answer, value_delta)
        if age < 60:
            return base
        return {
            "child": base.get("parents", ""),
            "friend": base.get("friend", ""),
            "past_self": base.get("future_self", ""),
        }

    def _normalize_voices(
        self,
        age: int,
        provider_voices: dict | None,
        default_voices: dict,
    ) -> dict:
        voices = provider_voices if isinstance(provider_voices, dict) else {}
        normalized = dict(voices)
        # map generic role keys if present
        if "role1" in normalized or "role2" in normalized or "role3" in normalized:
            roles = [normalized.get("role1"), normalized.get("role2"), normalized.get("role3")]
            if age < 60:
                normalized.setdefault("parents", roles[0] or "")
                normalized.setdefault("friend", roles[1] or "")
                normalized.setdefault("future_self", roles[2] or "")
            else:
                normalized.setdefault("child", roles[0] or "")
                normalized.setdefault("friend", roles[1] or "")
                normalized.setdefault("past_self", roles[2] or "")
        if age < 60:
            required = {
                "parents": default_voices.get("parents", ""),
                "friend": default_voices.get("friend", ""),
                "future_self": default_voices.get("future_self", ""),
            }
        else:
            required = {
                "child": default_voices.get("child", ""),
                "friend": default_voices.get("friend", ""),
                "past_self": default_voices.get("past_self", ""),
            }
        for key, fallback in required.items():
            if not normalized.get(key):
                normalized[key] = fallback or ""
        return normalized

    def _sync_jump_charges_with_state(self) -> None:
        if not hasattr(self.state, "jump_charges"):
            self.state.jump_charges = 2
        if not hasattr(self.state, "jump_bonus_awarded"):
            self.state.jump_bonus_awarded = 0
        self.state.jump_charges = max(0, self.state.jump_charges)
        self._grant_jump_bonus_if_needed()

    def _sync_ally_state(self) -> None:
        if not hasattr(self.state, "ally_jump_charges"):
            self.state.ally_jump_charges = 2
        if not hasattr(self.state, "ally_last_jump_bonus_ts"):
            self.state.ally_last_jump_bonus_ts = time.time()
        if self.state.ally_last_jump_bonus_ts is None:
            self.state.ally_last_jump_bonus_ts = time.time()
        self._replenish_ally_jump_charges()
        self._sync_trap_state()

    def _sync_trap_state(self) -> None:
        if not hasattr(self.state, "hero_health"):
            self.state.hero_health = 100
        if not hasattr(self.state, "ally_trap_charges"):
            self.state.ally_trap_charges = 1
        if not hasattr(self.state, "ally_trap_last_bonus_ts"):
            self.state.ally_trap_last_bonus_ts = time.time()
        if not hasattr(self.state, "traps"):
            self.state.traps = []
        if self.state.ally_trap_last_bonus_ts is None:
            self.state.ally_trap_last_bonus_ts = time.time()
        self._grant_shield_bonus_if_needed()

    def _sync_shield_state(self) -> None:
        if not hasattr(self.state, "shield_charges"):
            self.state.shield_charges = 1
        if not hasattr(self.state, "shield_last_age"):
            self.state.shield_last_age = 0
        if not hasattr(self.state, "shield_active_until"):
            self.state.shield_active_until = None
        # ensure at least 1 initial charge
        self.state.shield_charges = max(1, self.state.shield_charges)
        if self.state.shield_active_until and self.state.shield_active_until <= time.time():
            self.state.shield_active_until = None
        self._grant_shield_bonus_if_needed()

    def _sync_blink_state(self) -> None:
        if not hasattr(self.state, "ally_blink_charges"):
            self.state.ally_blink_charges = 1
        if not hasattr(self.state, "ally_blink_last_bonus_ts"):
            self.state.ally_blink_last_bonus_ts = time.time()
        if self.state.ally_blink_last_bonus_ts is None:
            self.state.ally_blink_last_bonus_ts = time.time()
        if not hasattr(self.state, "ally_position") or self.state.ally_position is None:
            # default spawn next to hero
            hx, hy = self.state.current_position
            self.state.ally_position = (min(self.maze.width - 1, hx + 1), hy)

    def _init_active_decisions(self) -> None:
        """Initialize dynamic active decisions."""
        candidates = []
        for row in self.maze.grid:
            for cell in row:
                if (cell.x, cell.y) in getattr(self.state, "visited_nodes", set()):
                    continue
                candidates.append((cell.x, cell.y))
        random.shuffle(candidates)
        count = min(8, len(candidates))
        self.state.active_decisions = set(candidates[:count])

    def _sync_freeze_state(self) -> None:
        if not hasattr(self.state, "ally_freeze_charges"):
            self.state.ally_freeze_charges = 0
        if not hasattr(self.state, "ally_freeze_initial_bonus_awarded"):
            self.state.ally_freeze_initial_bonus_awarded = False
        if not hasattr(self.state, "ally_freeze_last_bonus_ts"):
            self.state.ally_freeze_last_bonus_ts = time.time()
        if self.state.ally_freeze_last_bonus_ts is None:
            self.state.ally_freeze_last_bonus_ts = time.time()
        self._replenish_freeze_charges()

    def _sync_expand_state(self) -> None:
        if not hasattr(self.state, "ally_expand_charges"):
            self.state.ally_expand_charges = 0
        if not hasattr(self.state, "ally_expand_initial_bonus_awarded"):
            self.state.ally_expand_initial_bonus_awarded = False
        if not hasattr(self.state, "ally_expand_last_bonus_ts"):
            self.state.ally_expand_last_bonus_ts = time.time()
        if self.state.ally_expand_last_bonus_ts is None:
            self.state.ally_expand_last_bonus_ts = time.time()
        self._replenish_expand_charges()

    def _sync_dissolve_state(self) -> None:
        if not hasattr(self.state, "ally_dissolve_charges"):
            self.state.ally_dissolve_charges = 1
        if not hasattr(self.state, "ally_dissolve_last_bonus_ts"):
            self.state.ally_dissolve_last_bonus_ts = time.time()
        if not hasattr(self.state, "ally_dissolve_max_charges"):
            self.state.ally_dissolve_max_charges = 2
        if not hasattr(self.state, "dissolved_nodes"):
            self.state.dissolved_nodes = {}
        if self.state.ally_dissolve_last_bonus_ts is None:
            self.state.ally_dissolve_last_bonus_ts = time.time()
        self._expire_dissolved_nodes()
        self._replenish_dissolve_charges()

    def set_active_decisions(self, coords: List[tuple[int, int]]) -> None:
        """Replace active decision coordinates (used by frontend sync)."""
        with self._lock:
            filtered = []
            for x, y in coords:
                if 0 <= x < self.maze.width and 0 <= y < self.maze.height:
                    filtered.append((x, y))
            self.state.active_decisions = set(filtered)
            save.save_now(self.state, self.settings.save_path)

    def _grant_jump_bonus_if_needed(self) -> None:
        expected_bonus = max(0, (self.state.age - self.settings.start_age) // 5)
        current_bonus = getattr(self.state, "jump_bonus_awarded", 0)
        bonus_delta = expected_bonus - current_bonus
        if bonus_delta > 0:
            self.state.jump_charges = max(0, getattr(self.state, "jump_charges", 0))
            self.state.jump_charges += bonus_delta
            self.state.jump_bonus_awarded = expected_bonus

    def _build_wall_grid(self) -> Tuple[List[List[bool]], Tuple[int, int]]:
        """Convert maze cell grid into Astray-friendly True/False grid."""
        width = self.maze.width
        height = self.maze.height
        grid_w = width * 2 + 1
        grid_h = height * 2 + 1

        wall_grid: List[List[bool]] = [
            [True for _ in range(grid_h)] for _ in range(grid_w)
        ]

        for y in range(height):
            for x in range(width):
                cell = self.maze.grid[y][x]
                px = 2 * x + 1
                py = 2 * y + 1
                wall_grid[px][py] = False

                if not cell.walls["north"]:
                    wall_grid[px][py - 1] = False
                if not cell.walls["south"]:
                    wall_grid[px][py + 1] = False
                if not cell.walls["west"]:
                    wall_grid[px - 1][py] = False
                if not cell.walls["east"]:
                    wall_grid[px + 1][py] = False

        return wall_grid, (grid_w, grid_h)

    def _has_progress(self) -> bool:
        if save.has_save(self.settings.save_path):
            return True
        return bool(self.state.history) or self.state.age > self.settings.start_age

    def _apply_wall_mutation(self, mutation: dict) -> bool:
        x = mutation.get("x")
        y = mutation.get("y")
        direction = mutation.get("direction")
        action = mutation.get("action")
        if direction not in DIR_TO_DELTA or action not in {"open", "close"}:
            return False
        cell = self.maze.get_cell(x, y)
        if not cell:
            return False
        target_state = action == "close"
        current_state = cell.walls.get(direction)
        if current_state is None or current_state == target_state:
            return False

        cell.walls[direction] = target_state
        dx, dy = DIR_TO_DELTA[direction]
        neighbor = self.maze.get_cell(x + dx, y + dy)
        if neighbor:
            neighbor.walls[OPPOSITE_DIRECTION[direction]] = target_state
        return True

    def _replenish_ally_jump_charges(self) -> None:
        last_ts = getattr(self.state, "ally_last_jump_bonus_ts", None)
        if last_ts is None:
            self.state.ally_last_jump_bonus_ts = time.time()
            return
        now = time.time()
        elapsed = now - last_ts
        interval = 15
        cap = 4
        if elapsed >= interval:
            bonus = int(elapsed // interval)
            current = max(0, getattr(self.state, "ally_jump_charges", 0))
            self.state.ally_jump_charges = min(cap, current + bonus)
            self.state.ally_last_jump_bonus_ts = last_ts + bonus * interval

    def _replenish_freeze_charges(self) -> None:
        last_ts = getattr(self.state, "ally_freeze_last_bonus_ts", None)
        if last_ts is None:
            self.state.ally_freeze_last_bonus_ts = time.time()
            return
        now = time.time()
        if not getattr(self.state, "ally_freeze_initial_bonus_awarded", False):
            if now - last_ts >= 10:
                current = max(0, getattr(self.state, "ally_freeze_charges", 0))
                self.state.ally_freeze_charges = min(3, current + 2)
                self.state.ally_freeze_initial_bonus_awarded = True
                self.state.ally_freeze_last_bonus_ts = now
            return
        elapsed = now - last_ts
        if elapsed >= 30:
            gained = int(elapsed // 30)
            if gained > 0:
                current = max(0, getattr(self.state, "ally_freeze_charges", 0))
                self.state.ally_freeze_charges = min(3, current + gained)
            self.state.ally_freeze_last_bonus_ts = last_ts + gained * 30

    def _replenish_expand_charges(self) -> None:
        last_ts = getattr(self.state, "ally_expand_last_bonus_ts", None)
        if last_ts is None:
            self.state.ally_expand_last_bonus_ts = time.time()
            return
        now = time.time()
        if not getattr(self.state, "ally_expand_initial_bonus_awarded", False):
            if now - last_ts >= 10:
                current = max(0, getattr(self.state, "ally_expand_charges", 0))
                self.state.ally_expand_charges = min(5, current + 2)
                self.state.ally_expand_initial_bonus_awarded = True
                self.state.ally_expand_last_bonus_ts = now
            return
        elapsed = now - last_ts
        if elapsed >= 20:
            cycles = int(elapsed // 20)
            if cycles > 0:
                current = max(0, getattr(self.state, "ally_expand_charges", 0))
                gained = cycles * 2
                self.state.ally_expand_charges = min(5, current + gained)
                self.state.ally_expand_last_bonus_ts = last_ts + cycles * 20

    def _replenish_dissolve_charges(self) -> None:
        last_ts = getattr(self.state, "ally_dissolve_last_bonus_ts", None)
        if last_ts is None:
            self.state.ally_dissolve_last_bonus_ts = time.time()
            return
        now = time.time()
        interval = 15
        cap = getattr(self.state, "ally_dissolve_max_charges", 2)
        elapsed = now - last_ts
        if elapsed >= interval:
            gained = int(elapsed // interval)
            current = max(0, getattr(self.state, "ally_dissolve_charges", 1))
            self.state.ally_dissolve_charges = min(cap, current + gained)
            self.state.ally_dissolve_last_bonus_ts = last_ts + gained * interval

    def _replenish_blink_charges(self) -> None:
        last_ts = getattr(self.state, "ally_blink_last_bonus_ts", None)
        if last_ts is None:
            self.state.ally_blink_last_bonus_ts = time.time()
            return
        now = time.time()
        interval = 20
        cap = 2
        elapsed = now - last_ts
        if elapsed >= interval:
            gained = int(elapsed // interval)
            current = max(0, getattr(self.state, "ally_blink_charges", 1))
            self.state.ally_blink_charges = min(cap, current + gained)
            self.state.ally_blink_last_bonus_ts = last_ts + gained * interval

    def _expire_dissolved_nodes(self) -> None:
        dissolved = getattr(self.state, "dissolved_nodes", {})
        if not dissolved:
            return
        now = time.time()
        to_delete = [(x, y) for (x, y), ts in dissolved.items() if ts <= now]
        for key in to_delete:
            dissolved.pop(key, None)
            # restore active decision if still valid
            if 0 <= key[0] < self.maze.width and 0 <= key[1] < self.maze.height:
                self.state.active_decisions.add(key)

    def _replenish_lift_charges(self) -> None:
        last_ts = getattr(self.state, "ally_lift_last_bonus_ts", None)
        if last_ts is None:
            self.state.ally_lift_last_bonus_ts = time.time()
            return
        now = time.time()
        if not getattr(self.state, "ally_lift_initial_bonus_awarded", False):
            elapsed = now - last_ts
            if elapsed < 10:
                return
            current = max(0, getattr(self.state, "ally_lift_charges", 0))
            self.state.ally_lift_charges = min(2, current + 1)
            self.state.ally_lift_initial_bonus_awarded = True
            self.state.ally_lift_last_bonus_ts = now
            return
        elapsed = now - last_ts
        if elapsed >= 20:
            gained = int(elapsed // 20)
            if gained > 0:
                current = max(0, getattr(self.state, "ally_lift_charges", 0))
                self.state.ally_lift_charges = min(2, current + gained)
                self.state.ally_lift_last_bonus_ts = last_ts + gained * 20

    def _replenish_trap_charges(self) -> None:
        last_ts = getattr(self.state, "ally_trap_last_bonus_ts", None)
        if last_ts is None:
            self.state.ally_trap_last_bonus_ts = time.time()
            return
        now = time.time()
        interval = 20
        cap = 2
        elapsed = now - last_ts
        if elapsed >= interval:
            gained = int(elapsed // interval)
            current = max(0, getattr(self.state, "ally_trap_charges", 1))
            self.state.ally_trap_charges = min(cap, current + gained)
            self.state.ally_trap_last_bonus_ts = last_ts + gained * interval

    def _expire_traps(self) -> None:
        traps = getattr(self.state, "traps", [])
        if not traps:
            return
        now = time.time()
        remaining = []
        for trap in traps:
            expires_at = trap.get("expires_at", 0)
            if expires_at and expires_at <= now:
                continue
            remaining.append(trap)
        self.state.traps = remaining

    def _sync_escape_state(self) -> None:
        if not hasattr(self.state, "hero_escape_charges"):
            # give the hero at least one escape by default so they can break free early-game
            self.state.hero_escape_charges = 1
        if not hasattr(self.state, "hero_escape_last_age"):
            self.state.hero_escape_last_age = 0
        self._grant_escape_by_age()

    def _grant_escape_by_age(self) -> None:
        last_age = getattr(self.state, "hero_escape_last_age", 0)
        current_age = getattr(self.state, "age", 10)
        # grant on each 10-year threshold crossed
        while current_age >= (last_age + 10):
            self.state.hero_escape_charges = max(0, getattr(self.state, "hero_escape_charges", 0)) + 1
            last_age += 10
        self.state.hero_escape_last_age = last_age

    def _grant_shield_bonus_if_needed(self) -> None:
        last_age = getattr(self.state, "shield_last_age", 0)
        current_age = getattr(self.state, "age", 10)
        # grant on each 20-year threshold crossed, cap at 1
        while current_age >= (last_age + 20):
            self.state.shield_charges = min(1, max(0, getattr(self.state, "shield_charges", 0)) + 1)
            last_age += 20
        self.state.shield_last_age = last_age

    def _visible_traps_payload(self) -> list[dict]:
        traps = getattr(self.state, "traps", [])
        now = time.time()
        out = []
        for trap in traps:
            reveal_at = trap.get("reveal_at", 0)
            expires_at = trap.get("expires_at", 0)
            if expires_at and expires_at <= now:
                continue
            visible = now >= reveal_at
            out.append(
                {
                    "type": trap.get("type"),
                    "x": trap.get("x"),
                    "y": trap.get("y"),
                    "visible": visible,
                    "reveal_at": reveal_at,
                    "expires_at": expires_at,
                }
            )
        return out

    def _build_life_summary(self) -> str:
        try:
            summary = self.ai_provider.life_summary(
                age=self.state.age,
                stage=self.state.stage,
                value_dimensions=self.state.value_dimensions.model_dump(),
                decisions=len(self.state.history),
                history_tags=self.state.get_history_tags(),
            )
            if summary:
                return summary
        except Exception as e:
            print(f"[Provider] life summary failed, using fallback. ({e})")
        # fallback simple narrative
        vd = self.state.value_dimensions
        return (
            f"Your journey closes at age {self.state.age}. Emp:{vd.empathy}, "
            f"Int:{vd.integrity}, Cou:{vd.courage}, Resp:{vd.responsibility}, "
            f"Ind:{vd.independence}. You made {len(self.state.history)} choices; "
            "these choices shaped a path of growing judgment and character."
        )


def build_controller(
    *,
    settings: Settings,
    maze: Maze,
    state: GameState,
    ai_provider: AIProvider,
) -> GameController:
    """Factory to build GameController."""
    return GameController(
        settings=settings,
        maze=maze,
        state=state,
        ai_provider=ai_provider,
    )
