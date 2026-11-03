import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import re

st.set_page_config(page_title="Отчёт по качеству", page_icon="📊", layout="wide")

# ========== ПАРСЕР ==========
CRITERIA = ["мд", "рп", "грамматика", "опечатки", "систем", "контекст", "комментарий", "единообразие", "рекомендации"]

HEADERS = {
    "мд": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Маркдаун|МД|Markdown|маркдаун)(?:\*\*)?\s*[:.]"],
    "рп": [r"(?:[-*•]\s*)?(?:\*\*)?(?:РП|Редполитика|редполитика)(?:\*\*)?\s*[:.]"],
    "грамматика": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Грамматика|грамматика|орфография|пунктуация)(?:\*\*)?\s*[:.]"],
    "опечатки": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Опечатки|опечатки|Пропущенная\s+ё)(?:\*\*)?\s*[:.]"],
    "систем": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Систем|систем)(?:\*\*)?\s*[:.]"],
    "контекст": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Контекст|контекст|ты/вы)(?:\*\*)?\s*[:.]"],
    "комментарий": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Комментарий|комментарий|editingComment)(?:\*\*)?\s*[:.]"],
    "единообразие": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Единообразие|единообразие)(?:\*\*)?\s*[:.]"],
    "рекомендации": [r"(?:[-*•]\s*)?(?:\*\*)?(?:Рекомендации|рекомендации)(?:\*\*)?\s*[:.]"],
}

KEYWORDS = {
    "мд": ["иерархия", "подзаголовки", "курсив", "болд", "latex", "кодблок", "маркдаун"],
    "рп": ["повторы", "двоеточия", "эмодзи", "кавычки", "лапки", "буллиты"],
    "грамматика": ["наращений", "орфография", "пунктуация", "не те слова", "слитное", "раздельное"],
    "опечатки": ["двойные пробелы", "лишние пробелы", "пропущенная ё", "опечатка", "потерянная точка"],
    "систем": ["не core", "некорр", "nicor", "некорректный", "пд", "искажение смысла"],
    "контекст": ["ты/вы", "обращение", "гендер"],
    "комментарий": ["editingcomment", "комментарий исполнителя"],
    "единообразие": ["единообразие"],
    "рекомендации": ["висячие", "деепричастные", "штампы", "канцелярит", "перефразировать", "можно убрать"],
}

def parse_comment(text):
    res = {c: 0 for c in CRITERIA}
    if not isinstance(text, str) or not text.strip():
        return res
    t = text.lower().strip()
    if re.match(r"^(доработка|вернуть на доработку|на доработку)\.?$", t):
        return res

    found_header = False
    for crit, pats in HEADERS.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                found_header = True
                # проверяем, что после заголовка не "без ошибки"
                m = re.search(pat, text, re.IGNORECASE)
                after = text[m.end():m.end()+80].lower() if m else ""
                if "без ошибк" not in after:
                    if crit == "систем" and re.search(r"верный\s+некорр|некорр\s+проставлен\s+верно", t):
                        continue
                    res[crit] = 1
                break

    if not found_header:
        for crit, kws in KEYWORDS.items():
            for kw in kws:
                if kw in t:
                    if crit == "систем" and re.search(r"верный\s+некорр", t):
                        continue
                    res[crit] = 1
                    break
    return res

def process_df(df, comment_col):
    parsed = df[comment_col].apply(parse_comment)
    for c in CRITERIA:
        df[c] = parsed.apply(lambda x: x[c])
    error_cols = [c for c in CRITERIA if c != "рекомендации"]
    df["has_error"] = df[error_cols].sum(axis=1) > 0
    return df

