"""
Refactor Agent — refactors code using patterns, best practices
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RefactorAgent:
    def __init__(self, llm):
        self.llm = llm

    async def refactor(
        self,
        code: str,
        instruction: str,
        context: str = "",
        pattern: Optional[str] = None,
    ) -> dict:
        """Refactor code based on instructions"""
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
                "clean": "Apply Clean Code principles: meaningful names, small functions, clear structure, no side effects.",
            }
            pattern_hint = pattern_descriptions.get(
                pattern.lower(),
                f"Apply the '{pattern}' pattern/principle."
            )

        prompt = f"""<|system|>
You are an expert software architect and refactoring specialist.
Your task is to refactor code following best practices.

Rules:
1. Preserve the original functionality exactly
2. Improve code quality, readability, and maintainability
3. Follow SOLID principles unless specifically asked otherwise
4. Add/improve documentation
5. Improve error handling
6. Make the code more testable

Output format:
1. First, explain what changes you'll make and why
2. Then provide the complete refactored code in a code block
3. Finally, list the key improvements made
<|end|>
<|user|>
## Code to refactor: {code[:4000]}

{f"## Project context:{chr(10)}```{chr(10)}{context[:2000]}{chr(10)}```{chr(10)}" if context else ""}

## Refactoring instruction: {instruction}
{f"{chr(10)}## Pattern to apply: {pattern_hint}" if pattern_hint else ""}
<|end|>
<|assistant|>"""

        response = await self.llm.generate(prompt)

        # Extract refactored code
        import re
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
        refactored_code = code_blocks[0].strip() if code_blocks else None

        return {
            "response": response,
            "refactored_code": refactored_code,
        }