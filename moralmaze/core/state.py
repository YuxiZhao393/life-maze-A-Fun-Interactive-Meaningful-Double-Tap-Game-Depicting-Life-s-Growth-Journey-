"""Global game state management."""

from typing import Optional
import time
from .models import DecisionRecord, SaveData, ValueDimensions, GrowthRecord
from .rules import compute_stage_by_age, Stage


class GameState:
    """Holds the full game state."""

    def __init__(self, save_data: Optional[SaveData] = None):
        if save_data:
            self.age = save_data.age
            self.stage = save_data.stage
            self.history = save_data.history
            self.seed = save_data.seed
            self.total_growth = save_data.total_growth
            self.hero_health = getattr(save_data, "hero_health", 100)
            self.value_dimensions = save_data.value_dimensions
            self.growth_history = save_data.growth_history or []
            self.jump_charges = getattr(save_data, "jump_charges", 2)
            self.jump_bonus_awarded = getattr(save_data, "jump_bonus_awarded", 0)
            self.ally_jump_charges = getattr(save_data, "ally_jump_charges", 2)
            self.ally_last_jump_bonus_ts = getattr(save_data, "ally_last_jump_bonus_ts", None)
            self.ally_freeze_charges = getattr(save_data, "ally_freeze_charges", 0)
            self.ally_freeze_initial_bonus_awarded = getattr(
                save_data, "ally_freeze_initial_bonus_awarded", False
            )
            self.ally_freeze_last_bonus_ts = getattr(save_data, "ally_freeze_last_bonus_ts", None)
            self.ally_expand_charges = getattr(save_data, "ally_expand_charges", 0)
            self.ally_expand_initial_bonus_awarded = getattr(
                save_data, "ally_expand_initial_bonus_awarded", False
            )
            self.ally_expand_last_bonus_ts = getattr(save_data, "ally_expand_last_bonus_ts", None)
            self.ally_lift_charges = getattr(save_data, "ally_lift_charges", 0)
            self.ally_lift_initial_bonus_awarded = getattr(
                save_data, "ally_lift_initial_bonus_awarded", False
            )
            self.ally_lift_last_bonus_ts = getattr(save_data, "ally_lift_last_bonus_ts", None)
            self.ally_blink_charges = getattr(save_data, "ally_blink_charges", 1)
            self.ally_blink_last_bonus_ts = getattr(save_data, "ally_blink_last_bonus_ts", None)
            self.ally_position = getattr(save_data, "ally_position", None)
            self.ally_trap_charges = getattr(save_data, "ally_trap_charges", 1)
            self.ally_trap_last_bonus_ts = getattr(save_data, "ally_trap_last_bonus_ts", None)
            self.traps = getattr(save_data, "traps", []) or []
            self.hero_escape_charges = getattr(save_data, "hero_escape_charges", 0)
            self.hero_escape_last_age = getattr(save_data, "hero_escape_last_age", 0)
            self.active_decisions: set[tuple[int, int]] = set(
                tuple(pair) for pair in getattr(save_data, "active_decisions", []) or []
            )
        else:
            self.age = 10
            self.stage = "preteen"
            self.history: list[DecisionRecord] = []
            self.seed = 0
            self.total_growth = 0
            self.hero_health = 100
            self.value_dimensions = ValueDimensions()
            self.growth_history: list[GrowthRecord] = []
            self.jump_charges = 2
            self.jump_bonus_awarded = 0
            self.ally_jump_charges = 2
            self.ally_last_jump_bonus_ts = None
            self.ally_freeze_charges = 0
            self.ally_freeze_initial_bonus_awarded = False
            self.ally_freeze_last_bonus_ts = None
            self.ally_expand_charges = 0
            self.ally_expand_initial_bonus_awarded = False
            self.ally_expand_last_bonus_ts = None
            self.ally_lift_charges = 0
            self.ally_lift_initial_bonus_awarded = False
            self.ally_lift_last_bonus_ts = None
            self.ally_blink_charges = 1
            self.ally_blink_last_bonus_ts = None
            self.ally_position: tuple[int, int] | None = None
            self.ally_trap_charges = 1
            self.ally_trap_last_bonus_ts = None
            self.traps: list[dict] = []
            self.hero_escape_charges = 0
            self.hero_escape_last_age = 0
            self.active_decisions: set[tuple[int, int]] = set()

        if self.ally_last_jump_bonus_ts is None:
            self.ally_last_jump_bonus_ts = time.time()
        if self.ally_freeze_last_bonus_ts is None:
            self.ally_freeze_last_bonus_ts = time.time()
        if self.ally_expand_last_bonus_ts is None:
            self.ally_expand_last_bonus_ts = time.time()
        if getattr(self, "ally_lift_last_bonus_ts", None) is None:
            self.ally_lift_last_bonus_ts = time.time()
        if getattr(self, "ally_blink_last_bonus_ts", None) is None:
            self.ally_blink_last_bonus_ts = time.time()
        if getattr(self, "ally_trap_last_bonus_ts", None) is None:
            self.ally_trap_last_bonus_ts = time.time()

        # runtime state
        self.current_position: tuple[int, int] = (0, 0)
        self.visited_nodes: set[tuple[int, int]] = set()

    def apply_growth(self, delta: int) -> None:
        """Legacy growth application (age + total_growth)."""
        self.age += delta
        self.total_growth += delta

        if self.age < 10:
            self.age = 10

        new_stage = compute_stage_by_age(self.age)
        self.stage = new_stage

    def apply_value_delta(self, delta: ValueDimensions) -> None:
        """Apply five-value delta to current state."""
        self.value_dimensions = self.value_dimensions.add_delta(delta)

    def append_decision(self, record: DecisionRecord) -> None:
        self.history.append(record)

    def append_growth_record(self, record: GrowthRecord) -> None:
        self.growth_history.append(record)

    def is_goal_reached(self, goal_age: int = 90) -> bool:
        return self.age >= goal_age

    def get_history_tags(self) -> list[str]:
        tags = []
        for record in self.history:
            if record.question.tags:
                tags.extend(record.question.tags)
        return tags

    def to_save_data(self) -> SaveData:
        return SaveData(
            age=self.age,
            stage=self.stage,
            history=self.history,
            value_dimensions=self.value_dimensions,
            growth_history=self.growth_history,
            seed=self.seed,
            total_growth=self.total_growth,
            jump_charges=self.jump_charges,
            jump_bonus_awarded=self.jump_bonus_awarded,
            ally_jump_charges=self.ally_jump_charges,
            ally_last_jump_bonus_ts=self.ally_last_jump_bonus_ts,
            ally_freeze_charges=self.ally_freeze_charges,
            ally_freeze_initial_bonus_awarded=self.ally_freeze_initial_bonus_awarded,
            ally_freeze_last_bonus_ts=self.ally_freeze_last_bonus_ts,
            ally_expand_charges=self.ally_expand_charges,
            ally_expand_initial_bonus_awarded=self.ally_expand_initial_bonus_awarded,
            ally_expand_last_bonus_ts=self.ally_expand_last_bonus_ts,
            ally_lift_charges=self.ally_lift_charges,
            ally_lift_initial_bonus_awarded=self.ally_lift_initial_bonus_awarded,
            ally_lift_last_bonus_ts=self.ally_lift_last_bonus_ts,
            ally_blink_charges=self.ally_blink_charges,
            ally_blink_last_bonus_ts=self.ally_blink_last_bonus_ts,
            ally_position=self.ally_position,
            ally_trap_charges=self.ally_trap_charges,
            ally_trap_last_bonus_ts=self.ally_trap_last_bonus_ts,
            traps=self.traps,
            hero_health=self.hero_health,
            hero_escape_charges=self.hero_escape_charges,
            hero_escape_last_age=self.hero_escape_last_age,
            shield_charges=self.shield_charges,
            shield_last_age=self.shield_last_age,
            shield_active_until=self.shield_active_until,
            active_decisions=list(self.active_decisions),
        )

    def mark_node_visited(self, x: int, y: int) -> bool:
        node = (x, y)
        if node in self.visited_nodes:
            return False
        self.visited_nodes.add(node)
        return True


