"""Mock AI Provider

本地评审实现，无需网络连接
"""

import random
from typing import Optional
from .provider_base import AIProvider
from ..core.models import Question, Answer, Review
from ..core.rules import calculate_growth, get_stage_themes


class MockProvider(AIProvider):
    """Mock AI Provider - 本地评审"""
    
    def __init__(self):
        """初始化 Mock Provider"""
        self._question_pools = self._init_question_pools()
        self._question_counter = 0
    
    @property
    def name(self) -> str:
        return "Mock Provider (Local)"
    
    def get_question(self, age: int, stage: str, history_tags: list[str]) -> Question:
        """从题库中获取题目
        
        Args:
            age: 玩家年龄
            stage: 人生阶段
            history_tags: 历史标签
            
        Returns:
            Question 对象
        """
        # 获取该阶段的题目池
        pool = self._question_pools.get(stage, self._question_pools["preteen"])
        
        # 过滤掉最近答过的主题
        recent_tags = set(history_tags[-5:]) if history_tags else set()
        available = [q for q in pool if not any(tag in recent_tags for tag in (q.tags or []))]
        
        if not available:
            available = pool
        
        # 随机选择
        question = random.choice(available)
        
        # 生成唯一 ID
        self._question_counter += 1
        question.id = f"{stage}_{self._question_counter}_{random.randint(1000, 9999)}"
        
        return question
    
    def review(self, age: int, question: Question, answer: Answer) -> Review:
        """评审答案
        
        使用启发式规则评估
        
        Args:
            age: 玩家年龄
            question: 题目
            answer: 答案
            
        Returns:
            Review 对象
        """
        # 检查答案是否为空
        if answer.is_empty():
            return Review(
                growth_delta=0,
                match_score=0.0,
                feedback="No answer provided. Try sharing your thoughts!"
            )
        
        # 获取答案文本
        answer_text = ""
        if answer.choice_id is not None and question.options:
            if 0 <= answer.choice_id < len(question.options):
                answer_text = question.options[answer.choice_id]
        if answer.free_text:
            answer_text += " " + answer.free_text
        
        answer_text = answer_text.strip()
        
        # 计算匹配分数
        match_score = self._calculate_match_score(answer_text, age)
        
        # 计算成长值
        growth_delta = calculate_growth(
            difficulty=question.difficulty,
            match_score=match_score,
            base=4
        )
        
        # 生成反馈
        feedback = self._generate_feedback(growth_delta, match_score, age)
        
        return Review(
            growth_delta=growth_delta,
            match_score=match_score,
            feedback=feedback
        )
    
    def _calculate_match_score(self, answer_text: str, age: int) -> float:
        """计算匹配分数
        
        基于启发式规则
        """
        if not answer_text:
            return 0.0
        
        score = 0.4  # 基础分
        
        # 长度奖励
        if len(answer_text) > 20:
            score += 0.2
        if len(answer_text) > 50:
            score += 0.1
        
        # 关键词奖励
        positive_keywords = [
            "因为", "所以", "但是", "可能", "应该", "如果",
            "帮助", "理解", "感受", "公平", "责任", "诚实",
            "尊重", "关心", "考虑", "影响", "后果", "原则"
        ]
        
        keyword_count = sum(1 for kw in positive_keywords if kw in answer_text)
        score += min(0.3, keyword_count * 0.1)
        
        # 限制在 0~1
        return min(1.0, max(0.0, score))
    
    def _generate_feedback(self, growth_delta: int, match_score: float, age: int) -> str:
        """生成反馈文本"""
        if growth_delta >= 4:
            feedbacks = [
                "Excellent thinking! You showed deep insight.",
                "Your answer reflects mature moral judgment. Keep it up!",
                "Great! You considered multiple perspectives."
            ]
        elif growth_delta >= 2:
            feedbacks = [
                "Good idea! Thinking deeper would be even better.",
                "Your answer has depth. Try considering more angles?",
                "A great start. More thinking brings more rewards."
            ]
        elif growth_delta >= 0:
            feedbacks = [
                "An honest answer. Keep trying!",
                "Nice attempt. Try to be more detailed next time.",
                "Your thoughts are genuine. Keep thinking."
            ]
        else:
            feedbacks = [
                "Try thinking about this from multiple angles.",
                "This question deserves deeper thought.",
                "Take your time. You'll discover something new."
            ]
        
        return random.choice(feedbacks)
    
    def _init_question_pools(self) -> dict[str, list[Question]]:
        """初始化题目池"""
        return {
            "child": [
                Question(
                    id="child_1",
                    prompt="You and your friend want to play with the same toy, but there's only one. What will you do?",
                    options=["I play first, then give it to them", "We take turns", "Let them have it"],
                    difficulty=0.3,
                    tags=["sharing", "fairness"]
                ),
                Question(
                    id="child_2",
                    prompt="You accidentally broke mom's favorite vase. What will you do?",
                    options=["Tell the truth", "Hide it", "Say I don't know"],
                    difficulty=0.4,
                    tags=["honesty", "responsibility"]
                ),
            ],
            "preteen": [
                Question(
                    id="preteen_1",
                    prompt="During a test, your best friend signals they want to see your answers. The teacher didn't notice. What will you do?",
                    options=["Pretend I didn't see", "Let them see", "Tell them after the test it's wrong"],
                    difficulty=0.5,
                    tags=["honesty", "rules", "friendship"]
                ),
                Question(
                    id="preteen_2",
                    prompt="A classmate borrowed a popular book from the class library and hasn't returned it for a long time. What will you do?",
                    options=["Remind them to return it", "Tell the teacher", "Don't get involved"],
                    difficulty=0.4,
                    tags=["fairness", "responsibility", "rules"]
                ),
                Question(
                    id="preteen_3",
                    prompt="On the way home, you see a younger student being mocked by several people. What will you do?",
                    options=["Go stop them", "Tell the teacher", "Pretend I didn't see"],
                    difficulty=0.6,
                    tags=["justice", "courage", "empathy"]
                ),
            ],
            "teen": [
                Question(
                    id="teen_1",
                    prompt="An embarrassing photo of a classmate is circulating in your social circle. Everyone is sharing and commenting. You know they're very upset. What will you do?",
                    options=["Don't share, comfort them privately", "Join everyone", "Say in the group this is wrong"],
                    difficulty=0.6,
                    tags=["peer pressure", "respect", "online ethics"]
                ),
                Question(
                    id="teen_2",
                    prompt="Your parents want to check your phone messages for your own good. You think this invades your privacy. How will you handle it?",
                    options=["Refuse and explain why", "Agree but express dissatisfaction", "Communicate openly and honestly"],
                    difficulty=0.7,
                    tags=["privacy", "trust", "communication"]
                ),
                Question(
                    id="teen_3",
                    prompt="You discover your best friend might have some risky behaviors (like smoking or drinking). What will you do?",
                    options=["Directly dissuade them", "Tell their parents or teacher", "Respect their choice"],
                    difficulty=0.8,
                    tags=["friendship", "responsibility", "care"]
                ),
            ],
            "young_adult": [
                Question(
                    id="ya_1",
                    prompt="During an internship, you find an obvious problem in a company process that wastes resources. But you're just an intern, and speaking up might offend your supervisor. What will you do?",
                    options=["Suggest through proper channels", "Discuss privately with colleagues", "Stay silent"],
                    difficulty=0.7,
                    tags=["professional ethics", "responsibility", "communication"]
                ),
                Question(
                    id="ya_2",
                    prompt="Your roommate often plays games late at night, affecting your rest. But they've been under a lot of stress lately. How will you handle it?",
                    options=["Communicate directly, find a solution", "Be patient and understanding", "Complain to the RA"],
                    difficulty=0.6,
                    tags=["relationships", "boundaries", "empathy"]
                ),
            ],
            "adult": [
                Question(
                    id="adult_1",
                    prompt="Work is busy, but your child's school event requires parents to attend. A colleague can help with your work, but it adds to their burden. What will you choose?",
                    options=["Attend event, ask colleague for help", "Finish work, have family attend instead", "Try to balance both"],
                    difficulty=0.8,
                    tags=["family responsibility", "work", "balance"]
                ),
                Question(
                    id="adult_2",
                    prompt="The community wants to build a new waste facility near your home. The community needs it, but it will affect your quality of life. What will you do?",
                    options=["Support public interest", "Oppose and suggest alternatives", "Unite neighbors to protest"],
                    difficulty=0.7,
                    tags=["public interest", "personal interest", "community"]
                ),
            ],
            "mature": [
                Question(
                    id="mature_1",
                    prompt="Your subordinate is very capable but poor at handling relationships. A promotion opportunity arises; promoting them might cause team conflicts. How will you decide?",
                    options=["Promote by ability, communicate well", "Consider team harmony, choose someone else", "Give them a chance with conditions"],
                    difficulty=0.9,
                    tags=["leadership", "fairness", "team"]
                ),
                Question(
                    id="mature_2",
                    prompt="You find some industry practices, though common, may be unethical. Changing them requires great effort and might affect your position. What will you do?",
                    options=["Push for change", "Speak up moderately", "Accept the status quo"],
                    difficulty=0.8,
                    tags=["professional ethics", "influence", "principles"]
                ),
            ],
            "senior": [
                Question(
                    id="senior_1",
                    prompt="Young people ask you for life advice, but you know some truths they need to experience themselves. How will you share?",
                    options=["Share experiences, let them think", "Give direct advice", "Encourage them to explore"],
                    difficulty=0.6,
                    tags=["wisdom", "legacy", "guidance"]
                ),
                Question(
                    id="senior_2",
                    prompt="You want to leave your life's accumulated resources to your descendants, but also see many people in society who need help. How will you arrange it?",
                    options=["Mainly leave to family", "Partly for charity", "Balanced distribution"],
                    difficulty=0.7,
                    tags=["legacy", "responsibility", "values"]
                ),
            ],
        }


# 创建默认实例
default_mock_provider = MockProvider()

