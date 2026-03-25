"""
Coder Agent — generates code, implements features, inline editing
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class CoderAgent:
    def __init__(self, llm):
        self.llm = llm

    async def generate(
        self,
        message: str,
        context: str,
        selected_code: Optional[str] = None,
        analysis: str = "",
    ) -> dict:
        """Generate code based on request"""
        prompt = f"""<|system|>
You are an expert code generator. Write clean, well-documented, production-ready code.
Rules:
1. Follow the coding style and conventions visible in the project context
2. Include proper error handling
3. Add meaningful comments and docstrings
4. Ensure type safety where applicable
5. Make code modular and testable
6. Output complete, working code

After the code block, briefly explain key decisions.
<|end|>
<|user|>
## Project Context: {context[:3000]}

{f"## Analysis of requirements:{chr(10)}{analysis[:1000]}{chr(10)}" if analysis else ""}
{f"## Existing code to extend/modify:{chr(10)}```{chr(10)}{selected_code}{chr(10)}```{chr(10)}" if selected_code else ""}

## Request: {message}
<|end|>
<|assistant|>"""

        response = await self.llm.generate(prompt)
        code = self._extract_code(response)

        return {
            "response": response,
            "code": code,
        }

    async def inline_edit(
        self,
        code: str,
        instruction: str,
        line_start: int,
        line_end: int,
        context: str = "",
    ) -> dict:
        """Generate inline code edits"""
        prompt = f"""<|system|>
You are a precise code editor. You will be given code and an edit instruction.
Output ONLY the modified code, nothing else. Preserve indentation and style.
<|end|>
<|user|>
## Code (lines {line_start}-{line_end}): {code}

{f"## Additional context:{chr(10)}```{chr(10)}{context[:1500]}{chr(10)}```{chr(10)}" if context else ""}

## Edit instruction: {instruction}

Output only the edited code:
<|end|>
<|assistant|>"""
        
        response = await self.llm.generate(prompt, max_new_tokens=1024)
        edited_code = self._extract_code(response) or response.strip()

        return {
            "code": edited_code,
            "response": f"Applied edit: {instruction}",
        }

def _extract_code(self, response: str) -> Optional[str]:
    """Extract code block from response"""
    # Match fenced code blocks
    pattern = r'```(?:\w+)?\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)
    if matches:
        return matches[0].strip()

    # If response looks like pure code
    lines = response.strip().split('\n')
    code_indicators = ['def ', 'class ', 'import ', 'from ', 'function ', 'const ', 'let ', 'var ', 'export ', '{', 'return ']
    if any(lines[0].strip().startswith(ind) for ind in code_indicators):
        return response.strip()

    return None