"""
Multi-Agent Orchestrator — coordinates analyst, coder, refactor, tester agents.

Поток:
1. Получает запрос пользователя
2. Извлекает контекст из RAG
3. Классифицирует intent (rule-based, быстро)
4. Маршрутизирует к нужному агенту (или цепочке агентов)
5. Возвращает ответ с пометкой какой агент отвечал
"""

import logging
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

        # Создаём 4 специализированных агента
        self.analyst = AnalystAgent(llm)
        self.coder = CoderAgent(llm)
        self.refactor_agent = RefactorAgent(llm)
        self.tester = TesterAgent(llm)

        logger.info("AgentOrchestrator initialized with 4 agents: analyst, coder, refactor, tester")

    async def process_request(
        self,
        message: str,
        context_file: Optional[str] = None,
        selected_code: Optional[str] = None,
        conversation_history: list = None,
    ) -> dict:
        """
        Главная точка входа. Классифицирует запрос и направляет нужному агенту.
        """
        if conversation_history is None:
            conversation_history = []

        # ── Шаг 1: Извлекаем контекст из RAG ──
        context_chunks = await self.rag.retrieve(message, top_k=5)
        context_text = "\n\n".join([
            f"// File: {c['metadata']['file_path']} "
            f"(lines {c['metadata'].get('line_start', '?')}-{c['metadata'].get('line_end', '?')})\n"
            f"{c['content']}"
            for c in context_chunks
        ])

        # Дополнительный контекст текущего файла
        if context_file:
            file_chunks = await self.rag.get_file_context(context_file)
            if file_chunks:
                file_text = "\n".join([c["content"] for c in file_chunks[:3]])
                context_text = f"// Current file: {context_file}\n{file_text}\n\n{context_text}"

        # ── Шаг 2: Классифицируем intent ──
        intent = self._classify_intent(message, selected_code)
        logger.info(f"Request classified as: {intent}")
        logger.info(f"  RAG found {len(context_chunks)} relevant chunks")

        # ── Шаг 3: Маршрутизируем к агенту ──
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

    def _classify_intent(self, message: str, selected_code: Optional[str]) -> str:
        """
        Rule-based классификация (быстро, без вызова LLM).
        Поддерживает русский и английский.
        """
        msg = message.lower()

        # ── Рефакторинг ──
        refactor_kw = [
            "refactor", "рефактор", "rewrite", "перепиши", "паттерн", "pattern",
            "optimize", "оптимизир", "clean up", "restructure", "переструктур",
            "extract", "извлеки", "rename", "переименуй", "simplify", "упрости",
            "strategy", "стратегия", "observer", "наблюдатель", "factory", "фабрик",
            "decorator", "декоратор", "singleton", "solid",
        ]
        if any(kw in msg for kw in refactor_kw):
            return "refactor"

        # ── Тестирование ──
        test_kw = [
            "test", "тест", "unit test", "юнит", "spec", "coverage",
            "покрытие", "mock", "мок", "assert", "pytest", "jest",
            "проверк", "verify",
        ]
        if any(kw in msg for kw in test_kw):
            return "test"

        # ── Генерация кода ──
        generate_kw = [
            "generate", "сгенерируй", "create", "создай", "implement", "реализуй",
            "write", "напиши", "add", "добавь", "build", "построй", "make", "сделай",
            "new function", "новую функцию", "new class", "новый класс",
            "endpoint", "api", "handler", "обработчик",
        ]
        if any(kw in msg for kw in generate_kw):
            return "generate"

        # ── Анализ / Поиск ──
        analysis_kw = [
            "where", "где", "find", "найди", "how does", "как работает",
            "what is", "что такое", "analyze", "анализ", "анализируй",
            "why", "почему", "describe", "опиши", "show", "покажи",
            "how many", "сколько", "list all", "перечисли",
            "architecture", "архитектур", "structure", "структур",
            "dependencies", "зависимост",
        ]
        if any(kw in msg for kw in analysis_kw):
            return "analyze"

        # ── Объяснение (если выделен код и короткий вопрос) ──
        explain_kw = ["explain", "объясни", "what does", "что делает", "расскажи"]
        if any(kw in msg for kw in explain_kw):
            return "explain"

        if selected_code and len(message.split()) < 10:
            return "explain"

        return "general"

    # ─── Обработчики для каждого intent ───

    async def _handle_analysis(self, message, context, history) -> dict:
        """Analyst agent отвечает на вопросы о коде"""
        logger.info("→ Routing to ANALYST agent")
        analysis = await self.analyst.analyze(message, context, history)
        return {
            "response": analysis["response"],
            "agent": "analyst",
            "intent": "analyze",
            "references": analysis.get("references", []),
        }

    async def _handle_generation(self, message, context, selected_code, history) -> dict:
        """
        Pipeline: Analyst → Coder
        Analyst сначала анализирует требования, потом Coder генерирует.
        """
        logger.info("→ Routing to ANALYST + CODER pipeline")

        # Шаг 1: Analyst понимает что нужно
        analysis = await self.analyst.analyze(
            f"Analyze this request for code generation: {message}",
            context,
            history,
        )
        logger.info("  Analyst analysis complete")

        # Шаг 2: Coder генерирует код
        generated = await self.coder.generate(
            message=message,
            context=context,
            selected_code=selected_code,
            analysis=analysis["response"],
        )
        logger.info("  Coder generation complete")

        return {
            "response": generated["response"],
            "code": generated.get("code"),
            "agent": "coder",
            "intent": "generate",
            "analysis_summary": analysis["response"][:200],
        }

    async def _handle_refactor(self, message, context, selected_code, history) -> dict:
        """Refactor agent рефакторит код"""
        logger.info("→ Routing to REFACTOR agent")
        code_to_refactor = selected_code or context or ""

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

    async def _handle_testing(self, message, context, selected_code, history) -> dict:
        """
        Pipeline: Analyst → Tester
        """
        logger.info("→ Routing to ANALYST + TESTER pipeline")

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

    async def _handle_explanation(self, message, context, selected_code, history) -> dict:
        """Analyst объясняет код"""
        logger.info("→ Routing to ANALYST agent (explain)")
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

    async def _handle_general(self, message, context, selected_code, history) -> dict:
        """Общий вопрос — прямой вызов LLM"""
        logger.info("→ Routing to GENERAL (direct LLM)")
        prompt = self._build_general_prompt(message, context, selected_code, history)
        response = await self.llm.generate(prompt)

        return {
            "response": response,
            "agent": "general",
            "intent": "general",
        }

    # ─── Прямые вызовы (для endpoint-ов refactor, inline-edit) ───

    async def refactor(self, code, file_path, instruction, pattern=None) -> dict:
        context_chunks = await self.rag.retrieve(instruction, top_k=3)
        context = "\n\n".join([c["content"] for c in context_chunks])

        result = await self.refactor_agent.refactor(
            code=code, instruction=instruction, context=context, pattern=pattern,
        )
        return {
            "response": result["response"],
            "refactored_code": result.get("refactored_code"),
            "file_path": file_path,
        }

    async def inline_edit(self, file_path, code, instruction, line_start, line_end, context="") -> dict:
        result = await self.coder.inline_edit(
            code=code, instruction=instruction,
            line_start=line_start, line_end=line_end, context=context,
        )
        return {
            "original_code": code,
            "edited_code": result.get("code", code),
            "explanation": result.get("response", ""),
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
        }

    def _build_general_prompt(self, message, context, selected_code, history) -> str:
        system = (
            "You are an expert AI code assistant. Answer questions accurately "
            "using the provided code context. Be concise but thorough. "
            "Reference specific files and functions when relevant."
        )

        parts = [f"<|system|>\n{system}\n<|end|>"]
        for h in (history or [])[-4:]:
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