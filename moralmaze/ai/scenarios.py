"""Scenario loader and helper for developmental dilemmas."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path(__file__).parent / "scenarios.json"


def load_scenarios(path: Optional[str] = None) -> Dict[str, Any]:
    """Load scenarios.json; falls back to default embedded file."""
    p = Path(path) if path else DEFAULT_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return data


def scenarios_by_stage(data: Dict[str, Any], stage: str) -> List[Dict[str, Any]]:
    for bucket in data.get("stages", []):
        if bucket.get("stage") == stage:
            return bucket.get("items", [])
    return []


def pick_for_stage(stage: str, fallback_stage: str = "teen") -> List[Dict[str, Any]]:
    data = load_scenarios()
    items = scenarios_by_stage(data, stage)
    if items:
        return items
    return scenarios_by_stage(data, fallback_stage)
