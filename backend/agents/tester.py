"""
Tester Agent — generates unit tests, integration tests
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class TesterAgent:
    def __init__(self, llm):
        self.llm = llm

    async def generate_tests(
        self,
        code: str,
        instruction: str = "",
        context: str = "",
    ) -> dict:
        """Generate tests for the given code"""
        # Detect language from code
        language = self._detect_language(code)
        framework = self._suggest_framework(language)

        prompt = f"""<|system|>
You are an expert test engineer. Generate comprehensive, well-structured tests.

Rules:
1. Cover all public functions/methods
2. Include edge cases, error cases, and boundary conditions
3. Use descriptive test names that explain what's being tested
4. Follow the AAA pattern (Arrange, Act, Assert)
5. Include appropriate mocking where needed
6. Add comments explaining test rationale for complex cases
7. Use {framework} framework conventions

Generate complete, runnable test code.
<|end|>
<|user|>
## Code to test:
```{language}
{code[:4000]}
{f"## Project context:{chr(10)}{chr(10)}{context[:1500]}{chr(10)}{chr(10)}" if context else ""}
Testing instructions: {instruction or "Generate comprehensive unit tests"}
Framework: {framework}
<|end|>
<|assistant|>"""
        
        response = await self.llm.generate(prompt)

        # Extract test code
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        test_code = code_blocks[0].strip() if code_blocks else None

        return {
            "response": response,
            "test_code": test_code,
            "framework": framework,
            "language": language,
        }

def _detect_language(self, code: str) -> str:
    """Detect programming language from code"""
    indicators = {
        "python": ["def ", "import ", "from ", "class ", "self.", "print(", "async def"],
        "javascript": ["const ", "let ", "var ", "function ", "=> ", "require(", "console.log"],
        "typescript": ["interface ", ": string", ": number", ": boolean", "type ", "export "],
        "java": ["public class", "private ", "System.out", "void ", "@Override"],
        "go": ["func ", "package ", "import (", "fmt.", "err != nil"],
        "rust": ["fn ", "let mut", "impl ", "pub fn", "use ", "::"],
    }

    code_lower = code.lower()
    scores = {}
    for lang, keywords in indicators.items():
        scores[lang] = sum(1 for kw in keywords if kw.lower() in code_lower)

    if not scores or max(scores.values()) == 0:
        return "python"

    return max(scores, key=scores.get)

def _suggest_framework(self, language: str) -> str:
    """Suggest testing framework based on language"""
    frameworks = {
        "python": "pytest",
        "javascript": "Jest",
        "typescript": "Jest with TypeScript",
        "java": "JUnit 5",
        "go": "testing package",
        "rust": "built-in #[test]",
    }
    return frameworks.get(language, "appropriate testing framework")