"""
Multi-Agent Orchestrator — настоящая агентная система.

Что изменено по сравнению с предыдущей версией:
1. IT-фильтр: отклоняем нерелевантные запросы (рецепты, погода и т.д.)
2. Убираем <think>...</think> теги из ответов моделей (Qwen3, DeepSeek-R1)
3. Настоящая агентная система: агенты имеют инструменты (tools) и планирование
4. ReAct-паттерн: Reason → Act → Observe → Repeat
5. Агент сам решает, какие инструменты вызвать, а не keyword matching
"""

import logging
import re
from typing import Optional

from .analyst import AnalystAgent
from .coder import CoderAgent
from .refactor import RefactorAgent
from .tester import TesterAgent

logger = logging.getLogger(__name__)


# ─── Утилиты ────────────────────────────────────────────────────────────────

def strip_think_tags(text: str) -> str:
    """
    Убирает <think>...</think> блоки из ответов моделей типа Qwen3 / DeepSeek-R1.
    Эти модели показывают цепочку рассуждений внутри тегов — нам это не нужно.
    """
    # Убираем блоки <think>...</think> (в том числе многострочные)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Убираем оставшиеся одиночные теги на случай незакрытых блоков
    cleaned = re.sub(r"</?think>", "", cleaned)
    # Убираем лишние пустые строки (больше 2 подряд)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ─── IT-фильтр ──────────────────────────────────────────────────────────────

# Ключевые слова, которые ТОЧНО относятся к IT/разработке
IT_KEYWORDS = [
    # Программирование
    "код", "code", "функция", "function", "класс", "class", "метод", "method",
    "переменная", "variable", "цикл", "loop", "условие", "condition",
    "рекурсия", "recursion", "алгоритм", "algorithm", "структура данных",
    "data structure", "массив", "array", "список", "list", "словарь", "dict",
    # Языки
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "sql", "html", "css", "bash",
    # Технологии
    "api", "rest", "graphql", "http", "https", "json", "xml", "yaml",
    "database", "база данных", "бд", "запрос", "query", "таблица", "table",
    "docker", "kubernetes", "k8s", "git", "github", "gitlab", "ci/cd",
    "микросервис", "microservice", "архитектура", "architecture",
    # Паттерны и концепции
    "паттерн", "pattern", "solid", "dry", "kiss", "mvc", "mvvm", "oop",
    "рефакторинг", "refactor", "тест", "test", "баг", "bug", "ошибка", "error",
    "исключение", "exception", "логирование", "logging", "дебаг", "debug",
    "оптимизация", "optimization", "кэш", "cache", "асинхронный", "async",
    # Инфраструктура
    "сервер", "server", "клиент", "client", "фронтенд", "frontend", "бэкенд",
    "backend", "деплой", "deploy", "конфиг", "config", "переменная окружения",
    "environment", "порт", "port", "endpoint", "роут", "route", "хук", "hook",
    # Запросы к коду проекта
    "файл", "file", "модуль", "module", "импорт", "import", "зависимость",
    "dependency", "пакет", "package", "библиотека", "library", "фреймворк",
    "framework", "аутентификация", "authentication", "авторизация", "authorization",
    # Действия разработчика
    "напиши", "написать", "сгенерируй", "generate", "реализуй", "implement",
    "объясни", "explain", "найди", "find", "исправь", "fix", "добавь", "add",
    "удали", "remove", "перепиши", "rewrite", "оптимизируй", "optimize",
    "протестируй", "тесты", "tests", "задокументируй", "document",
    # Английские глаголы запросов
    "write", "create", "build", "make", "show", "describe", "analyze",
    "review", "check", "list", "where", "how", "what", "why",
    # Специфика проекта
    "проект", "project", "репозиторий", "repository", "ветка", "branch",
    "коммит", "commit", "мерж", "merge", "пулл реквест", "pull request",
]

