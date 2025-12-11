"""年龄阶段与成长规则

定义人生阶段划分、成长值计算等游戏规则
"""

from typing import Literal

# 人生阶段类型
Stage = Literal["child", "preteen", "teen", "young_adult", "adult", "mature", "senior"]


# 年龄阶段映射
STAGE_RANGES = {
    "child": (0, 9),
    "preteen": (10, 12),
    "teen": (13, 17),
    "young_adult": (18, 24),
    "adult": (25, 39),
    "mature": (40, 59),
    "senior": (60, 120),
}

# 阶段中文名称
STAGE_NAMES_ZH = {
    "child": "儿童期",
    "preteen": "少年期",
    "teen": "青少年期",
    "young_adult": "青年期",
    "adult": "成年期",
    "mature": "中年期",
    "senior": "老年期",
}

# 阶段英文名称
STAGE_NAMES_EN = {
    "child": "Childhood",
    "preteen": "Preteen",
    "teen": "Teenager",
    "young_adult": "Young Adult",
    "adult": "Adult",
    "mature": "Mature",
    "senior": "Senior",
}


def compute_stage_by_age(age: int) -> Stage:
    """根据年龄计算人生阶段
    
    Args:
        age: 当前年龄
        
    Returns:
        对应的人生阶段
    """
    for stage, (min_age, max_age) in STAGE_RANGES.items():
        if min_age <= age <= max_age:
            return stage
    return "senior"


def get_stage_name_zh(stage: Stage) -> str:
    """获取阶段的中文名称
    
    Args:
        stage: 人生阶段
        
    Returns:
        中文名称
    """
    return STAGE_NAMES_ZH.get(stage, "未知阶段")


def get_stage_name_en(stage: Stage) -> str:
    """获取阶段的英文名称
    
    Args:
        stage: 人生阶段
        
    Returns:
        英文名称
    """
    return STAGE_NAMES_EN.get(stage, "Unknown")


def calculate_growth(
    difficulty: float,
    match_score: float,
    base: int = 4
) -> int:
    """计算成长值
    
    基于难度和匹配分数计算成长值变化
    
    Args:
        difficulty: 题目难度 0~1
        match_score: 答案匹配分数 0~1
        base: 基础成长值（默认 4）
        
    Returns:
        成长值变化 -2~+5
    """
    # 难度系数：0.7 ~ 1.3
    difficulty_factor = 0.7 + 0.6 * difficulty
    
    # 计算原始成长值
    raw_growth = base * match_score * difficulty_factor
    
    # 四舍五入
    growth_delta = round(raw_growth)
    
    # 限制在 -2 ~ +5 范围
    growth_delta = max(-2, min(5, growth_delta))
    
    return growth_delta


def get_stage_color(stage: Stage) -> tuple[int, int, int]:
    """获取阶段对应的主题色
    
    Args:
        stage: 人生阶段
        
    Returns:
        RGB 颜色元组
    """
    colors = {
        "child": (255, 200, 220),      # 粉色
        "preteen": (200, 220, 255),    # 浅蓝
        "teen": (180, 200, 255),       # 蓝色
        "young_adult": (200, 255, 200),# 绿色
        "adult": (255, 230, 180),      # 橙色
        "mature": (220, 200, 180),     # 棕色
        "senior": (200, 200, 220),     # 灰紫
    }
    return colors.get(stage, (200, 200, 200))


def get_stage_themes(stage: Stage) -> list[str]:
    """获取阶段相关的主题标签
    
    不同人生阶段关注的道德主题不同
    
    Args:
        stage: 人生阶段
        
    Returns:
        主题标签列表
    """
    themes = {
        "child": ["分享", "公平", "友谊"],
        "preteen": ["诚实", "规则", "责任"],
        "teen": ["同伴压力", "独立", "身份认同"],
        "young_adult": ["职业道德", "人际关系", "社会正义"],
        "adult": ["家庭责任", "工作生活平衡", "社区参与"],
        "mature": ["传承", "领导力", "人生意义"],
        "senior": ["智慧分享", "遗产", "生命回顾"],
    }
    return themes.get(stage, ["通用"])

