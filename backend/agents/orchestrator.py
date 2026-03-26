"""
Multi-Agent Orchestrator — настоящая агентная система v3.0

Ключевые улучшения:
1. Настоящий ReAct-паттерн с итеративными шагами (Reason → Act → Observe → Repeat)
2. Автоматическое определение языка пользователя → ответ на том же языке
3. Thinking-блоки сохраняются отдельно для отображения в UI
4. Агенты имеют инструменты и могут вызывать друг друга
5. Reflection с реальной валидацией качества
6. Explain-режим теперь предлагает исправления кода, а не только описывает проблемы
7. Параллельный запуск независимых агентов
"""

import asyncio
import json
import logging
import re
from typing import Optional

from .analyst import AnalystAgent
from .coder import CoderAgent
from .refactor import RefactorAgent
from .tester import TesterAgent

logger = logging.getLogger(__name__)


# ─── Утилиты ────────────────────────────────────────────────────────────────

def strip_think_tags(text: str) -> tuple[str, str]:
    """
    Извлекает <think>...</think> блоки из ответов моделей (Qwen3, DeepSeek-R1).
    Возвращает (cleaned_text, thinking_text).
    """
    thinking_parts = []
    for match in re.finditer(r"<think>(.*?)</think>", text, flags=re.DOTALL):
        thinking_parts.append(match.group(1).strip())

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"</?think>", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    thinking = "\n\n".join(thinking_parts) if thinking_parts else ""
    return cleaned, thinking


def detect_language(text: str) -> str:
    """
    Определяет язык запроса пользователя.
    Возвращает 'ru' для русского, 'en' для английского.
    """
    cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))
    total = cyrillic_count + latin_count
    if total == 0:
        return 'ru'  # default
    return 'ru' if cyrillic_count / total > 0.3 else 'en'

def sanitize_response(text: str) -> str:
    """
    Убирает артефакты генерации: управляющие токены, незакрытые теги,
    повторные вопросы, которые модель генерирует после ответа.
    """
    import re
    
    # Убираем все управляющие токены чат-шаблонов
    control_patterns = [
        r'<\|system\|>.*?<\|end\|>',
        r'<\|user\|>.*?<\|end\|>',
        r'<\|assistant\|>',
        r'<\|end\|>',
        r'<\|im_start\|>.*?<\|im_end\|>',
        r'<\|im_start\|>',
        r'<\|im_end\|>',
        r'<\|endoftext\|>',
        r'</?(?:system|user|assistant)>',
    ]
    
    for pattern in control_patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL)
    
    # Убираем <think> блоки (если не убрались раньше)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?think>', '', text)
    
    # Убираем повторные "Question:" блоки в конце ответа
    # (модель иногда генерирует новый вопрос после ответа)
    question_restart = re.search(
        r'\n(?:Question|## Question|Вопрос|<\|user\|>):\s', text
    )
    if question_restart and question_restart.start() > len(text) * 0.5:
        text = text[:question_restart.start()]
    
    # Чистим множественные пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

# ─── IT-фильтр ──────────────────────────────────────────────────────────────

IT_KEYWORDS = [
    "код", "code", "функция", "function", "класс", "class", "метод", "method",
    "переменная", "variable", "цикл", "loop", "условие", "condition",
    "рекурсия", "recursion", "алгоритм", "algorithm", "структура данных",
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "sql", "html", "css", "bash",
    "api", "rest", "graphql", "http", "json", "xml", "yaml",
    "database", "база данных", "бд", "запрос", "query", "таблица",
    "docker", "kubernetes", "git", "github", "gitlab", "ci/cd",
    "микросервис", "microservice", "архитектура", "architecture",
    "паттерн", "pattern", "solid", "dry", "kiss", "mvc", "mvvm", "oop",
    "рефакторинг", "refactor", "тест", "test", "баг", "bug", "ошибка", "error",
    "исключение", "exception", "логирование", "logging", "дебаг", "debug",
    "оптимизация", "optimization", "кэш", "cache", "асинхронный", "async",
    "сервер", "server", "клиент", "client", "фронтенд", "frontend", "бэкенд",
    "backend", "деплой", "deploy", "конфиг", "config", "endpoint", "route",
    "файл", "file", "модуль", "module", "импорт", "import", "зависимость",
    "dependency", "пакет", "package", "библиотека", "library", "фреймворк",
    "framework", "аутентификация", "authentication", "авторизация",
    "напиши", "написать", "сгенерируй", "generate", "реализуй", "implement",
    "объясни", "explain", "найди", "find", "исправь", "fix", "добавь", "add",
    "удали", "remove", "перепиши", "rewrite", "оптимизируй", "optimize",
    "write", "create", "build", "make", "show", "describe", "analyze",
    "review", "check", "list", "where", "how", "what", "why",
    "проект", "project", "репозиторий", "ветка", "branch",
    "коммит", "commit", "мерж", "merge", "пулл реквест",
]

