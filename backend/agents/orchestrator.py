"""
Multi-Agent Orchestrator v4.0 — НАСТОЯЩАЯ мультиагентная система

Ключевые отличия от v3:
1. Реальный ReAct-цикл с итеративными tool calls (до MAX_REACT_STEPS)
2. Агенты имеют настоящие инструменты: read_file, write_file, edit_file, run_command, search_code
3. Streaming: каждый шаг транслируется в реальном времени через callback
4. Межагентная коммуникация: агенты передают контекст друг другу
5. File change tracking: все изменения файлов трекаются и передаются в UI
6. Автоматический язык ответа + thinking-блоки
"""

import asyncio
import json
import logging
import re
from typing import Optional, Callable, AsyncGenerator

from .analyst import AnalystAgent
from .coder import CoderAgent
from .refactor import RefactorAgent
from .tester import TesterAgent
from .tools import AgentToolkit, ToolResult
from .utils import strip_think_tags, detect_language, sanitize_response

logger = logging.getLogger(__name__)

MAX_REACT_STEPS = 8  # Максимум итераций ReAct-цикла


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
    "или другими аспектами разработки."
)

OFFTOPIC_RESPONSE_EN = (
    "I specialize exclusively in software development and technical questions. "
    "Please ask a question related to code, architecture, debugging, testing "
    "or other aspects of development."
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


# ─── Парсинг tool calls из ответа LLM ───────────────────────────────────────

def parse_tool_calls(text: str) -> list[dict]:
    """
    Извлекает вызовы инструментов из ответа LLM.
    Формат: ```tool\n{"tool": "name", "args": {...}}\n```
    """
    calls = []

    # Формат 1: ```tool ... ```
    for match in re.finditer(r'```tool\s*\n(.*?)```', text, re.DOTALL):
        try:
            data = json.loads(match.group(1).strip())
            if "tool" in data:
                calls.append(data)
        except json.JSONDecodeError:
            continue

    # Формат 2: <tool>...</tool>
    for match in re.finditer(r'<tool>(.*?)</tool>', text, re.DOTALL):
        try:
            data = json.loads(match.group(1).strip())
            if "tool" in data:
                calls.append(data)
        except json.JSONDecodeError:
            continue

    # Формат 3: TOOL_CALL: {...}
    for match in re.finditer(r'TOOL_CALL:\s*(\{.*?\})', text, re.DOTALL):
        try:
            data = json.loads(match.group(1))
            if "tool" in data:
                calls.append(data)
        except json.JSONDecodeError:
            continue

    return calls


def strip_tool_calls(text: str) -> str:
    """Убирает блоки вызовов инструментов из ответа"""
    text = re.sub(r'```tool\s*\n.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<tool>.*?</tool>', '', text, flags=re.DOTALL)
    text = re.sub(r'TOOL_CALL:\s*\{.*?\}', '', text, flags=re.DOTALL)
    return text.strip()


def _clean_react_response(text: str) -> str:
    """
    Clean up the final ReAct response:
    - Remove leaked tool result blocks (### Tool Result ...)
    - Remove line-numbered file content that leaked from read_file output (outside code blocks)
    - Remove continuation prompts
    """
    # Remove tool result blocks: "### Tool Result (tool_name):\n...content..." up to next heading or end
    text = re.sub(r'### Tool Result \([^)]*\):\n.*?(?=\n##|\n\*\*|\Z)', '', text, flags=re.DOTALL)

    # Remove lines that look like read_file output OUTSIDE of code blocks:
    # Pattern: "   42 | code here" — only standalone (not in ``` blocks)
    # Split by code blocks, only clean non-code parts
    parts = re.split(r'(```[\s\S]*?```)', text)
    for i in range(0, len(parts), 2):  # Only process non-code parts (even indices)
        if i < len(parts):
            # Remove leaked line-numbered content
            parts[i] = re.sub(r'^\s{0,4}\d{1,5}\s*\|.*$', '', parts[i], flags=re.MULTILINE)
    text = ''.join(parts)

    # Remove continuation instructions that leaked into output
    text = re.sub(r'You have \d+ steps remaining\..*?(?:tool calls\.|response\.)', '', text, flags=re.DOTALL)
    text = re.sub(r'Continue\. If you need more tools.*?(?:tool calls\.|response\.)', '', text, flags=re.DOTALL)
    text = re.sub(r'You already read this file above\..*', '', text)
    text = re.sub(r'DO NOT read the same file again\..*?(?:tool calls\.|response\.)', '', text, flags=re.DOTALL)

    # Remove control tokens
    text = re.sub(r'<\|(?:system|user|assistant|end|im_start|im_end|endoftext)\|>', '', text)

    # Clean up excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ─── Настоящая мультиагентная система ─────────────────────────────────────────

class AgentOrchestrator:
    """
    Мультиагентная система v4.0 с настоящим ReAct-циклом и инструментами.

    Цикл:
    1. PLAN: определить intent и выбрать агентов
    2. REACT LOOP (до MAX_REACT_STEPS итераций):
       a. REASON: агент анализирует запрос + контекст + результаты прошлых инструментов
       b. ACT: если нужно — вызвать инструменты (read_file, write_file, run_command, etc.)
       c. OBSERVE: получить результаты инструментов, добавить в контекст
       d. Повторить или завершить
    3. REFLECT: санитизация, проверка качества, языковая проверка
    """

    def __init__(self, llm, rag_engine, config: dict):
        self.llm = llm
        self.rag = rag_engine
        self.config = config
        self.toolkit = AgentToolkit()

        # Специализированные агенты
        self.analyst = AnalystAgent(llm)
        self.coder = CoderAgent(llm)
        self.refactor_agent = RefactorAgent(llm)
        self.tester = TesterAgent(llm)

        logger.info("AgentOrchestrator v4 initialized (ReAct + Tools + Streaming)")

    # ─── Главная точка входа ─────────────────────────────────────────────

    async def process_request(
        self,
        message: str,
        context_file: Optional[str] = None,
        selected_code: Optional[str] = None,
        conversation_history: list = None,
        stream_callback: Optional[Callable] = None,
        platform: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> dict:
        """
        stream_callback(event_type, data) — для real-time streaming в UI.
        event_types: 'thinking', 'agent_start', 'agent_done', 'tool_call',
                     'tool_result', 'token', 'status'
        """
        if conversation_history is None:
            conversation_history = []

        self.platform = platform or "unknown"

        # Callback helper
        async def emit(event_type: str, data: any = None):
            if stream_callback:
                await stream_callback(event_type, data)

        # Устанавливаем workspace — приоритет: workspace_path > context_file > fallback
        from pathlib import Path
        if workspace_path:
            self.toolkit.set_workspace(workspace_path)
            logger.info(f"Workspace set from workspace_path: {workspace_path}")
        elif context_file:
            cf = Path(context_file)
            workspace_set = False
            for parent in cf.parents:
                if (parent / ".git").exists() or (parent / "package.json").exists() or (parent / "pyproject.toml").exists():
                    self.toolkit.set_workspace(str(parent))
                    logger.info(f"Workspace set from context_file project root: {parent}")
                    workspace_set = True
                    break
            if not workspace_set and cf.parent.exists():
                self.toolkit.set_workspace(str(cf.parent))
                logger.info(f"Workspace set from context_file parent: {cf.parent}")

        if not self.toolkit.workspace_root:
            logger.warning("No workspace root set! Tools requiring file access will fail.")

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
                "file_changes": [],
            }

        # ── Шаг 1: RAG — собираем контекст проекта ──
        await emit("status", "Ищу релевантный контекст в проекте...")
        context_chunks = await self.rag.retrieve(message, top_k=5)
        context_text = self._format_context(context_chunks)

        if context_file:
            file_chunks = await self.rag.get_file_context(context_file)
            if file_chunks:
                file_text = "\n".join([c["content"] for c in file_chunks[:3]])
                context_text = f"// Current file: {context_file}\n{file_text}\n\n{context_text}"

        logger.info(f"RAG retrieved {len(context_chunks)} chunks for: {message[:60]}...")

        # ── Шаг 1.5: Дочитываем файлы, упомянутые в запросе ──
        context_text = await self._read_mentioned_files(message, context_text)

        # ── Шаг 2: Planning — агент составляет план ──
        await emit("status", "Планирую выполнение запроса...")
        plan = await self._plan(message, context_text, selected_code, conversation_history)

        # Force tools for intents that need file access
        file_action_keywords = [
            "создай файл", "create file", "удали", "delete", "remove", "rm ",
            "запусти", "выполни", "run", "execute", "install",
            "рефактор", "refactor", "перепиши", "rewrite",
        ]
        if any(kw in message.lower() for kw in file_action_keywords):
            plan["needs_tools"] = True

        logger.info(f"Agent plan: intent={plan['intent']}, agents={plan['agents']}, tools={plan.get('needs_tools')}")
        await emit("agent_start", {"intent": plan["intent"], "agents": plan["agents"]})

        # ── Шаг 3: Execution с ReAct-циклом ──
        result = await self._execute_plan(
            plan, message, context_text, selected_code,
            conversation_history, user_lang, emit
        )

        # ── Шаг 4: Reflection ──
        result = await self._reflect(result, message, context_text, user_lang)

        # Добавляем метаданные
        result["references"] = [c["metadata"]["file_path"] for c in context_chunks]
        result["rag_chunks"] = len(context_chunks)
        result["file_changes"] = self.toolkit.get_changes_summary()

        await emit("agent_done", {"agent": result.get("agent"), "intent": result.get("intent")})

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

        planning_prompt = f"""<|system|>
You are a planning agent for a code assistant. Analyze the user's request and determine the best action plan.

Available agents:
- analyst: answers questions about code, finds implementations, explains architecture
- coder: generates new code, implements functions, creates endpoints, creates/edits files
- refactor: refactors existing code, applies design patterns, improves quality
- tester: generates unit tests, integration tests, test fixtures
- multi: use multiple agents in sequence (analyst+coder, analyst+tester, etc.)

The agents have access to tools: read_file, write_file, edit_file, run_command, search_code, list_files.
If the request involves creating/modifying files or running commands, include "coder" in agents and set needs_tools=true.

Respond with ONLY a JSON object:
{{
  "intent": "analyze|generate|refactor|test|explain|review|multi",
  "agents": ["analyst"],
  "reasoning": "brief reason",
  "needs_code": true/false,
  "needs_tools": true/false,
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
                "needs_tools": True,
            },
            "test": {
                "keywords": [
                    "test", "тест", "unit test", "юнит", "spec", "coverage",
                    "покрытие", "mock", "мок", "assert", "pytest", "jest",
                    "проверк", "verify", "тестирование",
                ],
                "agents": ["analyst", "tester"],
                "needs_tools": True,
            },
            "generate": {
                "keywords": [
                    "generate", "сгенерируй", "create", "создай", "implement", "реализуй",
                    "write", "напиши", "add", "добавь", "build", "make", "сделай",
                    "endpoint", "handler", "обработчик", "функцию", "класс",
                    "создать файл", "создай файл", "новый файл",
                ],
                "agents": ["analyst", "coder"],
                "needs_tools": True,
            },
            "review": {
                "keywords": [
                    "review", "ревью", "code review", "проверь", "аудит", "audit",
                    "уязвимост", "vulnerability", "security", "безопасн",
                ],
                "agents": ["analyst"],
                "needs_tools": True,
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
                "needs_tools": True,
            },
        }

        # Детект команд: если пользователь просит выполнить команду
        cmd_keywords = ["запусти", "выполни", "run", "execute", "install", "npm", "pip", "python"]
        if any(kw in msg for kw in cmd_keywords):
            return {
                "intent": "generate",
                "agents": ["coder"],
                "reasoning": "user wants to execute a command",
                "needs_tools": True,
                "confidence": 0.9,
            }

        # Детект создания/редактирования файлов
        file_keywords = ["создай файл", "создать файл", "create file", "write file",
                         "edit file", "modify file", "изменить файл", "отредактируй"]
        if any(kw in msg for kw in file_keywords):
            return {
                "intent": "generate",
                "agents": ["coder"],
                "reasoning": "user wants to create/edit files",
                "needs_tools": True,
                "confidence": 0.9,
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
                        "needs_tools": True,
                        "confidence": 0.7}
            return {"intent": "general", "agents": ["analyst"],
                    "reasoning": "general question", "confidence": 0.5}

        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent] / 3.0, 1.0)

        return {
            "intent": best_intent,
            "agents": patterns[best_intent]["agents"],
            "reasoning": f"matched {scores[best_intent]} keywords",
            "needs_tools": patterns[best_intent].get("needs_tools", False),
            "confidence": confidence,
        }

    # ─── Execution ───────────────────────────────────────────────────────

    async def _execute_plan(
        self, plan: dict, message: str, context: str,
        selected_code: Optional[str], history: list, user_lang: str,
        emit: Callable,
    ) -> dict:
        intent = plan.get("intent", "general")
        agents = plan.get("agents", ["analyst"])
        needs_tools = plan.get("needs_tools", False)

        lang_instruction = (
            "CRITICAL: Отвечай ТОЛЬКО на русском языке. Весь текст, объяснения и комментарии — на русском."
            if user_lang == 'ru' else
            "Respond in English."
        )

        logger.info(f"Executing plan: intent={intent}, agents={agents}, lang={user_lang}, tools={needs_tools}")

        # Если нужны инструменты — запускаем ReAct-цикл
        if needs_tools:
            return await self._react_loop(
                message, context, selected_code, history,
                lang_instruction, agents, intent, emit
            )

        # Иначе — стандартное выполнение через агентов
        if intent == "refactor":
            return await self._execute_refactor(message, context, selected_code, history, lang_instruction, emit)
        elif intent == "test":
            return await self._execute_test_pipeline(message, context, selected_code, history, lang_instruction, emit)
        elif intent == "generate":
            return await self._execute_generate_pipeline(message, context, selected_code, history, lang_instruction, emit)
        elif intent in ("analyze", "explain"):
            return await self._execute_analysis(message, context, selected_code, history, lang_instruction, emit)
        elif intent == "review":
            return await self._execute_review(message, context, selected_code, history, lang_instruction, emit)
        elif intent == "multi":
            return await self._execute_multi_agent(message, context, selected_code, history, agents, lang_instruction, emit)
        else:
            return await self._execute_general(message, context, selected_code, history, lang_instruction, emit)

    # ─── ReAct Loop — настоящий цикл Reason→Act→Observe ──────────────

    async def _react_loop(
        self, message: str, context: str, selected_code: Optional[str],
        history: list, lang_instruction: str, agents: list,
        intent: str, emit: Callable,
    ) -> dict:
        """
        Настоящий ReAct-цикл: LLM решает, какие инструменты вызвать,
        получает результаты, и итерирует до завершения.
        """
        logger.info("→ [REACT] Starting ReAct loop with tools")
        await emit("status", "🔧 Запускаю агентов с инструментами...")

        tool_descriptions = self.toolkit.get_tools_description()
        all_thinking = []
        tool_trace = []
        files_already_read = set()  # Prevent re-reading same files

        # Определяем платформу
        platform_map = {"win32": "Windows", "linux": "Linux", "darwin": "macOS"}
        platform_name = platform_map.get(getattr(self, 'platform', ''), 'Unknown')

        # Формируем начальный промпт
        system = (
            f"You are an expert software engineer agent with access to real tools.\n"
            f"{lang_instruction}\n\n"
            f"IMPORTANT: You can use tools to read files, write files, edit files, run commands, and search code.\n"
            f"The user is working on {platform_name}. Use platform-appropriate commands.\n"
            f"Think step by step. Use tools when needed. When done, provide your final answer.\n\n"
            f"CRITICAL RULES:\n"
            f"1. ALWAYS start by using list_files to see the project structure.\n"
            f"2. ALWAYS use read_file to read file contents BEFORE analyzing, reviewing, refactoring, or modifying them.\n"
            f"3. Read ALL relevant files — do not guess or assume file contents.\n"
            f"4. When the user asks about their project, use search_code and list_files to explore it thoroughly.\n"
            f"5. When suggesting terminal commands, use the correct syntax for {platform_name}.\n"
            f"6. NEVER read the same file twice — use the content from your first read.\n"
            f"7. For EVERY code suggestion, ALWAYS specify action, file, and lines using this EXACT format:\n"
            f"   Действие: заменить|добавить|удалить\n"
            f"   Файл: path/to/file.ext\n"
            f"   Строки: START-END\n"
            f"   ```lang\n"
            f"   code here\n"
            f"   ```\n"
            f"\n"
            f"   EXAMPLES:\n"
            f"   To REPLACE code (заменить):\n"
            f"   Действие: заменить\n"
            f"   Файл: src/utils.py\n"
            f"   Строки: 42-67\n"
            f"   ```python\n"
            f"   def improved_function():\n"
            f"       pass\n"
            f"   ```\n"
            f"\n"
            f"   To ADD new code (добавить) after a specific line:\n"
            f"   Действие: добавить\n"
            f"   Файл: src/utils.py\n"
            f"   Строка: 15\n"
            f"   ```python\n"
            f"   def new_function():\n"
            f"       pass\n"
            f"   ```\n"
            f"\n"
            f"   To DELETE code (удалить):\n"
            f"   Действие: удалить\n"
            f"   Файл: src/utils.py\n"
            f"   Строки: 42-50\n"
            f"\n"
            f"   ALWAYS include Действие, Файл, and Строки for EVERY code block! This is CRITICAL.\n\n"
            f"{tool_descriptions}\n"
        )

        messages_context = f"<|system|>\n{system}\n<|end|>\n"

        if context:
            messages_context += f"<|user|>\n## Project Context:\n```\n{context[:3000]}\n```\n\n"
        else:
            messages_context += "<|user|>\n"

        if selected_code:
            messages_context += f"## Selected Code:\n```\n{selected_code}\n```\n\n"

        messages_context += f"## User Request: {message}\n<|end|>\n<|assistant|>"

        accumulated_code = None

        for step in range(MAX_REACT_STEPS):
            logger.info(f"  [REACT step {step + 1}/{MAX_REACT_STEPS}]")
            await emit("status", f"🤔 Шаг {step + 1}: Агент размышляет...")

            # Генерируем ответ (4096 tokens for detailed responses like code review)
            response = await self.llm.generate(messages_context, max_new_tokens=4096)
            response, thinking = strip_think_tags(response)

            if thinking:
                all_thinking.append(thinking)
                await emit("thinking", thinking)

            # Парсим tool calls
            tool_calls = parse_tool_calls(response)

            if not tool_calls:
                # Нет tool calls — агент завершил работу
                clean_response = strip_tool_calls(response)
                # Remove any leaked tool result artifacts (line-numbered content from read_file)
                clean_response = _clean_react_response(clean_response)
                logger.info(f"  [REACT] Agent finished after {step + 1} steps")

                # Извлекаем код из ответа
                code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', clean_response, re.DOTALL)
                if code_blocks:
                    accumulated_code = code_blocks[-1].strip()

                return {
                    "response": clean_response,
                    "code": accumulated_code,
                    "agent": agents[-1] if agents else "coder",
                    "intent": intent,
                    "agent_trace": ["react"] + tool_trace,
                    "thinking": "\n\n".join(all_thinking),
                }

            # Выполняем tool calls
            tool_results_text = ""
            for tc in tool_calls:
                tool_name = tc.get("tool", "unknown")
                tool_args = tc.get("args", {})

                # Prevent re-reading the same file (loop prevention)
                if tool_name == "read_file":
                    fpath = tool_args.get("file_path", "")
                    if fpath in files_already_read:
                        logger.info(f"  [TOOL SKIP] Already read {fpath}, skipping")
                        tool_results_text += f"\n\n### Tool Result ({tool_name}):\nYou already read this file above. Use the contents from the previous read.\n"
                        continue
                    files_already_read.add(fpath)

                await emit("tool_call", {"tool": tool_name, "args": tool_args})
                logger.info(f"  [TOOL] {tool_name}({tool_args})")

                result = await self.toolkit.execute_tool(tool_name, tool_args)
                tool_trace.append(tool_name)

                await emit("tool_result", {"tool": tool_name, "success": result.success, "output": result.output[:500]})
                logger.info(f"  [TOOL RESULT] {result}")

                # Truncate tool output to prevent context overflow
                # For read_file: keep max 4000 chars (enough for most files)
                truncated_output = result.output
                if len(truncated_output) > 4000:
                    truncated_output = truncated_output[:4000] + f"\n... [truncated, {len(result.output)} chars total]"

                tool_results_text += f"\n\n### Tool Result ({tool_name}):\n{truncated_output}\n"

            # Добавляем результаты в контекст для следующей итерации
            clean_response = strip_tool_calls(response)
            remaining_steps = MAX_REACT_STEPS - step - 1
            messages_context += (
                f"{clean_response}\n\n{tool_results_text}\n\n"
                f"You have {remaining_steps} steps remaining. "
                f"You have already read the file contents above — DO NOT read the same file again. "
                f"Now provide your FINAL detailed answer based on the file contents you received. "
                f"If you still need OTHER files, call tools. Otherwise, provide your complete response WITHOUT any tool calls.\n"
                f"<|end|>\n<|assistant|>"
            )

        # Если превышен лимит итераций
        logger.warning(f"  [REACT] Max steps reached ({MAX_REACT_STEPS})")
        return {
            "response": _clean_react_response(strip_tool_calls(response)) + "\n\n*⚠ Достигнут лимит итераций агента.*",
            "code": accumulated_code,
            "agent": "react",
            "intent": intent,
            "agent_trace": ["react"] + tool_trace,
            "thinking": "\n\n".join(all_thinking),
        }

    # ─── Standard pipelines (улучшенные со streaming) ─────────────────

    async def _execute_analysis(self, message, context, selected_code, history, lang_instruction, emit) -> dict:
        logger.info("→ [ANALYST] Analyzing request")
        await emit("status", "🔍 Аналитик изучает запрос...")

        if selected_code:
            result = await self.analyst.explain_with_fixes(
                code=selected_code, question=message,
                context=context, lang_instruction=lang_instruction,
            )
        else:
            result = await self.analyst.analyze(message, context, history, lang_instruction=lang_instruction)

        response, thinking = strip_think_tags(result["response"])
        if thinking:
            await emit("thinking", thinking)

        return {
            "response": response,
            "code": result.get("improved_code"),
            "agent": "analyst",
            "intent": "analyze",
            "agent_trace": ["analyst"],
            "thinking": thinking,
        }

    async def _execute_generate_pipeline(self, message, context, selected_code, history, lang_instruction, emit) -> dict:
        logger.info("→ [ANALYST→CODER] Starting generation pipeline")

        # Step 1: Analyst
        await emit("status", "🔍 Аналитик изучает требования...")
        analysis = await self.analyst.analyze(
            f"Analyze this code generation request and identify: "
            f"1) What needs to be created, "
            f"2) Relevant existing patterns in the codebase, "
            f"3) Key constraints and conventions. "
            f"Request: {message}",
            context, history, lang_instruction=lang_instruction,
        )
        analysis_text, thinking1 = strip_think_tags(analysis["response"])
        if thinking1:
            await emit("thinking", thinking1)

        # Step 2: Coder
        await emit("status", "💻 Кодер генерирует код...")
        generated = await self.coder.generate(
            message=message, context=context,
            selected_code=selected_code, analysis=analysis_text,
            lang_instruction=lang_instruction,
        )
        response, thinking2 = strip_think_tags(generated["response"])
        if thinking2:
            await emit("thinking", thinking2)

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

    async def _execute_refactor(self, message, context, selected_code, history, lang_instruction, emit) -> dict:
        logger.info("→ [REFACTOR] Starting refactoring")
        await emit("status", "🔄 Рефакторинг...")

        code_to_refactor = selected_code or context or ""

        if not selected_code and not context:
            await emit("status", "🔍 Ищу код для рефакторинга...")
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
        if thinking:
            await emit("thinking", thinking)

        return {
            "response": response,
            "code": result.get("refactored_code"),
            "agent": "refactor",
            "intent": "refactor",
            "agent_trace": ["refactor"],
            "thinking": thinking,
        }

    async def _execute_test_pipeline(self, message, context, selected_code, history, lang_instruction, emit) -> dict:
        logger.info("→ [ANALYST→TESTER] Starting test generation pipeline")

        code_to_test = selected_code or context or ""

        if not selected_code:
            await emit("status", "🔍 Ищу код для тестирования...")
            analysis = await self.analyst.analyze(
                f"Identify the code that needs to be tested: {message}",
                context, history, lang_instruction=lang_instruction,
            )
            text, _ = strip_think_tags(analysis["response"])
            code_to_test = text

        await emit("status", "🧪 Генерирую тесты...")
        result = await self.tester.generate_tests(
            code=code_to_test, instruction=message,
            context=context, lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(result["response"])
        if thinking:
            await emit("thinking", thinking)

        return {
            "response": response,
            "code": result.get("test_code"),
            "agent": "tester",
            "intent": "test",
            "agent_trace": ["analyst", "tester"],
            "thinking": thinking,
        }

    async def _execute_review(self, message, context, selected_code, history, lang_instruction, emit) -> dict:
        logger.info("→ [ANALYST] Code review")
        await emit("status", "🔍 Провожу code review...")

        code_to_review = selected_code or context or ""

        review_result = await self.analyst.analyze(
            f"Conduct a detailed code review. For EACH issue found, describe the problem "
            f"AND provide a specific code fix. Request: {message}",
            code_to_review, history, lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(review_result["response"])
        if thinking:
            await emit("thinking", thinking)

        return {
            "response": response,
            "code": None,
            "agent": "analyst",
            "intent": "review",
            "agent_trace": ["analyst"],
            "thinking": thinking,
        }

    async def _execute_multi_agent(self, message, context, selected_code, history, agents, lang_instruction, emit) -> dict:
        logger.info(f"→ [MULTI-AGENT] Running agents: {agents}")

        accumulated_context = context
        last_response = None
        agent_trace = []
        all_thinking = []
        result = {}

        for agent_name in agents:
            await emit("status", f"⚙ Агент {agent_name} работает...")
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
                await emit("thinking", thinking)

        return {
            "response": last_response or "Multi-agent pipeline completed",
            "code": result.get("code") if result else None,
            "agent": "multi",
            "intent": "multi",
            "agent_trace": agent_trace,
            "thinking": "\n\n".join(all_thinking),
        }

    async def _execute_general(self, message, context, selected_code, history, lang_instruction, emit) -> dict:
        logger.info("→ [GENERAL] Direct analyst response")
        await emit("status", "🤖 Обрабатываю запрос...")

        result = await self.analyst.analyze(
            message, context, history,
            lang_instruction=lang_instruction,
        )
        response, thinking = strip_think_tags(result["response"])
        if thinking:
            await emit("thinking", thinking)

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

        # Санитизация (preserve_think=False — thinking уже извлечён)
        response = sanitize_response(response, preserve_think=False)

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

        if result["thinking"]:
            result["thinking"] = sanitize_response(result["thinking"], preserve_think=False)

        if "file_changes" not in result:
            result["file_changes"] = []

        return result

    # ─── Утилиты ─────────────────────────────────────────────────────────

    async def _read_mentioned_files(self, message: str, context: str) -> str:
        """
        Reads files explicitly mentioned in the user's message and adds their
        content to the context. This ensures agents can actually see file contents
        even if RAG didn't retrieve them.
        """
        if not self.toolkit.workspace_root:
            return context

        # Extract file paths from message
        mentioned = set()
        patterns = [
            r'(?:файл[еа]?\s+|file\s+)(\S+\.\w{1,6})',
            r'(\S+\.(?:py|js|ts|tsx|jsx|java|cpp|go|rs|rb|php|css|scss|html|vue|svelte|json|yaml|yml|toml|md|sql|sh))\b',
        ]
        for pat in patterns:
            for m in re.finditer(pat, message, re.IGNORECASE):
                path = m.group(1).strip('`"\'')
                if path and not path.startswith('http'):
                    mentioned.add(path)

        if not mentioned:
            return context

        additional = []
        for file_path in mentioned:
            result = await self.toolkit.execute_tool("read_file", {"path": file_path})
            if result.success and result.output:
                additional.append(f"\n\n// File: {file_path}\n{result.output[:4000]}")
                logger.info(f"[ENRICH] Read mentioned file: {file_path} ({len(result.output)} chars)")

        if additional:
            return context + "\n".join(additional)
        return context

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
