"""游戏主循环

Pygame 主循环，处理迷宫渲染、玩家移动、事件触发
"""

import pygame
import sys
from typing import Optional, Tuple
from ..core.state import GameState, Settings
from ..core.maze import Maze, Cell
from ..core.models import Question, Answer, Review, DecisionRecord
from ..ai.provider_base import AIProvider
from ..core import save
from .decision_overlay import DecisionOverlay
from .timeline import TimelinePage
import math


class MazeGame:
    """迷宫游戏主类"""
    
    def __init__(
        self,
        state: GameState,
        maze: Maze,
        settings: Settings,
        ai_provider: AIProvider
    ):
        """初始化游戏
        
        Args:
            state: 游戏状态
            maze: 迷宫对象
            settings: 游戏设置
            ai_provider: AI Provider
        """
        self.state = state
        self.maze = maze
        self.settings = settings
        self.ai_provider = ai_provider
        
        # 初始化 Pygame
        pygame.init()
        self.screen = pygame.display.set_mode(
            (settings.window_width, settings.window_height)
        )
        pygame.display.set_caption(settings.title)
        self.clock = pygame.time.Clock()
        
        # 字体
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        
        # 玩家位置
        self.player_x, self.player_y = maze.start_pos
        self.state.current_position = (self.player_x, self.player_y)
        
        # 计算迷宫渲染参数
        # 摄像机窗口大小，单位：tile（推荐奇数最大贴边）
        self.camera_tiles_w = min(15, self.maze.width) if self.maze.width>9 else self.maze.width
        self.camera_tiles_h = min(11, self.maze.height) if self.maze.height>7 else self.maze.height
        self.half_camera_w = self.camera_tiles_w // 2
        self.half_camera_h = self.camera_tiles_h // 2
        # cell_size 重新适配，最大化填满画面
        cell_size_x = (settings.window_width)//self.camera_tiles_w
        cell_size_y = (settings.window_height)//self.camera_tiles_h
        self.cell_size = min(cell_size_x, cell_size_y)
        # 补偿offset，使屏幕正中心严格对应tile正中心
        self.center_px = settings.window_width//2
        self.center_py = settings.window_height//2
        
        # UI 状态
        self.running = True
        self.paused = False
        self.decision_overlay: Optional[DecisionOverlay] = None
        self.timeline_page: Optional[TimelinePage] = None
        self.current_question: Optional[Question] = None
        self.last_review: Optional[Review] = None
        
        # 移动冷却
        self.move_cooldown = 0
        self.move_delay = 150  # 毫秒
        
        # 摄像头可视大小（保证奇数居中）
        self.camera_tile_w = min(17, maze.width) if maze.width > 9 else maze.width  # 画面宽度tile数
        self.camera_tile_h = min(13, maze.height) if maze.height > 7 else maze.height
        # 通过cell_size算出像素宽高（可继续适配屏幕）
        self.camera_pixel_w = self.camera_tile_w * self.cell_size
        self.camera_pixel_h = self.camera_tile_h * self.cell_size
        
        # 加载地板与墙壁贴图
        try:
            self.img_tile_floor = pygame.image.load("moralmaze/ui/assets/tile_floor.png").convert_alpha()
        except:
            self.img_tile_floor = None
        try:
            self.img_tile_wall = pygame.image.load("moralmaze/ui/assets/tile_wall.png").convert_alpha()
        except:
            self.img_tile_wall = None
        # 主角四方向多帧动画
        self.player_sprites = {}
        dirs = ["down","left","right","up"]
        for d in dirs:
            arr=[]
            for i in range(4):
                try:
                    arr.append(pygame.image.load(f"moralmaze/ui/assets/player_{d}_{i}.png").convert_alpha())
                except:
                    break
            self.player_sprites[d]=arr if arr else None
        # 玩家朝向与帧计数
        self.player_dir = "down"
        self.player_anim_frame = 0
        self.player_anim_tick = 0
        self.node_anim_tick = 0 # 用于节点发光
    
    def run(self) -> None:
        """运行游戏主循环"""
        last_time = pygame.time.get_ticks()
        
        while self.running:
            current_time = pygame.time.get_ticks()
            dt = current_time - last_time
            last_time = current_time
            
            # 更新冷却
            if self.move_cooldown > 0:
                self.move_cooldown -= dt
            
            # 事件处理
            self.handle_events()
            
            # 更新
            self.update()
            
            # 渲染
            self.render()
            
            # 帧率控制
            self.clock.tick(self.settings.fps)
        
        pygame.quit()
    
    def handle_events(self) -> None:
        """处理事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.decision_overlay:
                        # 关闭决策弹窗
                        self.decision_overlay = None
                    elif self.timeline_page:
                        # 关闭时间线
                        self.timeline_page = None
                    else:
                        # 暂停/保存/退出
                        self.paused = not self.paused
                        if self.paused:
                            save.save_now(self.state, self.settings.save_path)
            
            # 将事件传递给活动的覆盖层
            if self.decision_overlay:
                self.decision_overlay.handle_event(event)
            elif self.timeline_page:
                result = self.timeline_page.handle_event(event)
                if result == "restart":
                    self.running = False  # 触发重启
    
    def update(self) -> None:
        """更新游戏状态"""
        # 检查是否达到目标年龄
        if self.state.is_goal_reached(self.settings.goal_age):
            if not self.timeline_page:
                self.timeline_page = TimelinePage(
                    self.screen,
                    self.state,
                    self.settings,
                    self.font_large,
                    self.font_medium,
                    self.font_small
                )
            return
        
        # 决策弹窗处理
        if self.decision_overlay:
            # 检查是否有待提交的答案
            if self.decision_overlay.pending_submit:
                answer = self.decision_overlay.get_answer()
                self.process_decision(self.current_question, answer)
                self.decision_overlay.pending_submit = False
                return
            
            result = self.decision_overlay.update()
            if result:
                if result["action"] == "close":
                    # 关闭弹窗
                    self.decision_overlay = None
                    self.current_question = None
            return
        
        # 时间线页面处理
        if self.timeline_page:
            return
        
        # 暂停状态不处理移动
        if self.paused:
            return
        
        # 玩家移动
        if self.move_cooldown <= 0:
            self.handle_movement()
        
        # 记录帧动画计数
        if not self.paused:
            self.player_anim_tick += 1
            self.node_anim_tick += 1
    
    def handle_movement(self) -> None:
        """处理玩家移动"""
        keys = pygame.key.get_pressed()
        
        current_cell = self.maze.get_cell(self.player_x, self.player_y)
        if not current_cell:
            return
        
        moved = False
        new_x, new_y = self.player_x, self.player_y
        dir_temp = self.player_dir
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dir_temp = "up"
            if self.maze.can_move(current_cell, "north"):
                new_y -= 1
                moved = True
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dir_temp = "down"
            if self.maze.can_move(current_cell, "south"):
                new_y += 1
                moved = True
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dir_temp = "left"
            if self.maze.can_move(current_cell, "west"):
                new_x -= 1
                moved = True
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dir_temp = "right"
            if self.maze.can_move(current_cell, "east"):
                new_x += 1
                moved = True
        
        if moved:
            self.player_dir = dir_temp
            # 动画帧切换逻辑(80ms)
            if self.player_anim_tick%5==0:
                self.player_anim_frame = (self.player_anim_frame+1)%4
            self.player_x = new_x
            self.player_y = new_y
            self.state.current_position = (new_x, new_y)
            self.move_cooldown = self.move_delay
            
            # 检查是否进入决策节点
            self.check_decision_node()
    
    def check_decision_node(self) -> None:
        """检查是否进入决策节点"""
        cell = self.maze.get_cell(self.player_x, self.player_y)
        if not cell or not cell.decision_node:
            return
        
        # 检查是否首次访问
        is_first_visit = self.state.mark_node_visited(self.player_x, self.player_y)
        if not is_first_visit:
            return
        
        # 触发决策事件
        self.trigger_decision()
    
    def trigger_decision(self) -> None:
        """触发决策事件"""
        # 获取题目
        question = self.ai_provider.get_question(
            age=self.state.age,
            stage=self.state.stage,
            history_tags=self.state.get_history_tags()
        )
        
        self.current_question = question
        
        # 创建决策弹窗
        self.decision_overlay = DecisionOverlay(
            self.screen,
            question,
            self.settings,
            self.font_large,
            self.font_medium,
            self.font_small
        )
    
    def process_decision(self, question: Question, answer: Answer) -> None:
        """处理决策结果
        
        Args:
            question: 题目
            answer: 答案
        """
        # 获取评审
        review = self.ai_provider.review(
            age=self.state.age,
            question=question,
            answer=answer
        )
        
        self.last_review = review
        
        # 记录决策
        record = DecisionRecord(
            question=question,
            answer=answer,
            review=review,
            age_at_decision=self.state.age,
            stage_at_decision=self.state.stage
        )
        self.state.append_decision(record)
        
        # 应用成长值
        self.state.apply_growth(review.growth_delta)
        
        # 保存进度
        save.save_now(self.state, self.settings.save_path)
        
        # 显示评审结果
        if self.decision_overlay:
            self.decision_overlay.show_review(review)
    
    def get_camera_xy(self):
        # 计算摄像机左上角tile索引（camera_x,camera_y），让主角尽量屏幕中心
        cam_x = self.player_x - self.half_camera_w
        cam_y = self.player_y - self.half_camera_h
        # clamp边界（不能看到超出地牢外空白区）
        cam_x = max(0, min(self.maze.width - self.camera_tiles_w, cam_x))
        cam_y = max(0, min(self.maze.height - self.camera_tiles_h, cam_y))
        return cam_x, cam_y

    def render(self) -> None:
        """渲染游戏画面"""
        # 背景
        self.screen.fill(self.settings.color_background)
        
        # 渲染 HUD
        self.render_hud()
        
        # 渲染迷宫
        self.render_maze()
        
        # 渲染玩家
        self.render_player()
        
        # 渲染覆盖层
        if self.decision_overlay:
            self.decision_overlay.render()
        elif self.timeline_page:
            self.timeline_page.render()
        elif self.paused:
            self.render_pause_menu()
        
        pygame.display.flip()
    
    def render_hud(self) -> None:
        from ..core.rules import get_stage_name_en
        # 缩小为极小的角落信息
        hud_font = self.font_small
        # 年龄 阶段放左上
        age_text = hud_font.render(f"Age:{self.state.age}", True, self.settings.color_text)
        stage_text = hud_font.render(f"{get_stage_name_en(self.state.stage)}", True, self.settings.color_text)
        self.screen.blit(age_text, (10, 6))
        self.screen.blit(stage_text, (10, 22))
        # 最近成长放右上
        if self.last_review:
            delta = self.last_review.growth_delta
            color = (50, 180, 50) if delta > 0 else (180, 50, 50) if delta < 0 else (100, 100, 100)
            growth_text = hud_font.render(f"\u2191{delta:+d}" if delta>0 else f"{delta:+d}", True, color)
            self.screen.blit(growth_text, (self.settings.window_width - growth_text.get_width() - 18, 6))
        # AI Provider放左下极角
        provider_text = hud_font.render(f"AI: {self.ai_provider.name}", True, (120, 120, 120))
        self.screen.blit(provider_text, (10, self.settings.window_height - 24))

    def render_maze(self) -> None:
        # 拿到camera窗口
        cam_x, cam_y = self.get_camera_xy()
        for y in range(self.camera_tiles_h):
            for x in range(self.camera_tiles_w):
                mx = cam_x + x
                my = cam_y + y
                if mx<0 or mx>=self.maze.width or my<0 or my>=self.maze.height:
                    continue
                cell = self.maze.grid[my][mx]
                px = x*self.cell_size + (self.center_px - self.half_camera_w*self.cell_size)
                py = y*self.cell_size + (self.center_py - self.half_camera_h*self.cell_size)
                rect = pygame.Rect(px, py, self.cell_size, self.cell_size)
                # ---Floor填充明亮色---
                pygame.draw.rect(self.screen, (225,225,229), rect)
                # ---事件脉动点---
                if cell.decision_node and (mx, my) not in self.state.visited_nodes:
                    base = 180 + int(35*math.sin(self.node_anim_tick/14.0 + (mx+my)*0.7))
                    for rad in reversed(range(12, self.cell_size//2, 2)):
                        alpha = int(38*math.sin(self.node_anim_tick/15.0 + rad + mx*1.3))
                        surf = pygame.Surface((rad*2, rad*2), pygame.SRCALPHA)
                        pygame.draw.circle(surf, (255,246,200,93+alpha), (rad,rad), rad)
                        self.screen.blit(surf, (px+self.cell_size//2-rad, py+self.cell_size//2-rad), special_flags=pygame.BLEND_RGBA_ADD)
                # ---墙体加粗线---
                wall = cell.walls
                thick = 5
                clr = (80,80,120)
                # 都要减1像素避免双边重叠
                if wall["north"]:
                    pygame.draw.line(self.screen, clr, (px, py), (px + self.cell_size -1, py), thick)
                if wall["south"]:
                    pygame.draw.line(self.screen, clr, (px, py + self.cell_size -1), (px + self.cell_size -1, py + self.cell_size -1), thick)
                if wall["west"]:
                    pygame.draw.line(self.screen, clr, (px, py), (px, py + self.cell_size -1), thick)
                if wall["east"]:
                    pygame.draw.line(self.screen, clr, (px + self.cell_size -1, py), (px + self.cell_size -1, py + self.cell_size -1), thick)

    def render_player(self) -> None:
        # 主角始终绘制在中心
        px = self.center_px
        py = self.center_py
        color_dir = {
            "down": (240,72,90),
            "up": (60,140,255),
            "left": (120,210,88),
            "right": (120,80,210)
        }
        c = color_dir.get(self.player_dir,'down') if hasattr(self,'player_dir') else (220,200,120)
        jitter = int(2 * math.sin(self.player_anim_tick/5.0))
        shadow_surf = pygame.Surface((self.cell_size, self.cell_size//2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf,(60,60,70,120),(0,0,self.cell_size,self.cell_size//2))
        self.screen.blit(shadow_surf,(px-self.cell_size//2, py+self.cell_size//4))
        player_rect = pygame.Rect(px-self.cell_size//2+jitter, py-self.cell_size//2+jitter, self.cell_size, self.cell_size)
        pygame.draw.rect(self.screen, c, player_rect, border_radius=self.cell_size//4)
        pygame.draw.circle(self.screen,(255,255,255,160),(px,py-self.cell_size//6),self.cell_size//7)
        pygame.draw.rect(self.screen, (20,20,40), player_rect, 3, border_radius=self.cell_size//3)
    
    def render_pause_menu(self) -> None:
        """渲染暂停菜单"""
        # 半透明背景
        overlay = pygame.Surface((self.settings.window_width, self.settings.window_height))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # 文本
        pause_text = self.font_large.render("Game Paused", True, (255, 255, 255))
        hint_text = self.font_medium.render("Press ESC to continue", True, (200, 200, 200))
        save_text = self.font_small.render("(Progress auto-saved)", True, (150, 150, 150))
        
        self.screen.blit(
            pause_text,
            (self.settings.window_width // 2 - pause_text.get_width() // 2, 250)
        )
        self.screen.blit(
            hint_text,
            (self.settings.window_width // 2 - hint_text.get_width() // 2, 300)
        )
        self.screen.blit(
            save_text,
            (self.settings.window_width // 2 - save_text.get_width() // 2, 340)
        )

