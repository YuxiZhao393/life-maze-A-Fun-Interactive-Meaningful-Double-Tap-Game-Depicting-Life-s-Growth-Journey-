"""Ollama AI Provider

使用本地 Ollama 模型进行题目生成和评审
"""

import subprocess
import json
import re
import os
import platform
from typing import Optional
from .provider_base import AIProvider
from .provider_mock import MockProvider
from ..core.models import Question, Answer, Review
from .prompts import format_question_prompt, format_review_prompt, SYSTEM_PROMPT
import requests


def _get_ollama_command() -> str:
    """
    获取 Ollama 命令路径
    """
    # Windows 默认安装路径
    if platform.system() == "Windows":
        default_path = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs", "Ollama", "ollama.exe"
        )
        if os.path.exists(default_path):
            return default_path
    
    # 尝试从 PATH 中找
    return "ollama"


def _list_ollama_models() -> list[str]:
    """
    列出当前 Ollama 已安装的模型名称列表
    """
    try:
        ollama_cmd = _get_ollama_command()
        # 先尝试 JSON 格式（新版本）
        try:
            out = subprocess.check_output(
                [ollama_cmd, "list", "--format", "json"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            data = json.loads(out)
            return [m["name"] for m in data]
        except:
            # 回退到文本格式解析（旧版本）
            out = subprocess.check_output(
                [ollama_cmd, "list"],
                text=True,
                stderr=subprocess.DEVNULL
            )
            models = []
            for line in out.strip().split('\n')[1:]:  # 跳过标题行
                parts = line.split()
                if parts:
                    models.append(parts[0])  # 第一列是模型名
            return models
    except Exception as e:
        print(f"[Ollama] Error listing models: {e}")
        return []


def extract_json(text: str) -> str:
    """从模型响应中提取 JSON
    
    处理可能包含 markdown 代码块或其他文本的响应
    """
    # 尝试提取 ```json ... ``` 或 ``` ... ``` 代码块
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # 尝试提取 {...} JSON 对象
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return text.strip()


class OllamaProvider(AIProvider):
    """
    现优先用本地 Ollama API, 如果不可用回退原有CLI
    """
    def __init__(self, model: str = "qwen2.5:3b"):
        self.model = model
        self.ollama_cmd = _get_ollama_command()
        self._client: Optional[bool] = None
        self._fallback = MockProvider()
        self.api_url = "http://localhost:11434"
        self.api_available = self._test_ollama_api()
        self._client = self.api_available or self._check_model_available()

    def _test_ollama_api(self) -> bool:
        try:
            r = requests.get(f"{self.api_url}/api/tags",timeout=1)
            return r.status_code==200
        except Exception:
            return False

    def _get_response_api(self, prompt:str, system_prompt:str=None, stream=False)->str:
        """
        用Ollama API /api/chat
        """
        messages=[{"role": "system", "content": system_prompt or SYSTEM_PROMPT}, {"role": "user", "content":prompt}]
        req_data = {
            "model": self.model,
            "messages": messages,
            "format": "json",
            "stream": stream,
        }
        try:
            resp = requests.post(f"{self.api_url}/api/chat",json=req_data,timeout=20,stream=stream)
            resp.raise_for_status()
            if stream:
                # 逐步拼接响应
                chunks = []
                for line in resp.iter_lines():
                    if not line: continue
                    # ollama api streaming 行是 { "message":...}
                    try:
                        obj = json.loads(line.decode())
                        if "message" in obj and "content" in obj["message"]:
                            chunks.append(obj["message"]["content"])
                    except Exception:continue
                return ''.join(chunks)
            else:
                result = resp.json()
                return result["message"]["content"] if "message" in result and "content" in result["message"] else resp.text
        except Exception as e:
            print(f"Ollama API error: {e}")
            raise

    def _ask(self, prompt:str) -> str:
        if self.api_available:
            try:
                # API模式用流式响应减少等待
                return self._get_response_api(prompt, SYSTEM_PROMPT, stream=True)
            except Exception:
                print("[Ollama API fallback CLI mode]")
                # 尝试CLI模式
        # CLI fallback
        process = subprocess.Popen(
            [self.ollama_cmd, "run", self.model],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(prompt)
        if stderr:
            print("[Ollama stderr]", stderr)
        return stdout.strip()

    def _check_model_available(self) -> bool:
        """检查模型是否可用"""
        models = _list_ollama_models()
        if self.model in models:
            print(f"[Ollama] Found model '{self.model}'")
            return True
        else:
            print(f"Warning: Model '{self.model}' not found in Ollama")
            if models:
                print("Available models:", ", ".join(models))
            else:
                print("No local Ollama models found.")
            print(f"To download this model, run:\n  ollama pull {self.model}")
            return False

    @property
    def name(self) -> str:
        """Provider 名称"""
        if self._client:
            return f"Ollama Provider ({self.model})"
        return "Ollama Provider (降级为 Mock)"

    def get_question(self, age: int, stage: str, history_tags: list[str]) -> Question:
        """使用 Ollama 生成题目
        
        失败时回退到 Mock Provider
        """
        if not self._client:
            return self._fallback.get_question(age, stage, history_tags)
        
        try:
            # 构建提示词
            user_prompt = format_question_prompt(age, stage, history_tags)
            full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
            
            # 调用 Ollama
            response = self._ask(full_prompt)
            
            # 提取并解析 JSON
            json_str = extract_json(response)
            data = json.loads(json_str)
            
            # 添加唯一 ID 如果缺失
            if "id" not in data:
                import random
                data["id"] = f"ollama_{age}_{random.randint(1000, 9999)}"
            
            return Question.model_validate(data)
        
        except Exception as e:
            print(f"Ollama question generation failed: {e}, falling back to Mock")
            return self._fallback.get_question(age, stage, history_tags)

    def review(self, age: int, question: Question, answer: Answer) -> Review:
        """使用 Ollama 评审答案
        
        失败时回退到 Mock Provider
        """
        if not self._client:
            return self._fallback.review(age, question, answer)
        
        try:
            # 构建答案文本
            answer_text = ""
            if answer.choice_id is not None and question.options:
                if 0 <= answer.choice_id < len(question.options):
                    answer_text = f"Choice: {question.options[answer.choice_id]}"
            if answer.free_text:
                if answer_text:
                    answer_text += f"\nFree text: {answer.free_text}"
                else:
                    answer_text = f"Free text: {answer.free_text}"
            
            if not answer_text:
                answer_text = "(No answer provided)"
            
            # 构建提示词
            user_prompt = format_review_prompt(
                age=age,
                question_prompt=question.prompt,
                question_tags=question.tags or [],
                difficulty=question.difficulty,
                answer_text=answer_text
            )
            full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
            
            # 调用 Ollama
            response = self._ask(full_prompt)
            
            # 提取并解析 JSON
            json_str = extract_json(response)
            data = json.loads(json_str)
            
            return Review.model_validate(data)
        
        except Exception as e:
            print(f"Ollama review failed: {e}, falling back to Mock")
            return self._fallback.review(age, question, answer)


def create_ollama_provider(model: Optional[str] = None) -> OllamaProvider:
    """
    外部统一调用入口
    """
    if model is None:
        model = "qwen2.5:3b"
    return OllamaProvider(model=model)
