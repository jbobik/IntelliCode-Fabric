"""
Analyst Agent — analyzes code, answers questions, provides insights
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AnalystAgent:
    def __init__(self, llm):
        self.llm = llm

    async def analyze(self, question: str, context: str, history: list = None) -> dict:
        """Analyze codebase and answer questions"""
        prompt = self._build_prompt(question, context, history or [])
        response = await self.llm.generate(prompt)

        # Extract file references from response
        references = self._extract_references(response)

        return {
            "response": response,
            "references": references,
        }

    async def explain(self, code: str, question: str, context: str = "") -> dict:
        """Explain code in detail"""
        prompt = f"""<|system|>
You are an expert code analyst. Explain code clearly and thoroughly.
Include:
1. What the code does (high-level purpose)
2. How it works (step-by-step breakdown)
3. Key design decisions and patterns used
4. Potential issues or improvements
5. How it fits into the broader codebase
<|end|>
<|user|>
## Code to explain: {code}

## Additional context: {context[:2000]}

## Specific question: {question}
<|end|>
<|assistant|>"""

        response = await self.llm.generate(prompt)
        return {"response": response}

    def _build_prompt(self, question: str, context: str, history: list) -> str:
        system = """You are an expert code analyst. Your role is to:
1. Analyze codebases thoroughly
2. Answer questions about code structure, patterns, and implementation
3. Find specific implementations (authentication, database access, API endpoints, etc.)
4. Identify potential issues, code smells, and improvement opportunities
5. Reference specific files and line numbers

Always be specific and cite the exact files and code sections you're referring to."""

        parts = [f"<|system|>\n{system}\n<|end|>"]

        for h in history[-4:]:
            role = h.get("role", "user")
            parts.append(f"<|{role}|>\n{h['content']}\n<|end|>")

        user_msg = f"## Relevant Code:\n```\n{context[:3000]}\n```\n\n## Question: {question}"
        parts.append(f"<|user|>\n{user_msg}\n<|end|>")
        parts.append("<|assistant|>")

        return "\n".join(parts)

    def _extract_references(self, response: str) -> list[str]:
        """Extract file references from response text"""
        import re
        patterns = [
            r'`([^`]+\.\w{1,5})`',
            r'(?:file|File|in|In)\s+[`"]?(\S+\.\w{1,5})[`"]?',
        ]
        refs = set()
        for pattern in patterns:
            matches = re.findall(pattern, response)
            for m in matches:
                if '/' in m or '\\' in m or '.' in m:
                    refs.add(m)
        return list(refs)[:10]