"""
Shared utilities for the agent system.
Extracted to avoid circular imports between agents and orchestrator.
"""

import re


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
    """Определяет язык запроса пользователя."""
    cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))
    total = cyrillic_count + latin_count
    if total == 0:
        return 'ru'
    return 'ru' if cyrillic_count / total > 0.3 else 'en'


def sanitize_response(text: str, preserve_think: bool = True) -> str:
    """
    Убирает артефакты генерации: управляющие токены, незакрытые теги,
    повторные вопросы, которые модель генерирует после ответа.

    preserve_think=True: НЕ трогает <think> теги (orchestrator их извлечёт).
    preserve_think=False: удаляет <think> теги (для финальной очистки).
    """
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

    # Удаляем <think> блоки только если не нужно сохранять
    if not preserve_think:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'</?think>', '', text)

    # Убираем повторные "Question:" блоки в конце ответа
    # (ищем в тексте БЕЗ think-блоков для корректного определения позиции)
    clean_for_search = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    question_restart = re.search(
        r'\n(?:Question|## Question|Вопрос|<\|user\|>):\s', clean_for_search
    )
    if question_restart and question_restart.start() > len(clean_for_search) * 0.5:
        # Находим соответствующую позицию в оригинальном тексте
        text = text[:question_restart.start()]

    # Чистим множественные пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