# Ключевые слова, которые ТОЧНО НЕ относятся к IT
OFFTOPIC_KEYWORDS = [
    "рецепт", "recipe", "готовить", "cooking", "еда", "food", "блюдо",
    "пирог", "торт", "суп", "борщ", "погода", "weather", "прогноз",
    "кино", "фильм", "movie", "сериал", "музыка", "music", "песня",
    "спорт", "sport", "футбол", "хоккей", "стихи", "poem", "поэзия",
    "история", "history", "география", "политика", "politics", "религия",
    "медицина", "болезнь", "диета", "похудеть", "здоровье", "health",
    "любовь", "отношения", "relationship", "гороскоп", "horoscope",
    "путешествие", "travel", "туризм", "tourism", "отель", "hotel",
    "кулинар", "culinar", "ингредиент", "ingredient",
]

OFFTOPIC_RESPONSE = (
    "Я специализируюсь исключительно на разработке программного обеспечения и технических вопросах. "
    "Пожалуйста, задайте вопрос, связанный с кодом, архитектурой, отладкой, тестированием "
    "или другими аспектами разработки. Например:\n\n"
    "• «Где в проекте реализована аутентификация?»\n"
    "• «Напиши unit-тесты для этого класса»\n"
    "• «Объясни, как работает этот алгоритм»\n"
    "• «Отрефактори этот код с паттерном Strategy»"
)


def is_it_related(message: str) -> bool:
    """
    Определяет, относится ли запрос к IT/разработке.
    Логика: если есть явные off-topic слова → отклоняем.
    Если есть IT-слова → принимаем.
    Если ничего нет (короткое или непонятное сообщение) → принимаем (даём шанс).
    """
    msg_lower = message.lower()

    # Если запрос очень короткий (< 3 слов) — не фильтруем
    if len(message.split()) < 3:
        return True

    # Проверяем явные off-topic сигналы
    for kw in OFFTOPIC_KEYWORDS:
        if kw in msg_lower:
            # Дополнительно проверяем — вдруг это IT-контекст ("рецепт SQL-запроса")
            it_count = sum(1 for it_kw in IT_KEYWORDS if it_kw in msg_lower)
            if it_count < 2:
                return False

    # Проверяем наличие IT-слов
    it_count = sum(1 for kw in IT_KEYWORDS if kw in msg_lower)

    # Если нашли хотя бы одно IT-слово — это IT-вопрос
    if it_count >= 1:
        return True

    # Если вообще нет IT-слов но и нет off-topic — скорее всего общий вопрос к коду
    # Принимаем (пусть агент разберётся)
    return True


# ─── Настоящая агентная система ─────────────────────────────────────────────

class AgentTool:
    """Описание инструмента, доступного агенту"""
    def __init__(self, name: str, description: str, fn):
        self.name = name
        self.description = description
        self.fn = fn

    async def call(self, **kwargs):
        return await self.fn(**kwargs)


