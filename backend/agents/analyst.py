"""
Analyst Agent v4 — анализирует кодовую базу, отвечает на вопросы,
находит реализации, объясняет архитектуру.

Улучшения v4:
- НЕ удаляет <think> теги — это делает orchestrator через strip_think_tags(),
  чтобы thinking блоки доходили до UI
- sanitize_response применяется
- lang_instruction → ответ на языке пользователя
"""

import re
import logging

from .utils import sanitize_response

logger = logging.getLogger(__name__)


class AnalystAgent:
    def __init__(self, llm):
        self.llm = llm

    async def analyze(self, question, context, history=None, lang_instruction=""):
        prompt = self._build_prompt(question, context, history or [], lang_instruction)
        response = await self.llm.generate(prompt)
        # НЕ strip_think — orchestrator извлечёт thinking
        response = sanitize_response(response)
        references = self._extract_references(response)
        return {"response": response, "references": references}

    async def explain(self, code: str, question: str, context: str = "",
                      lang_instruction: str = "") -> dict:
        """Объясняет код подробно"""
        prompt = (
            "<|system|>\n"
            "You are an expert code analyst. Your task is to explain code clearly and thoroughly.\n\n"
            f"{lang_instruction}\n\n"
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
            prompt += f"## Additional context from project:\n```\n{context[:5000]}\n```\n\n"
        prompt += f"## Question: {question}\n<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        return {"response": response}

    async def explain_with_fixes(self, code: str, question: str, context: str = "",
                                 lang_instruction: str = "") -> dict:
        """
        Объясняет код подробно И предлагает улучшенную версию.
        """
        prompt = (
            "<|system|>\n"
            "You are an expert code analyst and improver. Your task is to:\n"
            "1. Explain the code clearly\n"
            "2. Identify ALL potential issues\n"
            "3. Provide a COMPLETE IMPROVED VERSION of the code\n\n"
            f"{lang_instruction}\n\n"
            "Structure your response EXACTLY like this:\n"
            "## Purpose\n"
            "What the code does\n\n"
            "## How It Works\n"
            "Step-by-step breakdown\n\n"
            "## Key Patterns\n"
            "Design decisions used\n\n"
            "## Issues Found\n"
            "For EACH issue:\n"
            "- **Problem**: description\n"
            "- **Impact**: why it matters\n"
            "- **Fix**: specific fix\n\n"
            "## Improved Code\n"
            "For EACH file that needs changes, use this format:\n\n"
            "Действие: заменить\n"
            "Файл: path/to/file.ext\n"
            "Строки: START-END\n"
            "```lang\n"
            "improved code\n"
            "```\n\n"
            "ALWAYS include Действие, Файл, and Строки before each code block.\n"
            "If multiple files need changes, output a separate block for each.\n\n"
            "## Summary of Changes\n"
            "Brief list of all improvements made\n"
            "<|end|>\n"
            "<|user|>\n"
            f"## Code to analyze and improve:\n```\n{code[:4000]}\n```\n\n"
        )
        if context:
            prompt += f"## Project context:\n```\n{context[:5000]}\n```\n\n"
        prompt += f"## Question: {question}\n<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        # НЕ удаляем think теги — orchestrator сделает это и покажет в UI

        # Извлекаем улучшенный код (без think тегов для парсинга)
        clean_for_parse = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', clean_for_parse, re.DOTALL)
        improved_code = code_blocks[-1].strip() if code_blocks else None

        return {
            "response": response,
            "improved_code": improved_code,
        }

    def _build_prompt(self, question, context, history, lang_instruction: str = "") -> str:
        system = (
            "You are an expert code analyst with deep knowledge of software architecture.\n\n"
            f"{lang_instruction}\n\n"
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
            user_msg += f"## Relevant Project Code:\n```\n{context[:5000]}\n```\n\n"
        user_msg += f"## Question: {question}"

        parts.append(f"<|user|>\n{user_msg}\n<|end|>")
        parts.append("<|assistant|>")
        return "\n".join(parts)

    def _extract_references(self, response: str) -> list:
        # Clean think tags for reference extraction
        clean = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        refs = set()
        for match in re.findall(r'`([^`]*\.\w{1,5})`', clean):
            if '/' in match or '\\' in match or '.' in match:
                refs.add(match)
        return list(refs)[:10]
