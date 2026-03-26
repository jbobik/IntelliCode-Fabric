"""
Tester Agent — генерирует unit-тесты, определяет фреймворк автоматически.
"""

import re
import logging

logger = logging.getLogger(__name__)


def _strip_think(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"</?think>", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class TesterAgent:
    def __init__(self, llm):
        self.llm = llm

    async def generate_tests(self, code: str, instruction: str = "",
                             context: str = "") -> dict:
        """Генерирует тесты для данного кода"""

        language = self._detect_language(code)
        framework = self._suggest_framework(language)

        prompt = (
            "<|system|>\n"
            f"You are an expert test engineer. Generate comprehensive tests using {framework}.\n"
            "CRITICAL: Do NOT output <think> tags or internal reasoning. Output only the final tests.\n\n"
            "Rules:\n"
            "1. Cover all public functions/methods\n"
            "2. Include edge cases, error cases, and boundary conditions\n"
            "3. Use descriptive test names explaining what is being tested\n"
            "4. Follow AAA pattern (Arrange, Act, Assert)\n"
            "5. Include appropriate mocking where needed\n"
            "6. Generate complete, runnable test code\n"
            "<|end|>\n"
            "<|user|>\n"
            f"## Code to test:\n```{language}\n{code[:4000]}\n```\n\n"
        )
        if context:
            prompt += f"## Project context:\n```\n{context[:1500]}\n```\n\n"

        test_instruction = instruction or "Generate comprehensive unit tests"
        prompt += f"## Instructions: {test_instruction}\n## Framework: {framework}\n<|end|>\n<|assistant|>"

        response = await self.llm.generate(prompt)
        response = _strip_think(response)

        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        test_code = code_blocks[0].strip() if code_blocks else None

        return {
            "response": response,
            "test_code": test_code,
            "framework": framework,
            "language": language,
        }

    def _detect_language(self, code: str) -> str:
        indicators = {
            "python": ["def ", "import ", "from ", "class ", "self.", "print("],
            "javascript": ["const ", "let ", "var ", "function ", "=> ", "require("],
            "typescript": ["interface ", ": string", ": number", "type ", "export "],
            "java": ["public class", "private ", "System.out", "void "],
            "go": ["func ", "package ", "fmt.", "err != nil"],
            "rust": ["fn ", "let mut", "impl ", "pub fn"],
        }
        scores = {}
        code_lower = code.lower()
        for lang, keywords in indicators.items():
            scores[lang] = sum(1 for kw in keywords if kw.lower() in code_lower)
        if not scores or max(scores.values()) == 0:
            return "python"
        return max(scores, key=scores.get)

    def _suggest_framework(self, language: str) -> str:
        frameworks = {
            "python": "pytest",
            "javascript": "Jest",
            "typescript": "Jest",
            "java": "JUnit 5",
            "go": "testing",
            "rust": "#[test]",
        }
        return frameworks.get(language, "appropriate testing framework")