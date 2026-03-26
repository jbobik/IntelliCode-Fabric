"""
Analyst Agent — анализирует кодовую базу, отвечает на вопросы,
находит реализации, объясняет архитектуру.

Улучшения:
- Системный промт явно запрещает <think> теги в выводе
- Более структурированные промты
- Лучшая работа с историей диалога
"""

import re
import logging

logger = logging.getLogger(__name__)


def _strip_think(text: str) -> str:
    """Убирает <think>...</think> блоки из ответа"""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"</?think>", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class AnalystAgent:
    def __init__(self, llm):
        self.llm = llm

    async def analyze(self, question: str, context: str, history: list = None) -> dict:
        """Анализирует кодовую базу и отвечает на вопрос"""
        prompt = self._build_prompt(question, context, history or [])
        response = await self.llm.generate(prompt)
        response = _strip_think(response)
        references = self._extract_references(response)

        return {
            "response": response,
            "references": references,
        }

    async def explain(self, code: str, question: str, context: str = "") -> dict:
        """Объясняет код подробно"""
        prompt = (
            "<|system|>\n"
            "You are an expert code analyst. Your task is to explain code clearly and thoroughly.\n"
            "IMPORTANT: Do NOT output <think> tags or any internal reasoning. Output only your final explanation.\n\n"
            "Structure your explanation:\n"
            "1. **Purpose**: What the code does (high-level)\n"
            "2. **How it works**: Step-by-step breakdown\n"
            "3. **Key patterns**: Design decisions and patterns used\n"
            "4. **Potential issues**: Bugs, edge cases, or improvements\n"
            "5. **Context**: How it fits into the broader codebase\n"
            "<|end|>\n"
            "<|user|>\n"
            f"## Code to explain:\n```\n{code}\n```\n\n"
        )
        if context:
            prompt += f"## Additional context from project:\n```\n{context[:2000]}\n```\n\n"
        prompt += f"## Question: {question}\n<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        return {"response": _strip_think(response)}

    def _build_prompt(self, question, context, history) -> str:
        system = (
            "You are an expert code analyst with deep knowledge of software architecture.\n"
            "CRITICAL: Do NOT output <think> tags or internal reasoning chains. Output only your final answer.\n\n"
            "Your role:\n"
            "1. Analyze codebases thoroughly and accurately\n"
            "2. Answer questions about code structure, patterns, and implementation\n"
            "3. Find specific implementations with exact file references\n"
            "4. Identify potential issues and improvement opportunities\n"
            "5. Always cite specific files, functions, and line numbers when available\n\n"
            "Be specific, cite files, and provide actionable insights."
        )

        parts = [f"<|system|>\n{system}\n<|end|>"]
        for h in (history or [])[-4:]:
            role = h.get("role", "user")
            parts.append(f"<|{role}|>\n{h['content']}\n<|end|>")

        user_msg = ""
        if context:
            user_msg += f"## Relevant Project Code:\n```\n{context[:3000]}\n```\n\n"
        user_msg += f"## Question: {question}"

        parts.append(f"<|user|>\n{user_msg}\n<|end|>")
        parts.append("<|assistant|>")
        return "\n".join(parts)

    def _extract_references(self, response: str) -> list:
        """Извлекает ссылки на файлы из ответа"""
        refs = set()
        for match in re.findall(r'`([^`]*\.\w{1,5})`', response):
            if '/' in match or '\\' in match or '.' in match:
                refs.add(match)
        return list(refs)[:10]