# ========== ДЕМО ==========
def create_sample(n=40):
    np.random.seed(42)
    execs = [(101,"Иванов"),(102,"Петрова"),(103,"Сидоров"),(104,"Козлова")]
    comments = [
        "Маркдаун: ошибка в иерархии. Грамматика: отсутствует наращение.",
        "РП: грубые повторы. Систем: нужно было поставить NICOR.",
        "без ошибок", "Доработка",
        "Контекст: неправильное обращение. Рекомендации: лучше перефразировать.",
        "Опечатки: двойные пробелы. Грамматика: орфография.",
        "Систем: верный некорр.",
        "Единообразие: нарушение оформления.",
        "Систем: искажение смысла. Время превышено.",
        "Рекомендованное время. Грамматика: пунктуация.",
        "**Маркдаун:** иерархия. **Грамматика:** не те слова.",
        "Free form: опечатка и неправильные кавычки, а также ты/вы.",
    ]
    base = datetime(2026, 8, 1)
    rows = []
    for i in range(n):
        eid, name = execs[i % 4]
        rows.append({
            "marker_id": eid, "surname": name,
            "date": base + timedelta(days=int(np.random.randint(0,50))),
            "quality": float(np.random.choice([0.75,0.8,0.85,0.9,0.95,1.0])),
            "time_min": int(np.random.randint(20,90)),
            "reviewer_comment": str(np.random.choice(comments))
        })
    return pd.DataFrame(rows)

# ========== ИНТЕРФЕЙС ==========
st.title("📊 Отчёт по качеству")

with st.sidebar:
    st.header("Настройки")
    use_sample = st.checkbox("Демо-данные", value=True)
    uploaded = st.file_uploader("Excel / CSV", type=["xlsx","csv"], disabled=use_sample)

if use_sample:
    df = create_sample(40)
    st.info("Демо-данные. Снимите галочку, чтобы загрузить свой файл.")
else:
    if uploaded is None:
        st.warning("Загрузите файл")
        st.stop()
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)

# Определяем столбцы
cols = {c.lower(): c for c in df.columns}
comment_col = None
for key in ["reviewer_comment", "comment", "коммент", "замечан"]:
    for cl, orig in cols.items():
        if key in cl:
            comment_col = orig
            break
    if comment_col: break

id_col = None
for key in ["marker_id", "id"]:
    for cl, orig in cols.items():
        if key in cl:
            id_col = orig
            break
    if id_col: break

if comment_col is None:
    st.error("Не найден столбец с комментариями")
    st.stop()

df = df.rename(columns={comment_col: "reviewer_comment"})
if id_col:
    df = df.rename(columns={id_col: "marker_id"})
else:
    df["marker_id"] = range(len(df))

# Парсим
with st.spinner("Разбираю комментарии..."):
    df = process_df(df, "reviewer_comment")

# Метрики
total = len(df)
with_err = int(df["has_error"].sum())
c1,c2,c3,c4 = st.columns(4)
c1.metric("Всего заданий", total)
c2.metric("С ошибками", with_err, f"{with_err/total*100:.1f}%")
c3.metric("Исполнителей", df["marker_id"].nunique())
if "quality" in df.columns:
    c4.metric("Ср. качество", f"{df['quality'].mean():.2%}")
else:
    c4.metric("Ср. качество", "—")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["Ошибки по критериям", "По исполнителям", "Скачать отчёт"])

with tab1:
    st.subheader("Количество ошибок по критериям")
    sums = df[CRITERIA].sum().sort_values(ascending=False)
    st.bar_chart(sums)
    st.dataframe(pd.DataFrame({
        "критерий": CRITERIA,
        "всего": [int(df[c].sum()) for c in CRITERIA],
        "доля": [f"{df[c].mean():.1%}" for c in CRITERIA]
    }), use_container_width=True)

with tab2:
    st.subheader("Сводка по исполнителям")
    g = df.groupby("marker_id")
    summary = g[CRITERIA].sum()
    summary["всего_заданий"] = g.size()
    summary["с_ошибкой"] = g["has_error"].sum()
    st.dataframe(summary, use_container_width=True)

    sel = st.selectbox("Примеры замечаний", df["marker_id"].unique())
    sub = df[(df["marker_id"]==sel) & (df["has_error"])]
    if len(sub):
        st.dataframe(sub[["reviewer_comment"] + CRITERIA].head(10), use_container_width=True)
    else:
        st.success("Нет ошибок у этого исполнителя")

with tab3:
    st.subheader("Скачать Excel")
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="По_исполнителям")
        df.to_excel(writer, sheet_name="С_разбором", index=False)
        pd.DataFrame({"критерий": CRITERIA, "всего": [int(df[c].sum()) for c in CRITERIA]}).to_excel(writer, sheet_name="Критерии", index=False)
    st.download_button("Скачать отчёт", data=buffer.getvalue(), file_name="quality_report.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
