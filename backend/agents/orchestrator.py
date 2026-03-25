"""
Multi-Agent Orchestrator — coordinates analyst, coder, refactor, tester agents
"""

import asyncio
import logging
import re
from typing import Optional

from .analyst import AnalystAgent
from .coder import CoderAgent
from .refactor import RefactorAgent
from .tester import TesterAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, llm, rag_engine, config: dict):
        self.llm = llm
        self.rag = rag_engine
        self.config = config

        self.analyst = AnalystAgent(llm)
        self.coder = CoderAgent(llm)
        self.refactor_agent = RefactorAgent(llm)
        self.tester = TesterAgent(llm)

    async def process_request(
        self,
        message: str,
        context_file: Optional[str] = None,
        selected_code: Optional[str] = None,
        conversation_history: list = None,
    ) -> dict:
        """
        Main entry point. Classify the request, route to appropriate agent(s).
        """
        if conversation_history is None:
            conversation_history = []

        # Step 1: Retrieve context from RAG
        context_chunks = await self.rag.retrieve(message, top_k=5)
        context_text = "\n\n".join([
            f"// File: {c['metadata']['file_path']} (lines {c['metadata'].get('line_start', '?')}-{c['metadata'].get('line_end', '?')})\n{c['content']}"
            for c in context_chunks
        ])

        # Additional file context
        if context_file:
            file_chunks = await self.rag.get_file_context(context_file)
            if file_chunks:
                file_text = "\n".join([c["content"] for c in file_chunks])
                context_text = f"// Current file: {context_file}\n{file_text}\n\n{context_text}"

        # Step 2: Classify intent
        intent = await self._classify_intent(message, selected_code)
        logger.info(f"Classified intent: {intent}")

        # Step 3: Route to agents
        if intent == "analyze":
            return await self._handle_analysis(message, context_text, conversation_history)
        elif intent == "generate":
            return await self._handle_generation(message, context_text, selected_code, conversation_history)
        elif intent == "refactor":
            return await self._handle_refactor(message, context_text, selected_code, conversation_history)
        elif intent == "test":
            return await self._handle_testing(message, context_text, selected_code, conversation_history)
        elif intent == "explain":
            return await self._handle_explanation(message, context_text, selected_code, conversation_history)
        else:
            return await self._handle_general(message, context_text, selected_code, conversation_history)

    async def _classify_intent(self, message: str, selected_code: Optional[str]) -> str:
        """Classify user intent without LLM (rule-based for speed)"""
        msg_lower = message.lower()

        # Refactoring patterns
        refactor_keywords = [
            "refactor", "рефактор", "rewrite", "перепиши", "паттерн", "pattern",
            "optimize", "оптимизир", "clean up", "restructure", "переструктур",
            "extract", "извлеки", "rename", "переименуй", "simplify", "упрости",
        ]
        if any(kw in msg_lower for kw in refactor_keywords):
            return "refactor"

        # Testing patterns
        test_keywords = [
            "test", "тест", "unit test", "юнит", "spec", "coverage",
            "покрытие", "mock", "мок", "assert", "pytest", "jest",
        ]
        if any(kw in msg_lower for kw in test_keywords):
            return "test"

        # Generation patterns
        generate_keywords = [
            "generate", "сгенерируй", "create", "создай", "implement", "реализуй",
            "write", "напиши", "add", "добавь", "build", "построй", "make", "сделай",
        ]
        if any(kw in msg_lower for kw in generate_keywords):
            return "generate"

        # Analysis/question patterns
        analysis_keywords = [
            "where", "где", "find", "найди", "how does", "как работает",
            "what is", "что такое", "explain", "объясни", "analyze", "анализ",
            "why", "почему", "describe", "опиши", "show", "покажи",
        ]
        if any(kw in msg_lower for kw in analysis_keywords):
            return "analyze"

        # Explanation of selected code
        if selected_code and len(message.split()) < 10:
            return "explain"

        return "general"

    async def _handle_analysis(self, message: str, context: str, history: list) -> dict:
        """Handle code analysis questions"""
        analysis = await self.analyst.analyze(message, context, history)
        return {
            "response": analysis["response"],
            "agent": "analyst",
            "intent": "analyze",
            "references": analysis.get("references", []),
        }

    async def _handle_generation(
        self, message: str, context: str, selected_code: Optional[str], history: list
    ) -> dict:
        """Handle code generation with analyst + coder pipeline"""
        # Analyst understands the requirements
        analysis = await self.analyst.analyze(
            f"Analyze this request for code generation: {message}",
            context,
            history,
        )

        # Coder generates the code
        generated = await self.coder.generate(
            message=message,
            context=context,
            selected_code=selected_code,
            analysis=analysis["response"],
        )

        return {
            "response": generated["response"],
            "code": generated.get("code"),
            "agent": "coder",
            "intent": "generate",
            "analysis_summary": analysis["response"][:200],
        }

    async def _handle_refactor(
        self, message: str, context: str, selected_code: Optional[str], history: list
    ) -> dict:
        """Handle refactoring requests"""
        code_to_refactor = selected_code or ""

        # If no selected code, try to find it from context
        if not code_to_refactor and context:
            code_to_refactor = context

        result = await self.refactor_agent.refactor(
            code=code_to_refactor,
            instruction=message,
            context=context,
        )

        return {
            "response": result["response"],
            "code": result.get("refactored_code"),
            "agent": "refactor",
            "intent": "refactor",
        }

    async def _handle_testing(
        self, message: str, context: str, selected_code: Optional[str], history: list
    ) -> dict:
        """Handle test generation"""
        code_to_test = selected_code or context

        result = await self.tester.generate_tests(
            code=code_to_test,
            instruction=message,
            context=context,
        )

        return {
            "response": result["response"],
            "code": result.get("test_code"),
            "agent": "tester",
            "intent": "test",
        }

    async def _handle_explanation(
        self, message: str, context: str, selected_code: Optional[str], history: list
    ) -> dict:
        """Handle code explanation"""
        result = await self.analyst.explain(
            code=selected_code or "",
            question=message,
            context=context,
        )

        return {
            "response": result["response"],
            "agent": "analyst",
            "intent": "explain",
        }

    async def _handle_general(
        self, message: str, context: str, selected_code: Optional[str], history: list
    ) -> dict:
        """Handle general questions"""
        prompt = self._build_general_prompt(message, context, selected_code, history)
        response = await self.llm.generate(prompt)

        return {
            "response": response,
            "agent": "general",
            "intent": "general",
        }

    async def refactor(
        self, code: str, file_path: str, instruction: str, pattern: Optional[str] = None
    ) -> dict:
        """Direct refactoring endpoint"""
        context_chunks = await self.rag.retrieve(instruction, top_k=3)
        context = "\n\n".join([c["content"] for c in context_chunks])

        result = await self.refactor_agent.refactor(
            code=code,
            instruction=instruction,
            context=context,
            pattern=pattern,
        )

        return {
            "response": result["response"],
            "refactored_code": result.get("refactored_code"),
            "file_path": file_path,
        }

    async def inline_edit(
        self,
        file_path: str,
        code: str,
        instruction: str,
        line_start: int,
        line_end: int,
        context: str = "",
    ) -> dict:
        """Generate inline edit"""
        result = await self.coder.inline_edit(
            code=code,
            instruction=instruction,
            line_start=line_start,
            line_end=line_end,
            context=context,
        )

        return {
            "original_code": code,
            "edited_code": result.get("code", code),
            "explanation": result.get("response", ""),
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
        }

    def _build_general_prompt(
        self, message: str, context: str, selected_code: Optional[str], history: list
    ) -> str:
        system = """You are an expert AI code assistant. Answer questions accurately using the provided code context. 
Be concise but thorough. Reference specific files and functions when relevant."""

        parts = [f"<|system|>\n{system}\n<|end|>"]

        for h in history[-4:]:
            role = h.get("role", "user")
            parts.append(f"<|{role}|>\n{h['content']}\n<|end|>")

        user_msg = ""
        if context:
            user_msg += f"## Code Context:\n```\n{context[:3000]}\n```\n\n"
        if selected_code:
            user_msg += f"## Selected Code:\n```\n{selected_code}\n```\n\n"
        user_msg += f"## Question:\n{message}"

        parts.append(f"<|user|>\n{user_msg}\n<|end|>")
        parts.append("<|assistant|>")

        return "\n".join(parts)