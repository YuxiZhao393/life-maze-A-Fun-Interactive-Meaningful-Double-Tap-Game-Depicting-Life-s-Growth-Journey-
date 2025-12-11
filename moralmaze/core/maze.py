"""迷宫生成算法

使用 DFS 回溯算法生成迷宫，标注岔路节点
"""

import random
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Cell:
    """迷宫格子"""
    x: int
    y: int
    walls: dict[str, bool] = field(default_factory=lambda: {
        "north": True,
        "south": True,
        "east": True,
        "west": True
    })
    visited: bool = False
    decision_node: bool = False  # 是否为岔路节点
    
    def open_directions(self) -> list[str]:
        """返回打通的方向列表"""
        return [d for d, has_wall in self.walls.items() if not has_wall]
    
    def opening_count(self) -> int:
        """返回打通的方向数量"""
        return len(self.open_directions())


@dataclass
class Maze:
    """迷宫数据结构"""
    width: int
    height: int
    seed: int
    grid: list[list[Cell]] = field(default_factory=list)
    start_pos: tuple[int, int] = (0, 0)
    
    def get_cell(self, x: int, y: int) -> Optional[Cell]:
        """获取指定位置的格子"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return None
    
    def get_neighbors(self, cell: Cell) -> list[tuple[Cell, str]]:
        """获取相邻格子及方向
        
        Returns:
            [(邻居格子, 方向), ...]
        """
        neighbors = []
        directions = {
            "north": (0, -1),
            "south": (0, 1),
            "east": (1, 0),
            "west": (-1, 0)
        }
        
        for direction, (dx, dy) in directions.items():
            nx, ny = cell.x + dx, cell.y + dy
            neighbor = self.get_cell(nx, ny)
            if neighbor:
                neighbors.append((neighbor, direction))
        
        return neighbors
    
    def can_move(self, from_cell: Cell, direction: str) -> bool:
        """检查是否可以向指定方向移动"""
        return not from_cell.walls[direction]
    
    def grid_to_pixel(self, x: int, y: int, cell_size: int, offset_x: int = 0, offset_y: int = 0) -> tuple[int, int]:
        """网格坐标转屏幕像素坐标"""
        px = offset_x + x * cell_size + cell_size // 2
        py = offset_y + y * cell_size + cell_size // 2
        return px, py


def generate_maze(width: int, height: int, seed: Optional[int] = None) -> Maze:
    """使用 DFS 回溯算法生成迷宫
    
    Args:
        width: 迷宫宽度（格子数）
        height: 迷宫高度（格子数）
        seed: 随机种子（None 则随机）
        
    Returns:
        生成的迷宫对象
    """
    if seed is None:
        seed = random.randint(1, 999999)
    
    random.seed(seed)
    
    # 初始化网格
    maze = Maze(width=width, height=height, seed=seed)
    maze.grid = [[Cell(x, y) for x in range(width)] for y in range(height)]
    
    # DFS 回溯生成
    stack = []
    current = maze.grid[0][0]
    current.visited = True
    stack.append(current)
    
    # 反向方向映射
    opposite = {
        "north": "south",
        "south": "north",
        "east": "west",
        "west": "east"
    }
    
    while stack:
        current = stack[-1]
        
        # 获取未访问的邻居
        unvisited_neighbors = [
            (neighbor, direction)
            for neighbor, direction in maze.get_neighbors(current)
            if not neighbor.visited
        ]
        
        if unvisited_neighbors:
            # 随机选择一个邻居
            next_cell, direction = random.choice(unvisited_neighbors)
            
            # 打通墙壁
            current.walls[direction] = False
            next_cell.walls[opposite[direction]] = False
            
            # 标记为已访问并入栈
            next_cell.visited = True
            stack.append(next_cell)
        else:
            # 回溯
            stack.pop()
    
    # 标注岔路节点（开口 >= 3 的格子）
    decision_nodes = []
    for y in range(height):
        for x in range(width):
            cell = maze.grid[y][x]
            if cell.opening_count() >= 3:
                # 30% 概率标记为决策节点
                if random.random() < 0.3:
                    cell.decision_node = True
                    decision_nodes.append((x, y))
    
    # 确保至少有几个决策节点
    if len(decision_nodes) < 5:
        candidates = [
            (x, y) for y in range(height) for x in range(width)
            if maze.grid[y][x].opening_count() >= 2 and not maze.grid[y][x].decision_node
        ]
        random.shuffle(candidates)
        for x, y in candidates[:5 - len(decision_nodes)]:
            maze.grid[y][x].decision_node = True
    
    maze.start_pos = (0, 0)
    
    return maze

