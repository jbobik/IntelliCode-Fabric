"""
Coder Agent v4 — генерирует код, реализует функции, inline-редактирование.

Улучшения v4:
- НЕ удаляет <think> теги — orchestrator извлечёт и покажет в UI
- lang_instruction для ответов на языке пользователя
- Улучшенная extraction кода из ответа
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CoderAgent:
    def __init__(self, llm):
        self.llm = llm

    async def generate(self, message: str, context: str,
                       selected_code: Optional[str] = None, analysis: str = "",
                       lang_instruction: str = "") -> dict:
        prompt = (
            "<|system|>\n"
            "You are an expert code generator. Write clean, well-documented, production-ready code.\n\n"
            f"{lang_instruction}\n\n"
            "Rules:\n"
            "1. Follow the coding style and conventions visible in the project context\n"
            "2. Include proper error handling\n"
            "3. Add meaningful comments and docstrings\n"
            "4. Ensure type safety where applicable\n"
            "5. Make code modular and testable\n"
            "6. Output complete, working code\n\n"
            "Format: Code block first, then brief explanation of key decisions.\n"
            "<|end|>\n"
            "<|user|>\n"
        )
        if context:
            prompt += f"## Project Context:\n```\n{context[:3000]}\n```\n\n"
        if analysis:
            prompt += f"## Requirements Analysis:\n{analysis[:1000]}\n\n"
        if selected_code:
            prompt += f"## Existing code to extend/modify:\n```\n{selected_code}\n```\n\n"
        prompt += f"## Request: {message}\n<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        # НЕ strip_think — orchestrator извлечёт thinking
        code = self._extract_code(response)
        return {"response": response, "code": code}

    async def inline_edit(self, code: str, instruction: str,
                          line_start: int, line_end: int, context: str = "",
                          lang_instruction: str = "") -> dict:
        prompt = (
            "<|system|>\n"
            "You are a precise code editor. Apply the given instruction to the code.\n"
            "Output ONLY the modified code, nothing else.\n"
            "Preserve indentation, style, and all unrelated functionality.\n"
            f"{lang_instruction}\n"
            "<|end|>\n"
            "<|user|>\n"
            f"## Code (lines {line_start}-{line_end}):\n```\n{code}\n```\n\n"
        )
        if context:
            prompt += f"## Project context:\n```\n{context[:1500]}\n```\n\n"
        prompt += f"## Edit instruction: {instruction}\n\nOutput only the edited code:\n<|end|>\n<|assistant|>\n```\n"

        response = await self.llm.generate(prompt, max_new_tokens=1024)
        edited_code = self._extract_code(response) or response.strip()
        return {"code": edited_code, "response": f"Applied edit: {instruction}"}

    def _extract_code(self, response: str) -> Optional[str]:
        # Clean think tags for code extraction
        clean = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
        matches = re.findall(r'```(?:\w+)?\n(.*?)```', clean, re.DOTALL)
        if matches:
            return matches[0].strip()

        lines = clean.strip().split('\n')
        code_indicators = [
            'def ', 'class ', 'import ', 'from ', 'function ', 'const ',
            'let ', 'var ', 'export ', 'return ', 'async def ', 'public ',
        ]
        if lines and any(lines[0].strip().startswith(ind) for ind in code_indicators):
            return clean.strip()

        return None
