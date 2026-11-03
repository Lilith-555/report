"""
Парсер комментариев проверяющего по критериям ошибок.
Реализует правила из промпта пользователя.
"""

import re
from typing import Dict, List, Tuple, Optional
import pandas as pd

# Критерии
CRITERIA = [
    "мд", "рп", "грамматика", "опечатки", "систем",
    "контекст", "комментарий", "единообразие", "рекомендации"
]

# Паттерны заголовков критериев (с учётом markdown, буллетов и т.д.)
CRITERION_HEADERS = {
    "мд": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Маркдаун|МД|Markdown|маркдаун)(?:\*\*)?\s*[:.]",
        r"(?:\*\*)?Пропущенная\s+ё.*?опечатка.*?точка(?:\*\*)?",
    ],
    "рп": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:РП|Редполитика|редполитика|ошибки\s+РП)(?:\*\*)?\s*[:.]",
    ],
    "грамматика": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Грамматика|грамматика|орфография|пунктуация)(?:\*\*)?\s*[:.]",
    ],
    "опечатки": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Опечатки|опечатки|Пропущенная\s+ё|потерянная\s+точка)(?:\*\*)?\s*[:.]",
    ],
    "систем": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Систем|систем|системные)(?:\*\*)?\s*[:.]",
    ],
    "контекст": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Контекст|контекст|ты/вы|обращение)(?:\*\*)?\s*[:.]",
    ],
    "комментарий": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Комментарий|комментарий|editingComment)(?:\*\*)?\s*[:.]",
    ],
    "единообразие": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Единообразие|единообразие)(?:\*\*)?\s*[:.]",
    ],
    "рекомендации": [
        r"(?:[-*•]\s*)?(?:\*\*)?(?:Рекомендации|рекомендации|пожелания)(?:\*\*)?\s*[:.]",
    ],
}

# Ключевые слова для free-form комментариев (маппинг)
FREEFORM_KEYWORDS = {
    "мд": [
        "иерархия заголовков", "подзаголовки", "курсив", "болд", "жирный",
        "latex", "кодблок", "код-блок", "отсутствие пробелов в формулах",
        "формула latex", "markdown", "маркдаун"
    ],
    "рп": [
        "грубые повторы", "повторы однокоренных", "два двоеточия",
        "недоскрытые скобки", "эмодзи", "нумерация вместо буллитов",
        "неправильные кавычки", "лапки", "кавычки", "буллиты"
    ],
    "грамматика": [
        "буквенных наращений", "орфография", "пунктуация", "не те слова",
        "слитное", "раздельное написание", "грамматическая ошибка"
    ],
    "опечатки": [
        "двойные пробелы", "лишние пробелы", "пропущенная ё", "опечатка",
        "потерянная точка", "лишний пробел", "двойной пробел"
    ],
    "систем": [
        "не core", "это не core", "некорр", "nicor", "некорректный",
        "нельзя было редактировать", "нужно было поставить nicor",
        "стоило поставить некорр", "nicor проставлен неверно",
        "персональные данные", "пд", "искажение смысла",
        "банальные фразы", "бф", "эмпатия", "восторженность",
        "ложные обещания", "отправить в некорр"
    ],
    "контекст": [
        "ты/вы", "обращение", "гендер", "неправильное обращение",
        "ты ", "вы "
    ],
    "комментарий": [
        "editingcomment", "комментарий исполнителя", "ошибка в комментарии"
    ],
    "единообразие": [
        "единообразие", "нарушение единообразия", "оформление"
    ],
    "рекомендации": [
        "висячие предложения", "разделители", "деепричастные обороты",
        "отглагольные существительные", "штампы", "усилители", "канцелярит",
        "лучше перефразировать", "можно убрать", "мягкие пожелания"
    ],
}

# Исключения для "систем" (не ошибка)
SYSTEM_EXCEPTIONS = [
    r"верный\s+некорр",
    r"некорр\s+проставлен\s+верно",
    r"некорр\s+не\s+ставим",
    r"верный\s+nicor",
]

# Фразы, которые игнорируем полностью (короткие "доработка")
IGNORE_PHRASES = [
    r"^доработка\.?$",
    r"^вернуть\s+на\s+доработку\.?$",
    r"^на\s+доработку\.?$",
    r"^доработать\.?$",
]


def normalize_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    text = text.lower().strip()
    # Убираем лишние markdown
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"`+", "", text)
    return text


def is_ignore_comment(text: str) -> bool:
    t = normalize_text(text)
    for pat in IGNORE_PHRASES:
        if re.match(pat, t):
            return True
    return False


def has_system_exception(text: str) -> bool:
    t = normalize_text(text)
    for pat in SYSTEM_EXCEPTIONS:
        if re.search(pat, t):
            return True
    return False


def extract_section(text: str, criterion: str) -> Optional[str]:
    """Извлекает текст после заголовка критерия до следующего заголовка или конца."""
    patterns = CRITERION_HEADERS.get(criterion, [])
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if match:
            start = match.end()
            # Ищем следующий критерий
            next_starts = []
            for other_crit, other_pats in CRITERION_HEADERS.items():
                if other_crit == criterion:
                    continue
                for op in other_pats:
                    m2 = re.search(op, text[start:], re.IGNORECASE | re.DOTALL)
                    if m2:
                        next_starts.append(start + m2.start())
            end = min(next_starts) if next_starts else len(text)
            section = text[start:end].strip()
            # Если "без ошибки" / "без ошибок" / пусто
            if not section or re.search(r"без\s+ошибк", section, re.IGNORECASE):
                return None
            return section
    return None


