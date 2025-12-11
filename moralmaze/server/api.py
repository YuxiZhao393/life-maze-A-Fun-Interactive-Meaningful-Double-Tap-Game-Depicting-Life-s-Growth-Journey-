"""FastAPI 应用定义"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .controller import GameController


class MoveRequest(BaseModel):
    x: int
    y: int


class DecisionStartRequest(BaseModel):
    x: int
    y: int


class DecisionSubmitRequest(BaseModel):
    question_id: str
    choice_id: Optional[int] = None
    free_text: Optional[str] = None


class WallMutationOp(BaseModel):
    x: int
    y: int
    direction: Literal["north", "south", "east", "west"]
    action: Literal["open", "close"]


class WallMutationsRequest(BaseModel):
    operations: List[WallMutationOp]


class JumpRequest(BaseModel):
    direction: Literal["north", "south", "east", "west"]


class ActiveDecisionsRequest(BaseModel):
    active: List[dict]


class LiftStartRequest(BaseModel):
    hero_x: int
    hero_y: int
    ally_x: int
    ally_y: int


class LiftThrowRequest(BaseModel):
    ally_x: int
    ally_y: int
    direction: Literal["north", "south", "east", "west"]


class FreezeHitRequest(BaseModel):
    damage_percent: Optional[float] = None


class DissolveRequest(BaseModel):
    x: int
    y: int


class TrapPlaceRequest(BaseModel):
    type: str
    x: int
    y: int

class BlinkRequest(BaseModel):
    pass

class EscapeRequest(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None

class ShieldRequest(BaseModel):
    pass

def create_app(
    controller: GameController,
    *,
    static_dir: Optional[Path] = None,
) -> FastAPI:
    """构建 FastAPI 实例并注入控制器。"""
    app = FastAPI(title="Moral Maze Web API", version="1.0.0")
    app.state.controller = controller

    # 允许前端直接请求
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/ping")
    async def ping():
        return {"status": "ok"}

    @app.get("/api/state")
    async def get_state():
        return controller.get_state_payload()

    @app.post("/api/state/restart")
    async def restart_state():
        state_payload, maze_payload = controller.restart_game()
        return {"state": state_payload, "maze": maze_payload}

    @app.get("/api/maze")
    async def get_maze():
        return controller.get_maze_payload()

    @app.post("/api/player/move")
    async def move_player(payload: MoveRequest):
        return controller.move_player(payload.x, payload.y)

    @app.post("/api/player/jump")
    async def jump_player(payload: JumpRequest):
        return controller.jump_player(payload.direction)

    @app.post("/api/player/sync_position")
    async def sync_position(payload: MoveRequest):
        try:
            return controller.sync_position(payload.x, payload.y)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/maze/mutations")
    async def mutate_maze(payload: WallMutationsRequest):
        operations = [op.dict() for op in payload.operations]
        return controller.apply_wall_mutations(operations)

    @app.post("/api/decisions/active")
    async def set_active_decisions(payload: ActiveDecisionsRequest):
        active_list = []
        for item in payload.active:
            if "x" in item and "y" in item:
                active_list.append((int(item["x"]), int(item["y"])))
        controller.set_active_decisions(active_list)
        return {"active": [{"x": x, "y": y} for x, y in controller.state.active_decisions]}

    @app.post("/api/ally/lift/start")
    async def lift_start(payload: LiftStartRequest):
        try:
            return controller.start_lift(
                hero=(payload.hero_x, payload.hero_y),
                ally=(payload.ally_x, payload.ally_y),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ally/lift/throw")
    async def lift_throw(payload: LiftThrowRequest):
        try:
            return controller.throw_lift(
                ally=(payload.ally_x, payload.ally_y),
                direction=payload.direction,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ally/dissolve")
    async def dissolve(payload: DissolveRequest):
        try:
            return controller.dissolve_node(payload.x, payload.y)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ally/trap")
    async def trap(payload: TrapPlaceRequest):
        try:
            return controller.place_trap(payload.type, payload.x, payload.y)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ally/freeze/hit")
    async def freeze_hit(payload: FreezeHitRequest):
        try:
            return controller.apply_freeze_hit(damage_percent=payload.damage_percent)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ally/blink")
    async def blink(_: BlinkRequest):
        try:
            return controller.blink_ally()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/hero/escape")
    async def hero_escape(payload: EscapeRequest):
        try:
            return controller.escape_hero(x=payload.x, y=payload.y)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/hero/shield")
    async def hero_shield(_: ShieldRequest):
        try:
            return controller.activate_shield()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/decision/start")
    async def start_decision(payload: DecisionStartRequest):
        try:
            return controller.start_decision(payload.x, payload.y)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/decision/submit")
    async def submit_decision(payload: DecisionSubmitRequest):
        try:
            return controller.submit_decision(
                question_id=payload.question_id,
                choice_id=payload.choice_id,
                free_text=payload.free_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/timeline")
    async def get_timeline():
        return controller.get_timeline_payload()

    if static_dir and static_dir.exists():
        app.mount(
            "/web",
            StaticFiles(directory=static_dir, html=True),
            name="astray",
        )

        @app.get("/")
        async def root():
            index_file = static_dir / "index.html"
            if not index_file.exists():
                raise HTTPException(status_code=404, detail="index.html not found")
            return FileResponse(index_file)

    return app
