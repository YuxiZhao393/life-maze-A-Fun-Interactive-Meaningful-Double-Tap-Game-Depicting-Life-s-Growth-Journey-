"""轨迹回顾页

展示玩家的决策历史和成长轨迹
"""

import pygame
from typing import Optional
from ..core.state import GameState, Settings
from ..core.rules import get_stage_name_en


class TimelinePage:
    """轨迹回顾页面"""
    
    def __init__(
        self,
        screen: pygame.Surface,
        state: GameState,
        settings: Settings,
        font_large: pygame.font.Font,
        font_medium: pygame.font.Font,
        font_small: pygame.font.Font
    ):
        self.screen = screen
        self.state = state
        self.settings = settings
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        
        # 滚动
        self.scroll_offset = 0
        self.max_scroll = 0
        
        # 按钮
        button_width = 200
        button_height = 50
        button_x = (settings.window_width - button_width) // 2
        button_y = settings.window_height - 80
        
        self.restart_button = pygame.Rect(button_x, button_y, button_width, button_height)
        self.restart_hovered = False
        
        # 计算内容高度
        self._calculate_content_height()
    
    def _calculate_content_height(self) -> None:
        """计算内容总高度"""
        # 标题 + 总结 + 历史记录
        base_height = 200
        record_height = len(self.state.history) * 150
        self.content_height = base_height + record_height
        self.max_scroll = max(0, self.content_height - self.settings.window_height + 150)
    
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """处理事件
        
        Returns:
            "restart" 如果点击重新开始，否则 None
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # 左键
                if self.restart_button.collidepoint(event.pos):
                    return "restart"
            elif event.button == 4:  # 滚轮向上
                self.scroll_offset = max(0, self.scroll_offset - 30)
            elif event.button == 5:  # 滚轮向下
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 30)
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.scroll_offset = max(0, self.scroll_offset - 50)
            elif event.key == pygame.K_DOWN:
                self.scroll_offset = min(self.max_scroll, self.scroll_offset + 50)
        
        return None
    
    def render(self) -> None:
        """渲染页面"""
        # 背景
        self.screen.fill((240, 240, 245))
        
        # 创建可滚动区域
        content_surface = pygame.Surface((self.settings.window_width, self.content_height))
        content_surface.fill((240, 240, 245))
        
        y_offset = 20
        
        # 标题
        title = self.font_large.render("Life Timeline Review", True, (60, 60, 80))
        content_surface.blit(
            title,
            (self.settings.window_width // 2 - title.get_width() // 2, y_offset)
        )
        y_offset += 60
        
        # 总结信息
        summary_lines = [
            f"Final Age: {self.state.age}",
            f"Life Stage: {get_stage_name_en(self.state.stage)}",
            f"Total Growth: {self.state.total_growth}",
            f"Decisions Made: {len(self.state.history)}",
        ]
        
        for line in summary_lines:
            text = self.font_medium.render(line, True, (80, 80, 80))
            content_surface.blit(
                text,
                (self.settings.window_width // 2 - text.get_width() // 2, y_offset)
            )
            y_offset += 35
        
        y_offset += 30
        
        # 分隔线
        pygame.draw.line(
            content_surface,
            (150, 150, 150),
            (100, y_offset),
            (self.settings.window_width - 100, y_offset),
            2
        )
        y_offset += 30
        
        # 历史记录标题
        history_title = self.font_medium.render("Decision History", True, (60, 60, 80))
        content_surface.blit(
            history_title,
            (self.settings.window_width // 2 - history_title.get_width() // 2, y_offset)
        )
        y_offset += 40
        
        # 历史记录列表
        for i, record in enumerate(self.state.history):
            y_offset = self._render_record(content_surface, record, i + 1, y_offset)
            y_offset += 20
        
        # 将内容渲染到主屏幕（应用滚动）
        visible_rect = pygame.Rect(
            0, self.scroll_offset,
            self.settings.window_width,
            self.settings.window_height - 150
        )
        self.screen.blit(content_surface, (0, -self.scroll_offset), visible_rect)
        
        # 底部面板（固定，不滚动）
        self._render_bottom_panel()
    
    def _render_record(
        self,
        surface: pygame.Surface,
        record,
        index: int,
        y_offset: int
    ) -> int:
        """渲染单条记录
        
        Returns:
            新的 y_offset
        """
        panel_width = self.settings.window_width - 100
        panel_x = 50
        panel_height = 130
        
        # 背景卡片
        card_rect = pygame.Rect(panel_x, y_offset, panel_width, panel_height)
        pygame.draw.rect(surface, (255, 255, 255), card_rect, border_radius=10)
        pygame.draw.rect(surface, (180, 180, 180), card_rect, 2, border_radius=10)
        
        # 序号和年龄
        header = self.font_small.render(
            f"#{index} | Age {record.age_at_decision} ({get_stage_name_en(record.stage_at_decision)})",
            True,
            (100, 100, 100)
        )
        surface.blit(header, (panel_x + 15, y_offset + 10))
        
        # 题目（截断）
        question_text = record.question.prompt[:60] + "..." if len(record.question.prompt) > 60 else record.question.prompt
        question = self.font_small.render(
            f"Question: {question_text}",
            True,
            (60, 60, 60)
        )
        surface.blit(question, (panel_x + 15, y_offset + 35))
        
        # 答案
        answer_text = ""
        if record.answer.choice_id is not None and record.question.options:
            if 0 <= record.answer.choice_id < len(record.question.options):
                answer_text = record.question.options[record.answer.choice_id][:40]
        if record.answer.free_text:
            answer_text += f" | {record.answer.free_text[:40]}"
        
        if answer_text:
            answer = self.font_small.render(
                f"Answer: {answer_text}",
                True,
                (60, 60, 60)
            )
            surface.blit(answer, (panel_x + 15, y_offset + 60))
        
        # 成长值和反馈
        delta = record.review.growth_delta
        color = (50, 150, 50) if delta > 0 else (150, 50, 50) if delta < 0 else (100, 100, 100)
        growth = self.font_small.render(
            f"Growth: {delta:+d} | {record.review.feedback[:50]}",
            True,
            color
        )
        surface.blit(growth, (panel_x + 15, y_offset + 85))
        
        return y_offset + panel_height
    
    def _render_bottom_panel(self) -> None:
        """渲染底部面板"""
        # 背景
        panel_rect = pygame.Rect(0, self.settings.window_height - 100, self.settings.window_width, 100)
        pygame.draw.rect(self.screen, (230, 230, 240), panel_rect)
        pygame.draw.line(
            self.screen,
            (180, 180, 180),
            (0, self.settings.window_height - 100),
            (self.settings.window_width, self.settings.window_height - 100),
            2
        )
        
        # 重新开始按钮
        mouse_pos = pygame.mouse.get_pos()
        self.restart_hovered = self.restart_button.collidepoint(mouse_pos)
        
        button_color = (90, 160, 90) if self.restart_hovered else (70, 140, 70)
        pygame.draw.rect(self.screen, button_color, self.restart_button, border_radius=10)
        pygame.draw.rect(self.screen, (80, 80, 80), self.restart_button, 2, border_radius=10)
        
        button_text = self.font_medium.render("Restart", True, (255, 255, 255))
        button_text_rect = button_text.get_rect(center=self.restart_button.center)
        self.screen.blit(button_text, button_text_rect)
        
        # 提示
        hint = self.font_small.render(
            "Use scroll wheel or arrow keys to scroll",
            True,
            (120, 120, 120)
        )
        self.screen.blit(
            hint,
            (self.settings.window_width // 2 - hint.get_width() // 2, self.settings.window_height - 25)
        )