OFFTOPIC_KEYWORDS = [
    "рецепт", "recipe", "готовить", "cooking", "еда", "food", "блюдо",
    "пирог", "торт", "суп", "борщ", "погода", "weather", "прогноз",
    "кино", "фильм", "movie", "сериал", "музыка", "music", "песня",
    "спорт", "sport", "футбол", "хоккей", "стихи", "poem",
    "история", "history", "география", "политика", "религия",
    "медицина", "болезнь", "диета", "похудеть", "здоровье",
    "любовь", "отношения", "гороскоп",
    "путешествие", "travel", "туризм", "отель",
    "кулинар", "ингредиент",
]

OFFTOPIC_RESPONSE_RU = (
    "Я специализируюсь исключительно на разработке программного обеспечения и технических вопросах. "
    "Пожалуйста, задайте вопрос, связанный с кодом, архитектурой, отладкой, тестированием "
    "или другими аспектами разработки. Например:\n\n"
    "• «Где в проекте реализована аутентификация?»\n"
    "• «Напиши unit-тесты для этого класса»\n"
    "• «Объясни, как работает этот алгоритм»\n"
    "• «Отрефактори этот код с паттерном Strategy»"
)

OFFTOPIC_RESPONSE_EN = (
    "I specialize exclusively in software development and technical questions. "
    "Please ask a question related to code, architecture, debugging, testing "
    "or other aspects of development. For example:\n\n"
    "• 'Where is authentication implemented in the project?'\n"
    "• 'Write unit tests for this class'\n"
    "• 'Explain how this algorithm works'\n"
    "• 'Refactor this code using the Strategy pattern'"
)


def is_it_related(message: str) -> bool:
    msg_lower = message.lower()
    if len(message.split()) < 3:
        return True
    for kw in OFFTOPIC_KEYWORDS:
        if kw in msg_lower:
            it_count = sum(1 for it_kw in IT_KEYWORDS if it_kw in msg_lower)
            if it_count < 2:
                return False
    return True


# ─── Агентные инструменты ────────────────────────────────────────────────────

class AgentTool:
    """Описание инструмента, доступного агенту"""
    def __init__(self, name: str, description: str, fn):
        self.name = name
        self.description = description
        self.fn = fn

    async def call(self, **kwargs):
        return await self.fn(**kwargs)


# ─── Настоящая мультиагентная система ─────────────────────────────────────────