class Settings:
    """Game settings."""

    def __init__(self):
        # Window
        self.window_width = 960
        self.window_height = 640
        self.fps = 60
        self.title = "閬撳痉杩峰 - Moral Maze"

        # Maze
        self.maze_width = 24
        self.maze_height = 18
        self.maze_seed: Optional[int] = None

        # Age
        self.start_age = 10
        self.goal_age = 90

        # AI
        self.ai_provider = "auto"
        self.ai_sensitivity = "standard"

        # Save
        self.save_path = "./save/profile.json"

        # Colors
        self.color_background = (240, 235, 230)
        self.color_wall = (60, 60, 80)
        self.color_player = (70, 130, 180)
        self.color_decision_node = (255, 200, 100)
        self.color_path = (255, 255, 255)
        self.color_text = (40, 40, 40)
        self.color_button = (100, 150, 200)
        self.color_button_hover = (120, 170, 220)

        # Web server
        self.server_host = "127.0.0.1"
        self.server_port = 8000
        self.auto_open_browser = True
        self.static_root = "./web/astray"

    def load_from_dict(self, config: dict) -> None:
        if "window" in config:
            w = config["window"]
            self.window_width = w.get("width", self.window_width)
            self.window_height = w.get("height", self.window_height)
            self.fps = w.get("fps", self.fps)
            self.title = w.get("title", self.title)

        if "maze" in config:
            m = config["maze"]
            self.maze_width = m.get("width", self.maze_width)
            self.maze_height = m.get("height", self.maze_height)
            self.maze_seed = m.get("seed", self.maze_seed)

        if "age" in config:
            a = config["age"]
            self.start_age = a.get("start", self.start_age)
            self.goal_age = a.get("goal", self.goal_age)

        if "ai" in config:
            ai = config["ai"]
            self.ai_provider = ai.get("provider", self.ai_provider)
            self.ai_sensitivity = ai.get("sensitivity", self.ai_sensitivity)

        if "save" in config:
            s = config["save"]
            self.save_path = s.get("path", self.save_path)

        if "colors" in config:
            c = config["colors"]
            if "background" in c:
                self.color_background = tuple(c["background"])
            if "wall" in c:
                self.color_wall = tuple(c["wall"])
            if "player" in c:
                self.color_player = tuple(c["player"])
            if "decision_node" in c:
                self.color_decision_node = tuple(c["decision_node"])
            if "path" in c:
                self.color_path = tuple(c["path"])

        if "server" in config:
            srv = config["server"]
            self.server_host = srv.get("host", self.server_host)
            self.server_port = srv.get("port", self.server_port)
            self.auto_open_browser = srv.get("auto_open_browser", self.auto_open_browser)
            self.static_root = srv.get("static_root", self.static_root)
