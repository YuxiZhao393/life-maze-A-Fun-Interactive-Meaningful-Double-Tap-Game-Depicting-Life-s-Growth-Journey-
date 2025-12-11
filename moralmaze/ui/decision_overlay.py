"""决策弹窗

显示道德困境题目、选项、输入框，并展示评审结果
"""

import pygame
from typing import Optional, Dict
from ..core.models import Question, Answer, Review
from ..core.state import Settings


class Button:
    """简单按钮类"""
    
    def __init__(self, rect: pygame.Rect, text: str, color: tuple, hover_color: tuple):
        self.rect = rect
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.hovered = False
    
    def update(self, mouse_pos: tuple[int, int]) -> None:
        """更新悬停状态"""
        self.hovered = self.rect.collidepoint(mouse_pos)
    
    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """绘制按钮"""
        color = self.hover_color if self.hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (80, 80, 80), self.rect, 2, border_radius=8)
        
        text_surf = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
    
    def is_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        """检查是否被点击"""
        return self.rect.collidepoint(mouse_pos)


class InputBox:
    """文本输入框"""
    
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font, max_length: int = 200):
        self.rect = rect
        self.font = font
        self.max_length = max_length
        self.text = ""
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
    
    def handle_event(self, event: pygame.event.Event) -> None:
        """处理事件"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                pass  # Enter 键不处理
            elif len(self.text) < self.max_length:
                self.text += event.unicode
    
    def update(self, dt: int) -> None:
        """更新光标闪烁"""
        self.cursor_timer += dt
        if self.cursor_timer > 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0
    
    def draw(self, screen: pygame.Surface) -> None:
        """绘制输入框"""
        # 背景
        color = (255, 255, 255) if self.active else (240, 240, 240)
        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        border_color = (100, 150, 200) if self.active else (180, 180, 180)
        pygame.draw.rect(screen, border_color, self.rect, 2, border_radius=5)
        
        # 文本
        if self.text:
            # 支持换行的文本渲染
            lines = self._wrap_text(self.text, self.rect.width - 20)
            y_offset = self.rect.y + 10
            for line in lines[:3]:  # 最多显示3行
                text_surf = self.font.render(line, True, (40, 40, 40))
                screen.blit(text_surf, (self.rect.x + 10, y_offset))
                y_offset += self.font.get_height() + 2
        else:
            # 占位符
            placeholder = self.font.render("Enter your thoughts here...", True, (150, 150, 150))
            screen.blit(placeholder, (self.rect.x + 10, self.rect.y + 10))
        
        # 光标
        if self.active and self.cursor_visible:
            cursor_x = self.rect.x + 10 + self.font.size(self.text[-50:])[0]
            cursor_y = self.rect.y + 10
            pygame.draw.line(
                screen,
                (40, 40, 40),
                (cursor_x, cursor_y),
                (cursor_x, cursor_y + self.font.get_height()),
                2
            )
    
    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """文本换行"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if self.font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines


