"""道德迷宫游戏启动脚本（Web 版本）

运行 FastAPI 服务，并使用 Astray 前端进行渲染。
"""

import random
import sys
import webbrowser
from pathlib import Path

import uvicorn
import yaml
from dotenv import load_dotenv

from moralmaze.ai.provider_gemini import create_gemini_provider
from moralmaze.ai.provider_groq import create_groq_provider
from moralmaze.ai.provider_mock import MockProvider
from moralmaze.ai.provider_ollama import create_ollama_provider
from moralmaze.ai.provider_openai import create_openai_provider
from moralmaze.core import save
from moralmaze.core.maze import generate_maze
from moralmaze.core.state import GameState, Settings
from moralmaze.server.api import create_app
from moralmaze.server.controller import build_controller

# 预加载环境变量（API Key 等）
load_dotenv()


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("Warning: config.yaml not found, using default config")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as exc:
        print(f"Warning: Failed to load config ({exc}), using default config")
        return {}


def create_ai_provider(settings: Settings):
    """根据设置创建 AI Provider"""
    provider_type = settings.ai_provider.lower()

    if provider_type == "mock":
        print("Using Mock Provider (Local Review)")
        return MockProvider()
    if provider_type == "ollama":
        print("Trying to use Ollama Provider...")
        provider = create_ollama_provider()
        if provider._client:
            print("[OK] Ollama Provider initialized successfully")
            return provider
        print("[!] Ollama Provider failed, falling back to Mock Provider")
        return MockProvider()
    if provider_type == "gemini":
        print("Trying to use Google Gemini Provider...")
        provider = create_gemini_provider()
        if provider._client:
            print("[OK] Gemini Provider initialized successfully")
            return provider
        print("[!] Gemini Provider failed, falling back to Mock Provider")
        return MockProvider()
    if provider_type == "groq":
        print("Trying to use Groq Provider...")
        provider = create_groq_provider()
        if getattr(provider, "_client", None):
            print("[OK] Groq Provider initialized successfully")
            return provider
        print("[!] Groq Provider failed, falling back to Mock Provider")
        return MockProvider()
    if provider_type == "openai":
        print("Trying to use OpenAI Provider...")
        provider = create_openai_provider()
        if provider._client:
            print("[OK] OpenAI Provider initialized successfully")
            return provider
        print("[!] OpenAI Provider failed, falling back to Mock Provider")
        return MockProvider()

    # auto：按顺序尝试本地/云端 Provider
    print("Auto-selecting AI Provider...")
    for factory in (
        create_ollama_provider,
        create_gemini_provider,
        create_groq_provider,
        create_openai_provider,
    ):
        provider = factory()
        if provider._client:
            print(f"[OK] Using {provider.name}")
            return provider

    print("[->] Using Mock Provider (Local Review)")
    return MockProvider()


def main():
    """脚本入口，启动 Web 服务"""
    print("=" * 60)
    print("Moral Maze - Web Edition")
    print("=" * 60)
    print()

    # 加载配置
    print("Loading configuration...")
    config = load_config()
    settings = Settings()
    if config:
        settings.load_from_dict(config)
    print("[OK] Configuration loaded")
    print()

    # 初始化存档 / 状态
    print("Checking save file...")
    save_data = save.load_save(settings.save_path) if save.has_save(settings.save_path) else None
    if save_data:
        print(f"[OK] Save loaded (Age: {save_data.age}, Decisions: {len(save_data.history)})")
        state = GameState(save_data)
        maze_seed = save_data.seed
    else:
        print("No save found, starting new profile")
        state = GameState()
        maze_seed = settings.maze_seed or random.randint(1, 999_999)
        state.seed = maze_seed
        state.age = settings.start_age
    print()

    # 生成迷宫
    print(f"Generating maze (seed={maze_seed})...")
    maze = generate_maze(
        width=settings.maze_width,
        height=settings.maze_height,
        seed=maze_seed,
    )
    print(f"[OK] Maze generated ({settings.maze_width}x{settings.maze_height})")
    print()

    # 构建 AI Provider
    print("Initializing AI system...")
    ai_provider = create_ai_provider(settings)
    print(f"[OK] AI Provider: {ai_provider.name}")
    print()

    # 构建控制器和 FastAPI 应用
    controller = build_controller(
        settings=settings,
        maze=maze,
        state=state,
        ai_provider=ai_provider,
    )

    static_dir = Path(settings.static_root)
    if not static_dir.exists():
        print(f"[!] Static directory not found: {static_dir}")
        print("    请先运行 `web/astray` 构建流程或下载 Astray 资源。")

    app = create_app(controller, static_dir=static_dir if static_dir.exists() else None)

    url = f"http://{settings.server_host}:{settings.server_port}"
    print("=" * 60)
    print(f"Server running at: {url}")
    print(f"API docs: {url}/docs")
    if static_dir.exists():
        print("Open the browser to play the game.")
    print("=" * 60)
    print()

    if settings.auto_open_browser and static_dir.exists():
        try:
            webbrowser.open(url)
        except Exception:
            pass

    config = uvicorn.Config(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nServer interrupted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
