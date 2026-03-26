"""
Refactor Agent — рефакторит код с применением паттернов проектирования.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _strip_think(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"</?think>", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class RefactorAgent:
    def __init__(self, llm):
        self.llm = llm

    async def refactor(self, code: str, instruction: str,
                       context: str = "", pattern: Optional[str] = None) -> dict:
        """Рефакторит код по инструкции"""

        pattern_hint = ""
        if pattern:
            pattern_descriptions = {
                "strategy": "Replace conditionals with Strategy pattern: define an interface, create concrete strategy classes, use dependency injection.",
                "observer": "Implement Observer pattern: create Subject/Observable and Observer interfaces, notify observers on state changes.",
                "factory": "Apply Factory pattern: extract object creation into a factory class/method.",
                "decorator": "Use Decorator pattern: create wrapper classes that add behavior without modifying original.",
                "singleton": "Implement Singleton pattern: ensure single instance with controlled access.",
                "solid": "Apply SOLID principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.",
                "dry": "Apply DRY principle: extract duplicated code into reusable functions/methods.",
                "clean": "Apply Clean Code principles: meaningful names, small functions, clear structure.",
            }
            pattern_hint = pattern_descriptions.get(pattern.lower(), f"Apply the '{pattern}' pattern/principle.")

        prompt = (
            "<|system|>\n"
            "You are an expert software architect and refactoring specialist.\n"
            "CRITICAL: Do NOT output <think> tags or internal reasoning. Output only your final refactored code and explanation.\n\n"
            "Rules:\n"
            "1. Preserve the original functionality exactly\n"
            "2. Improve code quality, readability, and maintainability\n"
            "3. Follow SOLID principles unless asked otherwise\n"
            "4. Add/improve documentation\n"
            "5. Improve error handling\n"
            "6. Make the code more testable\n\n"
            "Output format:\n"
            "1. Brief explanation of changes and why\n"
            "2. Complete refactored code in a code block\n"
            "3. Summary of key improvements\n"
            "<|end|>\n"
            "<|user|>\n"
            f"## Code to refactor:\n```\n{code[:4000]}\n```\n\n"
        )
        if context:
            prompt += f"## Project context:\n```\n{context[:2000]}\n```\n\n"
        prompt += f"## Refactoring instruction: {instruction}\n"
        if pattern_hint:
            prompt += f"## Pattern to apply: {pattern_hint}\n"
        prompt += "<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        response = _strip_think(response)

        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        refactored_code = code_blocks[0].strip() if code_blocks else None

        return {
            "response": response,
            "refactored_code": refactored_code,
        }