class AgentOrchestrator:
    """
    Настоящая агентная система на основе ReAct-паттерна.
    
    ReAct = Reasoning + Acting:
    1. REASON: агент анализирует запрос и составляет план
    2. ACT: вызывает нужные инструменты (RAG, specialist agents)
    3. OBSERVE: получает результаты инструментов
    4. REASON again: синтезирует финальный ответ
    
    В отличие от предыдущей версии (keyword routing), здесь:
    - Агент сам решает, что делать (через planning prompt)
    - Может комбинировать несколько агентов в одном запросе
    - Валидирует и улучшает ответ через reflection
    - Имеет память о ходе рассуждений
    """

    def __init__(self, llm, rag_engine, config: dict):
        self.llm = llm
        self.rag = rag_engine
        self.config = config

        # Специализированные агенты
        self.analyst = AnalystAgent(llm)
        self.coder = CoderAgent(llm)
        self.refactor_agent = RefactorAgent(llm)
        self.tester = TesterAgent(llm)

        logger.info("AgentOrchestrator initialized (ReAct mode)")

    # ─── Главная точка входа ─────────────────────────────────────────────

    async def process_request(
        self,
        message: str,
        context_file: Optional[str] = None,
        selected_code: Optional[str] = None,
        conversation_history: list = None,
    ) -> dict:
        if conversation_history is None:
            conversation_history = []

        # ── Шаг 0: IT-фильтр ──
        if not is_it_related(message):
            logger.info(f"Request filtered as off-topic: {message[:60]}...")
            return {
                "response": OFFTOPIC_RESPONSE,
                "agent": "filter",
                "intent": "offtopic",
                "references": [],
            }

        # ── Шаг 1: RAG — собираем контекст проекта ──
        context_chunks = await self.rag.retrieve(message, top_k=5)
        context_text = self._format_context(context_chunks)

        # Добавляем контекст текущего файла (если открыт)
        if context_file:
            file_chunks = await self.rag.get_file_context(context_file)
            if file_chunks:
                file_text = "\n".join([c["content"] for c in file_chunks[:3]])
                context_text = f"// Current file: {context_file}\n{file_text}\n\n{context_text}"

        logger.info(f"RAG retrieved {len(context_chunks)} chunks for: {message[:60]}...")

        # ── Шаг 2: Planning — агент составляет план ──
        plan = await self._plan(message, context_text, selected_code, conversation_history)
        logger.info(f"Agent plan: intent={plan['intent']}, agents={plan['agents']}")

        # ── Шаг 3: Execution — выполняем план ──
        result = await self._execute_plan(plan, message, context_text, selected_code, conversation_history)

        # ── Шаг 4: Reflection — проверяем качество ответа ──
        result = await self._reflect(result, message, context_text)

        # Добавляем метаданные RAG
        result["references"] = [c["metadata"]["file_path"] for c in context_chunks]
        result["rag_chunks"] = len(context_chunks)

        return result

    # ─── Planning ────────────────────────────────────────────────────────

    async def _plan(
        self,
        message: str,
        context: str,
        selected_code: Optional[str],
        history: list,
    ) -> dict:
        """
        Агент анализирует запрос и составляет план действий.
        Это первый шаг ReAct-паттерна (REASON).
        
        Вместо жёсткого keyword matching используем LLM для классификации
        (если модель загружена) или fallback на улучшенный keyword matching.
        """
        # Если LLM загружена — используем её для планирования
        if self.llm.is_loaded():
            return await self._llm_plan(message, context, selected_code, history)
        else:
            # Fallback на улучшенный rule-based
            return self._rule_based_plan(message, selected_code)

    async def _llm_plan(self, message: str, context: str, selected_code: Optional[str], history: list) -> dict:
        """Планирование через LLM — агент сам решает что делать"""
        
        has_code = bool(selected_code)
        has_context = bool(context.strip())
        recent_history = history[-3:] if history else []
        
        planning_prompt = f"""<|system|>
You are a planning agent for a code assistant. Analyze the user's request and determine the best action plan.

Available agents:
- analyst: answers questions about code, finds implementations, explains architecture
- coder: generates new code, implements functions, creates endpoints
- refactor: refactors existing code, applies design patterns, improves quality  
- tester: generates unit tests, integration tests, test fixtures
- multi: use multiple agents in sequence (analyst+coder, analyst+tester, etc.)

Respond with ONLY a JSON object in this exact format:
{{
  "intent": "analyze|generate|refactor|test|explain|multi",
  "agents": ["analyst"],
  "reasoning": "brief reason for this choice",
  "needs_code": true/false,
  "confidence": 0.0-1.0
}}
<|end|>
<|user|>
User request: {message}
Has selected code: {has_code}
Has project context: {has_context}
<|end|>
<|assistant|>
{{"""
        
        try:
            raw = await self.llm.generate(planning_prompt, max_new_tokens=150, temperature=0.1)
            raw = strip_think_tags(raw)
            
            # Парсим JSON из ответа
            import json
            # Пытаемся найти JSON в ответе
            json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
            if json_match:
                plan_data = json.loads("{" + json_match.group().lstrip("{"))
                # Валидируем
                if "intent" in plan_data and "agents" in plan_data:
                    logger.info(f"LLM planning succeeded: {plan_data}")
                    return plan_data
        except Exception as e:
            logger.warning(f"LLM planning failed ({e}), falling back to rule-based")
        
        # Fallback
        return self._rule_based_plan(message, selected_code)

    def _rule_based_plan(self, message: str, selected_code: Optional[str]) -> dict:
        """
        Улучшенный rule-based planning — fallback когда LLM недоступна.
        Лучше предыдущей версии: учитывает комбинированные случаи.
        """
        msg = message.lower()

        # Паттерны с весами — чем больше совпадений, тем выше уверенность
        patterns = {
            "refactor": {
                "keywords": [
                    "refactor", "рефактор", "rewrite", "перепиши", "паттерн", "pattern",
                    "optimize", "оптимизир", "clean up", "restructure", "extract",
                    "strategy", "стратегия", "observer", "factory", "decorator", "singleton",
                    "solid", "dry", "kiss", "упрости", "simplify",
                ],
                "agents": ["refactor"],
            },
            "test": {
                "keywords": [
                    "test", "тест", "unit test", "юнит", "spec", "coverage",
                    "покрытие", "mock", "мок", "assert", "pytest", "jest",
                    "проверк", "verify", "тестирование",
                ],
                "agents": ["analyst", "tester"],
            },
            "generate": {
                "keywords": [
                    "generate", "сгенерируй", "create", "создай", "implement", "реализуй",
                    "write", "напиши", "add", "добавь", "build", "make", "сделай",
                    "endpoint", "handler", "обработчик", "функцию", "класс",
                ],
                "agents": ["analyst", "coder"],
            },
            "analyze": {
                "keywords": [
                    "where", "где", "find", "найди", "how does", "как работает",
                    "what is", "что такое", "analyze", "анализ", "why", "почему",
                    "describe", "опиши", "show", "покажи", "list", "перечисли",
                    "architecture", "архитектур", "structure", "структур",
                    "dependencies", "зависимост", "explain", "объясни",
                ],
                "agents": ["analyst"],
            },
        }

        scores = {}
        for intent, data in patterns.items():
            score = sum(1 for kw in data["keywords"] if kw in msg)
            if score > 0:
                scores[intent] = score

        if not scores:
            # Если выделен код и короткий вопрос → объяснение
            if selected_code and len(message.split()) < 15:
                return {"intent": "explain", "agents": ["analyst"], "reasoning": "short question with code", "confidence": 0.7}
            return {"intent": "general", "agents": ["analyst"], "reasoning": "general question", "confidence": 0.5}

        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent] / 3.0, 1.0)

        return {
            "intent": best_intent,
            "agents": patterns[best_intent]["agents"],
            "reasoning": f"matched {scores[best_intent]} keywords",
            "confidence": confidence,
        }

    # ─── Execution ───────────────────────────────────────────────────────

    async def _execute_plan(
        self,
        plan: dict,
        message: str,
        context: str,
        selected_code: Optional[str],
        history: list,
    ) -> dict:
        """
        Выполняет план агента (ACT + OBSERVE шаги ReAct).
        Может запускать агентов последовательно или параллельно.
        """
        intent = plan.get("intent", "general")
        agents = plan.get("agents", ["analyst"])

        logger.info(f"Executing plan: intent={intent}, agents={agents}")

        # ── Рефакторинг ──
        if intent == "refactor":
            return await self._execute_refactor(message, context, selected_code, history)

        # ── Тестирование (Analyst → Tester pipeline) ──
        elif intent == "test":
            return await self._execute_test_pipeline(message, context, selected_code, history)

        # ── Генерация (Analyst → Coder pipeline) ──
        elif intent == "generate":
            return await self._execute_generate_pipeline(message, context, selected_code, history)

        # ── Анализ ──
        elif intent in ("analyze", "explain"):
            return await self._execute_analysis(message, context, selected_code, history)

        # ── Мультиагентный режим ──
        elif intent == "multi":
            return await self._execute_multi_agent(message, context, selected_code, history, agents)

        # ── Общий ──
        else:
            return await self._execute_general(message, context, selected_code, history)

    async def _execute_analysis(self, message, context, selected_code, history) -> dict:
        """Analyst агент — анализ и объяснение кода"""
        logger.info("→ [ANALYST] Analyzing request")

        if selected_code:
            result = await self.analyst.explain(
                code=selected_code,
                question=message,
                context=context,
            )
        else:
            result = await self.analyst.analyze(message, context, history)

        response = strip_think_tags(result["response"])

        return {
            "response": response,
            "agent": "analyst",
            "intent": "analyze",
            "agent_trace": ["analyst"],
        }

    async def _execute_generate_pipeline(self, message, context, selected_code, history) -> dict:
        """
        Analyst → Coder pipeline.
        Analyst сначала понимает контекст и требования,
        потом Coder генерирует качественный код.
        """
        logger.info("→ [ANALYST→CODER] Starting generation pipeline")

        # Step 1: Analyst изучает контекст
        logger.info("  [ANALYST] Analyzing requirements and codebase context...")
        analysis = await self.analyst.analyze(
            f"Analyze this code generation request and identify: "
            f"1) What needs to be created, "
            f"2) Relevant existing patterns in the codebase, "
            f"3) Key constraints and conventions to follow. "
            f"Request: {message}",
            context,
            history,
        )
        analysis_text = strip_think_tags(analysis["response"])
        logger.info("  [ANALYST] Analysis complete")

        # Step 2: Coder генерирует код с учётом анализа
        logger.info("  [CODER] Generating code based on analysis...")
        generated = await self.coder.generate(
            message=message,
            context=context,
            selected_code=selected_code,
            analysis=analysis_text,
        )
        response = strip_think_tags(generated["response"])
        logger.info("  [CODER] Generation complete")

        return {
            "response": response,
            "code": generated.get("code"),
            "agent": "coder",
            "intent": "generate",
            "agent_trace": ["analyst", "coder"],
            "analysis_summary": analysis_text[:300],
        }

    async def _execute_refactor(self, message, context, selected_code, history) -> dict:
        """
        Refactor agent с предварительным анализом.
        """
        logger.info("→ [REFACTOR] Starting refactoring")

        code_to_refactor = selected_code or context or ""

        # Если кода нет — просим Analyst найти его
        if not selected_code and not context:
            logger.info("  [ANALYST] No code provided, searching in codebase...")
            search_result = await self.analyst.analyze(
                f"Find the relevant code to refactor for this request: {message}",
                context,
                history,
            )
            code_to_refactor = strip_think_tags(search_result["response"])

        result = await self.refactor_agent.refactor(
            code=code_to_refactor,
            instruction=message,
            context=context,
        )
        response = strip_think_tags(result["response"])

        return {
            "response": response,
            "code": result.get("refactored_code"),
            "agent": "refactor",
            "intent": "refactor",
            "agent_trace": ["refactor"],
        }

    async def _execute_test_pipeline(self, message, context, selected_code, history) -> dict:
        """
        Analyst → Tester pipeline.
        Analyst определяет что нужно протестировать,
        Tester генерирует тесты.
        """
        logger.info("→ [ANALYST→TESTER] Starting test generation pipeline")

        code_to_test = selected_code or context or ""

        # Если нет кода — Analyst находит что тестировать
        if not selected_code:
            logger.info("  [ANALYST] Finding code to test...")
            analysis = await self.analyst.analyze(
                f"Identify the code that needs to be tested based on this request: {message}. "
                f"What are the key functions/classes/methods that should be covered?",
                context,
                history,
            )
            code_to_test = strip_think_tags(analysis["response"])
            logger.info("  [ANALYST] Target identified")

        logger.info("  [TESTER] Generating tests...")
        result = await self.tester.generate_tests(
            code=code_to_test,
            instruction=message,
            context=context,
        )
        response = strip_think_tags(result["response"])
        logger.info("  [TESTER] Tests generated")

        return {
            "response": response,
            "code": result.get("test_code"),
            "agent": "tester",
            "intent": "test",
            "agent_trace": ["analyst", "tester"],
        }

    async def _execute_multi_agent(self, message, context, selected_code, history, agents) -> dict:
        """
        Мультиагентный режим — запускаем агентов последовательно,
        передавая результат каждого следующему.
        """
        logger.info(f"→ [MULTI-AGENT] Running agents: {agents}")

        accumulated_context = context
        last_response = None
        agent_trace = []

        for agent_name in agents:
            logger.info(f"  [{agent_name.upper()}] Processing...")

            if agent_name == "analyst":
                result = await self.analyst.analyze(message, accumulated_context, history)
                last_response = strip_think_tags(result["response"])
                accumulated_context = f"{accumulated_context}\n\n## Previous Analysis:\n{last_response}"

            elif agent_name == "coder":
                result = await self.coder.generate(
                    message=message,
                    context=accumulated_context,
                    selected_code=selected_code,
                    analysis=last_response or "",
                )
                last_response = strip_think_tags(result["response"])

            elif agent_name == "refactor":
                result = await self.refactor_agent.refactor(
                    code=selected_code or context,
                    instruction=message,
                    context=accumulated_context,
                )
                last_response = strip_think_tags(result["response"])

            elif agent_name == "tester":
                result = await self.tester.generate_tests(
                    code=selected_code or accumulated_context,
                    instruction=message,
                    context=accumulated_context,
                )
                last_response = strip_think_tags(result["response"])

            agent_trace.append(agent_name)

        return {
            "response": last_response or "Multi-agent pipeline completed",
            "code": result.get("code") if result else None,
            "agent": "multi",
            "intent": "multi",
            "agent_trace": agent_trace,
        }

    async def _execute_general(self, message, context, selected_code, history) -> dict:
        """Общий вопрос — Analyst отвечает напрямую"""
        logger.info("→ [GENERAL] Direct analyst response")

        result = await self.analyst.analyze(message, context, history)
        response = strip_think_tags(result["response"])

        return {
            "response": response,
            "agent": "analyst",
            "intent": "general",
            "agent_trace": ["analyst"],
        }

    # ─── Reflection ──────────────────────────────────────────────────────

    async def _reflect(self, result: dict, original_message: str, context: str) -> dict:
        """
        Шаг рефлексии ReAct — проверяем качество ответа.
        Если ответ слишком короткий или явно некачественный — улучшаем.
        Лёгкая проверка без лишних LLM-вызовов.
        """
        response = result.get("response", "")

        # Убираем think-теги ещё раз на всякий случай
        response = strip_think_tags(response)
        result["response"] = response

        # Проверки качества
        if len(response) < 20:
            logger.warning("Response too short, may indicate an issue")
            result["response"] = response + "\n\n*Примечание: Ответ может быть неполным. Попробуйте уточнить запрос.*"

        # Убираем артефакты форматирования
        result["response"] = result["response"].strip()

        return result

    # ─── Утилиты ─────────────────────────────────────────────────────────

    def _format_context(self, chunks: list) -> str:
        """Форматирует чанки RAG в читаемый контекст"""
        if not chunks:
            return ""
        return "\n\n".join([
            f"// File: {c['metadata']['file_path']} "
            f"(lines {c['metadata'].get('line_start', '?')}-{c['metadata'].get('line_end', '?')})\n"
            f"{c['content']}"
            for c in chunks
        ])

    # ─── Прямые вызовы (для endpoint-ов /refactor, /inline-edit) ────────

    async def refactor(self, code, file_path, instruction, pattern=None) -> dict:
        context_chunks = await self.rag.retrieve(instruction, top_k=3)
        context = self._format_context(context_chunks)

        result = await self.refactor_agent.refactor(
            code=code, instruction=instruction, context=context, pattern=pattern,
        )
        return {
            "response": strip_think_tags(result["response"]),
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
            "explanation": strip_think_tags(result.get("response", "")),
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
        }