class DecisionOverlay:
    """决策弹窗"""
    
    def __init__(
        self,
        screen: pygame.Surface,
        question: Question,
        settings: Settings,
        font_large: pygame.font.Font,
        font_medium: pygame.font.Font,
        font_small: pygame.font.Font
    ):
        self.screen = screen
        self.question = question
        self.settings = settings
        self.font_large = font_large
        self.font_medium = font_medium
        self.font_small = font_small
        
        # 状态
        self.selected_option: Optional[int] = None
        self.review: Optional[Review] = None
        self.showing_review = False
        self.pending_submit = False
        
        # 卡片面板定位优化：宽度70% 高度60% 居中
        panel_width = int(settings.window_width * 0.7)
        panel_height = int(settings.window_height * 0.60)
        panel_x = (settings.window_width - panel_width) // 2
        panel_y = int(settings.window_height * 0.2)
        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # 选项按钮
        btn_height = 32
        btn_font = self.font_small
        self.option_buttons: list[Button] = []
        if question.options:
            button_y = panel_y + 120
            for i, option in enumerate(question.options):
                rect = pygame.Rect(panel_x+26, button_y, panel_width-52, btn_height)
                button = Button(
                    rect, f"{i+1}. {option}",(100,150,200),(120,170,220))
                self.option_buttons.append(button)
                button_y += btn_height+8
        
        # 输入框
        input_y = panel_y + 120 + len(self.option_buttons)*(btn_height+8)+18
        self.input_box = InputBox(
            pygame.Rect(panel_x + 26, input_y, panel_width - 52, 52), btn_font)
        
        # 提交按钮
        submit_y = input_y + 62
        self.submit_button = Button(
            pygame.Rect(panel_x + panel_width//2-54, submit_y, 108, 32),"Submit", (70,180,70),(90,200,90))
        
        # 关闭按钮缩小，靠右上
        self.close_button = Button(
            pygame.Rect(panel_x+panel_width-50, panel_y+7, 38, 20),"Close", (180,70,70),(200,90,90))
        
        self.last_time = pygame.time.get_ticks()
    
    def handle_event(self, event: pygame.event.Event) -> None:
        """处理事件"""
        if self.showing_review:
            # 评审页面只处理关闭
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                if self.close_button.is_clicked(mouse_pos):
                    # 触发关闭
                    pass
            return
        
        # 输入框事件
        self.input_box.handle_event(event)
        
        # 鼠标点击
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            
            # 选项按钮
            for i, button in enumerate(self.option_buttons):
                if button.is_clicked(mouse_pos):
                    self.selected_option = i
            
            # 提交按钮
            if self.submit_button.is_clicked(mouse_pos):
                self.pending_submit = True
    
    def update(self) -> Optional[Dict]:
        """更新状态
        
        Returns:
            {"action": "submit", "answer": Answer} 或
            {"action": "close"} 或 None
        """
        current_time = pygame.time.get_ticks()
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # 更新输入框
        self.input_box.update(dt)
        
        # 更新按钮悬停状态
        mouse_pos = pygame.mouse.get_pos()
        for button in self.option_buttons:
            button.update(mouse_pos)
        self.submit_button.update(mouse_pos)
        self.close_button.update(mouse_pos)
        
        # 检查是否点击关闭
        if self.showing_review:
            if pygame.mouse.get_pressed()[0] and self.close_button.is_clicked(mouse_pos):
                return {"action": "close"}
        
        return None
    
    def show_review(self, review: Review) -> None:
        """显示评审结果"""
        self.review = review
        self.showing_review = True
    
    def _submit_answer(self) -> None:
        """提交答案（内部方法）"""
        # 此方法不再直接返回，而是通过外部调用 show_review
        pass
    
    def render(self) -> None:
        # 只在panel区域做半透明暗化，其它迷宫不被完全遮住
        overlay = pygame.Surface((self.settings.window_width, self.settings.window_height), pygame.SRCALPHA)
        dark_rect = pygame.Surface((self.panel_rect.width+32,self.panel_rect.height+32), pygame.SRCALPHA)
        dark_rect.fill((40,40,40,170))
        overlay.blit(dark_rect,(self.panel_rect.x-16,self.panel_rect.y-16))
        self.screen.blit(overlay, (0,0))
        if self.showing_review:
            self._render_review_card()
        else:
            self._render_question_card()
    
    def _render_question_card(self) -> None:
        """渲染题目卡片"""
        # 面板背景
        pygame.draw.rect(self.screen, (250, 245, 240), self.panel_rect, border_radius=15)
        pygame.draw.rect(self.screen, (100, 100, 100), self.panel_rect, 3, border_radius=15)
        
        # 标题
        title = self.font_large.render("Moral Dilemma", True, (80, 80, 80))
        self.screen.blit(title, (self.panel_rect.x + 50, self.panel_rect.y + 30))
        
        # 题目文本（支持换行）
        prompt_lines = self._wrap_text(self.question.prompt, self.panel_rect.width - 100)
        y_offset = self.panel_rect.y + 80
        for line in prompt_lines:
            text_surf = self.font_medium.render(line, True, (40, 40, 40))
            self.screen.blit(text_surf, (self.panel_rect.x + 50, y_offset))
            y_offset += self.font_medium.get_height() + 5
        
        # 选项按钮
        for i, button in enumerate(self.option_buttons):
            # 高亮选中的选项
            if self.selected_option == i:
                pygame.draw.rect(
                    self.screen,
                    (255, 220, 100),
                    button.rect.inflate(10, 10),
                    3,
                    border_radius=10
                )
            button.draw(self.screen, self.font_small)
        
        # 输入框
        self.input_box.draw(self.screen)
        
        # 提交按钮
        self.submit_button.draw(self.screen, self.font_medium)
        
        # 提示文本
        hint = self.font_small.render(
            "Choose an option or enter your thoughts",
            True,
            (120, 120, 120)
        )
        self.screen.blit(
            hint,
            (self.panel_rect.centerx - hint.get_width() // 2, self.panel_rect.bottom - 40)
        )
    
    def _render_review_card(self) -> None:
        """渲染评审卡片"""
        if not self.review:
            return
        
        # 面板背景
        pygame.draw.rect(self.screen, (245, 250, 245), self.panel_rect, border_radius=15)
        pygame.draw.rect(self.screen, (100, 100, 100), self.panel_rect, 3, border_radius=15)
        
        # 标题
        title = self.font_large.render("Review Feedback", True, (80, 80, 80))
        self.screen.blit(title, (self.panel_rect.x + 50, self.panel_rect.y + 30))
        
        # 成长值
        delta = self.review.growth_delta
        color = (50, 180, 50) if delta > 0 else (180, 50, 50) if delta < 0 else (100, 100, 100)
        growth_text = self.font_large.render(
            f"Growth: {delta:+d}",
            True,
            color
        )
        self.screen.blit(
            growth_text,
            (self.panel_rect.centerx - growth_text.get_width() // 2, self.panel_rect.y + 120)
        )
        
        # 匹配分数
        score_text = self.font_medium.render(
            f"Reflection Depth: {self.review.match_score:.0%}",
            True,
            (80, 80, 80)
        )
        self.screen.blit(
            score_text,
            (self.panel_rect.centerx - score_text.get_width() // 2, self.panel_rect.y + 180)
        )
        
        # 反馈文本
        feedback_lines = self._wrap_text(self.review.feedback, self.panel_rect.width - 100)
        y_offset = self.panel_rect.y + 240
        for line in feedback_lines:
            text_surf = self.font_medium.render(line, True, (60, 60, 60))
            self.screen.blit(
                text_surf,
                (self.panel_rect.centerx - text_surf.get_width() // 2, y_offset)
            )
            y_offset += self.font_medium.get_height() + 5
        
        # 关闭按钮
        self.close_button.draw(self.screen, self.font_small)
        
        # 提示
        hint = self.font_small.render(
            "Click Close or press ESC to continue exploring",
            True,
            (120, 120, 120)
        )
        self.screen.blit(
            hint,
            (self.panel_rect.centerx - hint.get_width() // 2, self.panel_rect.bottom - 40)
        )
    
    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """文本换行"""
        words = list(text)  # 中文按字符分
        lines = []
        current_line = ""
        
        for char in words:
            test_line = current_line + char
            if self.font_medium.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def get_answer(self) -> Answer:
        """获取玩家答案"""
        return Answer(
            choice_id=self.selected_option,
            free_text=self.input_box.text if self.input_box.text else None
        )