def has_error_in_section(section: Optional[str]) -> bool:
    if not section:
        return False
    # Уже проверили "без ошибки"
    return True


def freeform_match(text: str) -> Dict[str, int]:
    """Если нет разбивки по критериям — ищем ключевые слова."""
    result = {c: 0 for c in CRITERIA}
    t = normalize_text(text)
    if not t or is_ignore_comment(t):
        return result

    for crit, keywords in FREEFORM_KEYWORDS.items():
        for kw in keywords:
            if kw in t:
                # Особый случай для систем
                if crit == "систем" and has_system_exception(t):
                    continue
                result[crit] = 1
                break
    return result


def parse_comment(comment: str) -> Dict[str, int]:
    """
    Возвращает словарь {критерий: 0/1} для одного комментария.
    1 = в этом задании есть ошибка по критерию.
    """
    result = {c: 0 for c in CRITERIA}
    if not isinstance(comment, str) or not comment.strip():
        return result

    if is_ignore_comment(comment):
        return result

    text = comment  # сохраняем оригинал для regex

    # Проверяем, есть ли хоть один заголовок критерия
    has_any_header = False
    for crit in CRITERIA:
        section = extract_section(text, crit)
        if section is not None:
            has_any_header = True
            if has_error_in_section(section):
                if crit == "систем" and has_system_exception(section):
                    result[crit] = 0
                else:
                    result[crit] = 1

    if not has_any_header:
        # Free-form
        result = freeform_match(text)

    return result


def parse_time_info(comment: str) -> Dict[str, Optional[str]]:
    """
    Извлекает информацию о времени из комментария.
    Возвращает: status ('recommended' / 'acceptable' / 'exceeded' / None), raw_text
    """
    if not isinstance(comment, str):
        return {"status": None, "raw": None}

    t = comment.lower()
    status = None
    raw = None

    # Паттерны (порядок важен — сначала более специфичные)
    patterns = [
        (r"(превышен[оаеы]?\s*(?:время|лимит|норма)|время\s*превышен|сверх\s*нормы|over\s*time)", "exceeded"),
        (r"(допустим[оаеы]?\s*время|в\s*пределах\s*допустим|acceptable)", "acceptable"),
        (r"(рекомендованн[оаеы]?\s*время|в\s*рекомендованн|recommended\s*time|норма\s*времени)", "recommended"),
        (r"(время\s*выполнения[:\s]+[\d\.,]+\s*(?:мин|час|h|m)?)", "mentioned"),
    ]

    for pat, st in patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            status = st
            raw = m.group(0)
            break

    return {"status": status, "raw": raw}


def process_dataframe(df: pd.DataFrame, comment_col: str = "reviewer_comment") -> pd.DataFrame:
    """
    Добавляет к DataFrame столбцы по каждому критерию + time_status.
    """
    if comment_col not in df.columns:
        raise ValueError(f"Столбец '{comment_col}' не найден")

    parsed = df[comment_col].apply(parse_comment)
    for c in CRITERIA:
        df[c] = parsed.apply(lambda x: x[c])

    time_info = df[comment_col].apply(parse_time_info)
    df["time_status"] = time_info.apply(lambda x: x["status"])
    df["time_raw"] = time_info.apply(lambda x: x["raw"])

    # Есть ли хотя бы одна ошибка (без рекомендаций)
    error_cols = [c for c in CRITERIA if c != "рекомендации"]
    df["has_error"] = df[error_cols].sum(axis=1) > 0

    return df


def aggregate_by_executor(df: pd.DataFrame, id_col: str = "marker_id", name_col: str = "surname") -> pd.DataFrame:
    """Сводная по исполнителям."""
    group_cols = [id_col]
    if name_col in df.columns:
        group_cols.append(name_col)

    agg = {c: "sum" for c in CRITERIA}
    agg["has_error"] = "sum"  # кол-во заданий с ошибками
    agg[id_col] = "count"     # всего заданий

    summary = df.groupby(group_cols, dropna=False).agg(agg).reset_index()
    summary = summary.rename(columns={id_col: "всего_заданий" if id_col not in group_cols else id_col})
    # Исправляем переименование
    summary = summary.rename(columns={id_col: "всего_заданий"})
    # На самом деле count идёт в столбец с именем id_col после rename — поправим
    # Лучше переписать чисто

    return summary


def make_executor_summary(df: pd.DataFrame, id_col: str = "marker_id", name_col: Optional[str] = "surname") -> pd.DataFrame:
    """Чистая сводная таблица по исполнителям."""
    cols = [id_col]
    if name_col and name_col in df.columns:
        cols.append(name_col)

    g = df.groupby(cols, dropna=False)
    result = g[CRITERIA].sum().reset_index()
    result["всего_заданий"] = g.size().values
    result["заданий_с_ошибкой"] = g["has_error"].sum().values

    # ИТОГО
    total_row = {c: result[c].sum() for c in CRITERIA}
    total_row[id_col] = "ИТОГО"
    if name_col and name_col in result.columns:
        total_row[name_col] = ""
    total_row["всего_заданий"] = result["всего_заданий"].sum()
    # для ИТОГО "заданий_с_ошибкой" = число заданий с хотя бы одной ошибкой (уникальные строки)
    total_row["заданий_с_ошибкой"] = df["has_error"].sum()

    result = pd.concat([result, pd.DataFrame([total_row])], ignore_index=True)
    return result
