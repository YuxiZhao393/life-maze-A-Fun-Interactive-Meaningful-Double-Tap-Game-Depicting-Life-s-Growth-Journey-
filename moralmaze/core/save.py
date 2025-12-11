"""存档系统

处理游戏存档的读写
"""

import os
import json
from typing import Optional
from pathlib import Path
from .models import SaveData
from .state import GameState


def ensure_save_dir(save_path: str) -> None:
    """确保存档目录存在
    
    Args:
        save_path: 存档文件路径
    """
    save_dir = Path(save_path).parent
    save_dir.mkdir(parents=True, exist_ok=True)


def load_save(save_path: str) -> Optional[SaveData]:
    """加载存档
    
    Args:
        save_path: 存档文件路径
        
    Returns:
        SaveData 对象，如果不存在则返回 None
    """
    if not os.path.exists(save_path):
        return None
    
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SaveData.model_validate(data)
    except Exception as e:
        print(f"加载存档失败: {e}")
        return None


def save_now(state: GameState, save_path: str) -> bool:
    """保存当前游戏状态
    
    Args:
        state: 游戏状态对象
        save_path: 存档文件路径
        
    Returns:
        是否保存成功
    """
    try:
        ensure_save_dir(save_path)
        save_data = state.to_save_data()
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(save_data.model_dump(), f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"保存存档失败: {e}")
        return False


def delete_save(save_path: str) -> bool:
    """删除存档文件
    
    Args:
        save_path: 存档文件路径
        
    Returns:
        是否删除成功
    """
    try:
        if os.path.exists(save_path):
            os.remove(save_path)
        return True
    except Exception as e:
        print(f"删除存档失败: {e}")
        return False


def has_save(save_path: str) -> bool:
    """检查是否存在存档
    
    Args:
        save_path: 存档文件路径
        
    Returns:
        是否存在存档
    """
    return os.path.exists(save_path)