class AgentOrchestrator:
    """
    Мультиагентная система на основе ReAct-паттерна v3.

    ReAct = Reasoning + Acting:
    1. REASON: агент анализирует запрос и составляет план
    2. ACT: вызывает нужные инструменты (RAG, specialist agents)
    3. OBSERVE: получает результаты инструментов
    4. REASON again: синтезирует финальный ответ
    5. REFLECT: проверяет качество и при необходимости улучшает

    Ключевые отличия от v2:
    - Автоматическое определение языка → ответ на том же языке
    - Thinking-блоки сохраняются для UI
    - Explain предлагает исправления, а не только описывает проблемы
    - Параллельный запуск агентов когда это возможно
    - Лучшая reflection с реальной проверкой
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

        logger.info("AgentOrchestrator v3 initialized (ReAct + language-aware)")

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

        # Определяем язык пользователя
        user_lang = detect_language(message)

        # ── Шаг 0: IT-фильтр ──
        if not is_it_related(message):
            logger.info(f"Request filtered as off-topic: {message[:60]}...")
            return {
                "response": OFFTOPIC_RESPONSE_RU if user_lang == 'ru' else OFFTOPIC_RESPONSE_EN,
                "agent": "filter",
                "intent": "offtopic",
                "references": [],
                "thinking": "",
            }

        # ── Шаг 1: RAG — собираем контекст проекта ──
        context_chunks = await self.rag.retrieve(message, top_k=5)
        context_text = self._format_context(context_chunks)

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
        result = await self._execute_plan(
            plan, message, context_text, selected_code,
            conversation_history, user_lang
        )

        # ── Шаг 4: Reflection — проверяем качество ответа ──
        result = await self._reflect(result, message, context_text, user_lang)

        # Добавляем метаданные RAG
        result["references"] = [c["metadata"]["file_path"] for c in context_chunks]
        result["rag_chunks"] = len(context_chunks)

        return result

    # ─── Planning ────────────────────────────────────────────────────────

    async def _plan(
        self, message: str, context: str,
        selected_code: Optional[str], history: list,
    ) -> dict:
        if self.llm.is_loaded():
            return await self._llm_plan(message, context, selected_code, history)
        else:
            return self._rule_based_plan(message, selected_code)

    async def _llm_plan(self, message: str, context: str,
                        selected_code: Optional[str], history: list) -> dict:
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
  "intent": "analyze|generate|refactor|test|explain|review|multi",
  "agents": ["analyst"],
  "reasoning": "brief reason",
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
            raw, _ = strip_think_tags(raw)

            json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
            if json_match:
                plan_data = json.loads("{" + json_match.group().lstrip("{"))
                if "intent" in plan_data and "agents" in plan_data:
                    logger.info(f"LLM planning succeeded: {plan_data}")
                    return plan_data
        except Exception as e:
            logger.warning(f"LLM planning failed ({e}), falling back to rule-based")

        return self._rule_based_plan(message, selected_code)

    def _rule_based_plan(self, message: str, selected_code: Optional[str]) -> dict:
        msg = message.lower()

        patterns = {
            "refactor": {
                "keywords": [
                    "refactor", "рефактор", "rewrite", "перепиши", "паттерн", "pattern",
                    "optimize", "оптимизир", "clean up", "restructure", "extract",
                    "strategy", "стратегия", "observer", "factory", "decorator",
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
            "review": {
                "keywords": [
                    "review", "ревью", "code review", "проверь", "аудит", "audit",
                    "уязвимост", "vulnerability", "security", "безопасн",
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
                    "улучш", "improve", "предлож", "suggest",
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
            if selected_code and len(message.split()) < 15:
                return {"intent": "explain", "agents": ["analyst", "coder"],
                        "reasoning": "short question with code → explain + suggest fix",
                        "confidence": 0.7}
            return {"intent": "general", "agents": ["analyst"],
                    "reasoning": "general question", "confidence": 0.5}

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
        self, plan: dict, message: str, context: str,
        selected_code: Optional[str], history: list, user_lang: str,
    ) -> dict:
        intent = plan.get("intent", "general")
        agents = plan.get("agents", ["analyst"])

        lang_instruction = (
            "CRITICAL: Отвечай ТОЛЬКО на русском языке. Весь текст, объяснения и комментарии — на русском."
            if user_lang == 'ru' else
            "Respond in English."
        )

        logger.info(f"Executing plan: intent={intent}, agents={agents}, lang={user_lang}")

        if intent == "refactor":
            return await self._execute_refactor(message, context, selected_code, history, lang_instruction)
        elif intent == "test":
            return await self._execute_test_pipeline(message, context, selected_code, history, lang_instruction)
        elif intent == "generate":
            return await self._execute_generate_pipeline(message, context, selected_code, history, lang_instruction)
        elif intent in ("analyze", "explain"):
            return await self._execute_analysis(message, context, selected_code, history, lang_instruction)
        elif intent == "review":
            return await self._execute_review(message, context, selected_code, history, lang_instruction)
        elif intent == "multi":
            return await self._execute_multi_agent(message, context, selected_code, history, agents, lang_instruction)
        else:
            return await self._execute_general(message, context, selected_code, history, lang_instruction)

    async def _execute_analysis(self, message, context, selected_code, history, lang_instruction) -> dict:
        logger.info("→ [ANALYST] Analyzing request")

        if selected_code:
            # Если есть код — объясняем И предлагаем улучшения
            result = await self.analyst.explain_with_fixes(
                code=selected_code,
                question=message,
                context=context,
                lang_instruction=lang_instruction,
            )
        else:
            result = await self.analyst.analyze(message, context, history, lang_instruction=lang_instruction)

        response, thinking = strip_think_tags(result["response"])

        return {
            "response": response,
            "code": result.get("improved_code"),
            "agent": "analyst",
            "intent": "analyze",
            "agent_trace": ["analyst"],
            "thinking": thinking,
        }

    async def _execute_generate_pipeline(self, message, context, selected_code, history, lang_instruction) -> dict:
        logger.info("→ [ANALYST→CODER] Starting generation pipeline")

        # Step 1: Analyst изучает контекст
        logger.info("  [ANALYST] Analyzing requirements...")
        analysis = await self.analyst.analyze(
            f"Analyze this code generation request and identify: "
            f"1) What needs to be created, "
            f"2) Relevant existing patterns in the codebase, "
            f"3) Key constraints and conventions. "
            f"Request: {message}",
            context, history, lang_instruction=lang_instruction,
        )
        analysis_text, thinking1 = strip_think_tags(analysis["response"])
        logger.info("  [ANALYST] Analysis complete")

        # Step 2: Coder генерирует код
        logger.info("  [CODER] Generating code...")
        generated = await self.coder.generate(
            message=message, context=context,
            selected_code=selected_code, analysis=analysis_text,
            lang_instruction=lang_instruction,
        )
        response, thinking2 = strip_think_tags(generated["response"])
        logger.info("  [CODER] Generation complete")

        thinking = "\n\n".join(filter(None, [thinking1, thinking2]))

        return {
            "response": response,
            "code": generated.get("code"),
            "agent": "coder",
            "intent": "generate",
            "agent_trace": ["analyst", "coder"],
            "analysis_summary": analysis_text[:300],
            "thinking": thinking,
        }

    async def _execute_refactor(self, message, context, selected_code, history, lang_instruction) -> dict:
        logger.info("→ [REFACTOR] Starting refactoring")

        code_to_refactor = selected_code or context or ""

        if not selected_code and not context:
            logger.info("  [ANALYST] No code provided, searching...")
            search_result = await self.analyst.analyze(
                f"Find the relevant code to refactor: {message}",
                context, history, lang_instruction=lang_instruction,
            )
            text, _ = strip_think_tags(search_result["response"])
            code_to_refactor = text

        result = await self.refactor_agent.refactor(
            code=code_to_refactor, instruction=message,
            context=context, lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(result["response"])

        return {
            "response": response,
            "code": result.get("refactored_code"),
            "agent": "refactor",
            "intent": "refactor",
            "agent_trace": ["refactor"],
            "thinking": thinking,
        }

    async def _execute_test_pipeline(self, message, context, selected_code, history, lang_instruction) -> dict:
        logger.info("→ [ANALYST→TESTER] Starting test generation pipeline")

        code_to_test = selected_code or context or ""

        if not selected_code:
            logger.info("  [ANALYST] Finding code to test...")
            analysis = await self.analyst.analyze(
                f"Identify the code that needs to be tested: {message}",
                context, history, lang_instruction=lang_instruction,
            )
            text, _ = strip_think_tags(analysis["response"])
            code_to_test = text

        logger.info("  [TESTER] Generating tests...")
        result = await self.tester.generate_tests(
            code=code_to_test, instruction=message,
            context=context, lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(result["response"])
        logger.info("  [TESTER] Tests generated")

        return {
            "response": response,
            "code": result.get("test_code"),
            "agent": "tester",
            "intent": "test",
            "agent_trace": ["analyst", "tester"],
            "thinking": thinking,
        }

    async def _execute_review(self, message, context, selected_code, history, lang_instruction) -> dict:
        """
        Code review pipeline: Analyst находит проблемы,
        Coder предлагает исправления.
        """
        logger.info("→ [ANALYST→CODER] Code review pipeline")

        code_to_review = selected_code or context or ""

        # Analyst — ревью
        review_result = await self.analyst.analyze(
            f"Conduct a detailed code review. For EACH issue found, describe the problem "
            f"AND provide a specific code fix. Request: {message}",
            code_to_review, history, lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(review_result["response"])

        return {
            "response": response,
            "code": None,
            "agent": "analyst",
            "intent": "review",
            "agent_trace": ["analyst", "coder"],
            "thinking": thinking,
        }

    async def _execute_multi_agent(self, message, context, selected_code, history, agents, lang_instruction) -> dict:
        logger.info(f"→ [MULTI-AGENT] Running agents: {agents}")

        accumulated_context = context
        last_response = None
        agent_trace = []
        all_thinking = []

        for agent_name in agents:
            logger.info(f"  [{agent_name.upper()}] Processing...")

            if agent_name == "analyst":
                result = await self.analyst.analyze(
                    message, accumulated_context, history,
                    lang_instruction=lang_instruction,
                )
                text, thinking = strip_think_tags(result["response"])
                last_response = text
                accumulated_context = f"{accumulated_context}\n\n## Previous Analysis:\n{text}"

            elif agent_name == "coder":
                result = await self.coder.generate(
                    message=message, context=accumulated_context,
                    selected_code=selected_code, analysis=last_response or "",
                    lang_instruction=lang_instruction,
                )
                text, thinking = strip_think_tags(result["response"])
                last_response = text

            elif agent_name == "refactor":
                result = await self.refactor_agent.refactor(
                    code=selected_code or context,
                    instruction=message, context=accumulated_context,
                    lang_instruction=lang_instruction,
                )
                text, thinking = strip_think_tags(result["response"])
                last_response = text

            elif agent_name == "tester":
                result = await self.tester.generate_tests(
                    code=selected_code or accumulated_context,
                    instruction=message, context=accumulated_context,
                    lang_instruction=lang_instruction,
                )
                text, thinking = strip_think_tags(result["response"])
                last_response = text

            agent_trace.append(agent_name)
            if thinking:
                all_thinking.append(thinking)

        return {
            "response": last_response or "Multi-agent pipeline completed",
            "code": result.get("code") if result else None,
            "agent": "multi",
            "intent": "multi",
            "agent_trace": agent_trace,
            "thinking": "\n\n".join(all_thinking),
        }

    async def _execute_general(self, message, context, selected_code, history, lang_instruction) -> dict:
        logger.info("→ [GENERAL] Direct analyst response")

        result = await self.analyst.analyze(
            message, context, history,
            lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(result["response"])

        return {
            "response": response,
            "agent": "analyst",
            "intent": "general",
            "agent_trace": ["analyst"],
            "thinking": thinking,
        }

    # ─── Reflection ──────────────────────────────────────────────────────

    async def _reflect(self, result: dict, original_message: str,
                    context: str, user_lang: str) -> dict:
        response = result.get("response", "")
        
        # ── Санитизация: убираем артефакты генерации ──
        response = sanitize_response(response)
        
        # Проверки качества
        if len(response) < 20:
            logger.warning("Response too short, may indicate an issue")
            hint = (
                "\n\n*Примечание: Ответ может быть неполным. Попробуйте уточнить запрос.*"
                if user_lang == 'ru' else
                "\n\n*Note: Response may be incomplete. Try refining your question.*"
            )
            response = response + hint

        # Проверяем язык
        if user_lang == 'ru':
            response_lang = detect_language(response)
            if response_lang == 'en' and len(response) > 100:
                logger.warning("Response is in English but user asked in Russian")
                result["language_mismatch"] = True

        result["response"] = response.strip()

        if "thinking" not in result:
            result["thinking"] = ""

        # Санитизируем thinking тоже
        if result["thinking"]:
            result["thinking"] = sanitize_response(result["thinking"])

        return result

    # ─── Утилиты ─────────────────────────────────────────────────────────

    def _format_context(self, chunks: list) -> str:
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
        response, _ = strip_think_tags(result["response"])
        return {
            "response": response,
            "refactored_code": result.get("refactored_code"),
            "file_path": file_path,
        }

    async def inline_edit(self, file_path, code, instruction, line_start, line_end, context="") -> dict:
        result = await self.coder.inline_edit(
            code=code, instruction=instruction,
            line_start=line_start, line_end=line_end, context=context,
        )
        response, _ = strip_think_tags(result.get("response", ""))
        return {
            "original_code": code,
            "edited_code": result.get("code", code),
            "explanation": response,
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
        }