"""
Analyst Agent — анализирует кодовую базу, отвечает на вопросы,
находит реализации, объясняет архитектуру.
"""

import re
import logging

logger = logging.getLogger(__name__)


class AnalystAgent:
    def __init__(self, llm):
        self.llm = llm

    async def analyze(self, question: str, context: str, history: list = None) -> dict:
        """Анализирует кодовую базу и отвечает на вопрос"""
        prompt = self._build_prompt(question, context, history or [])
        response = await self.llm.generate(prompt)
        references = self._extract_references(response)

        return {
            "response": response,
            "references": references,
        }

    async def explain(self, code: str, question: str, context: str = "") -> dict:
        """Объясняет код подробно"""
        prompt = (
            "<|system|>\n"
            "You are an expert code analyst. Explain code clearly and thoroughly.\n"
            "Include:\n"
            "1. What the code does (high-level purpose)\n"
            "2. How it works (step-by-step breakdown)\n"
            "3. Key design decisions and patterns used\n"
            "4. Potential issues or improvements\n"
            "5. How it fits into the broader codebase\n"
            "<|end|>\n"
            "<|user|>\n"
            f"## Code to explain:\n```\n{code}\n```\n\n"
        )
        if context:
            prompt += f"## Additional context:\n```\n{context[:2000]}\n```\n\n"
        prompt += f"## Specific question: {question}\n<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        return {"response": response}

    def _build_prompt(self, question, context, history) -> str:
        system = (
            "You are an expert code analyst. Your role is to:\n"
            "1. Analyze codebases thoroughly\n"
            "2. Answer questions about code structure, patterns, and implementation\n"
            "3. Find specific implementations (authentication, database access, API endpoints, etc.)\n"
            "4. Identify potential issues and improvement opportunities\n"
            "5. Reference specific files and line numbers\n\n"
            "Always be specific and cite the exact files and code sections."
        )

        parts = [f"<|system|>\n{system}\n<|end|>"]
        for h in (history or [])[-4:]:
            role = h.get("role", "user")
            parts.append(f"<|{role}|>\n{h['content']}\n<|end|>")

        user_msg = ""
        if context:
            user_msg += f"## Relevant Code:\n```\n{context[:3000]}\n```\n\n"
        user_msg += f"## Question: {question}"

        parts.append(f"<|user|>\n{user_msg}\n<|end|>")
        parts.append("<|assistant|>")
        return "\n".join(parts)

    def _extract_references(self, response: str) -> list:
        """Извлекает ссылки на файлы из ответа"""
        refs = set()
        # Находит упоминания файлов типа `path/to/file.py`
        for match in re.findall(r'`([^`]*\.\w{1,5})`', response):
            if '/' in match or '\\' in match or '.' in match:
                refs.add(match)
        return list(refs)[:10]