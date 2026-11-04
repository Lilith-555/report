import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO
import re

st.set_page_config(page_title="Отчёт по качеству", page_icon="📊", layout="wide")

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
    if re.match(r"^(доработка|вернуть на доработку|на доработку|доработать)(\s*\(.*\))?\.?$", t):
        return res
    if t.startswith("доработка") and len(t) < 70:
        return res
    found_header = False
    for crit, pats in HEADERS.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                found_header = True
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

def parse_time_status(text):
    if not isinstance(text, str):
        return None
    t = text.lower()
    if re.search(r"превышен[оаеы]?\s*(время|лимит|норма)|время\s*превышен|сверх\s*нормы", t):
        return "Превышено"
    if re.search(r"допустим[оаеы]?\s*время|в\s*пределах\s*допустим", t):
        return "Допустимое"
    if re.search(r"рекомендованн[оаеы]?\s*время|в\s*рекомендованн|норма\s*времени", t):
        return "Рекомендованное"
    return None

def process_df(df, comment_col):
    parsed = df[comment_col].apply(parse_comment)
    for c in CRITERIA:
        df[c] = parsed.apply(lambda x: x[c])
    df["time_status"] = df[comment_col].apply(parse_time_status)
    error_cols = [c for c in CRITERIA if c != "рекомендации"]
    df["has_error"] = df[error_cols].sum(axis=1) > 0
    return df

def to_week(dt):
    if pd.isna(dt):
        return pd.NaT
    return dt - pd.Timedelta(days=dt.weekday())

def create_sample(n=50):
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
        "доработка (в болд взять)",
        "Допустимое время. Опечатки: потерянная точка.",
    ]
    base = datetime(2026, 8, 1)
    rows = []
    for i in range(n):
        eid, name = execs[i % 4]
        rows.append({
            "marker_id": eid, "surname": name,
            "date": base + timedelta(days=int(np.random.randint(0, 70))),
            "quality": float(np.random.choice([0.75,0.8,0.85,0.9,0.95,1.0])),
            "time_min": int(np.random.randint(20,90)),
            "reviewer_comment": str(np.random.choice(comments))
        })
    return pd.DataFrame(rows)

st.title("📊 Отчёт по качеству")

with st.sidebar:
    st.header("Настройки")
    use_sample = st.checkbox("Демо-данные", value=True)
    uploaded = st.file_uploader("Excel / CSV с заданиями", type=["xlsx","csv"], disabled=use_sample)
    uploaded_events = st.file_uploader("Мероприятия / ВКС (опционально)", type=["xlsx","csv"])

if use_sample:
    df = create_sample(50)
    events_df = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-15","2026-09-01","2026-09-20","2026-10-05"]),
        "type": ["индивидуальная","малая группа","индивидуальная","малая группа"],
        "participants": ["Иванов","Петрова, Сидоров","Козлова","Морозов, Васильева"],
        "topic": ["Системные ошибки","Единообразие и РП","Контекст","Опечатки и грамматика"],
        "result": ["Улучшение","Снижение ошибок РП","Закрепление","Практика"]
    })
    st.info("Демо-данные. Снимите галочку, чтобы загрузить свои файлы.")
else:
    if uploaded is None:
        st.warning("Загрузите файл с заданиями")
        st.stop()
    df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
    events_df = None
    if uploaded_events is not None:
        events_df = pd.read_csv(uploaded_events) if uploaded_events.name.endswith(".csv") else pd.read_excel(uploaded_events)

cols = {str(c).lower(): c for c in df.columns}
def find_col(keys):
    for key in keys:
        for cl, orig in cols.items():
            if key in cl:
                return orig
    return None

comment_col = find_col(["reviewer_comment", "comment", "коммент", "замечан"])
id_col = find_col(["marker_id", "id"])
name_col = find_col(["surname", "фамилия", "исполнитель", "фио", "name"])
date_col = find_col(["date", "дата"])
quality_col = find_col(["quality", "качество", "оценка"])
time_col = find_col(["time_min", "time", "время"])

if comment_col is None:
    st.error("Не найден столбец с комментариями")
    st.stop()

df = df.rename(columns={comment_col: "reviewer_comment"})
if id_col:
    df = df.rename(columns={id_col: "marker_id"})
else:
    df["marker_id"] = range(len(df))
if name_col:
    df = df.rename(columns={name_col: "surname"})
if date_col:
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
if quality_col:
    df = df.rename(columns={quality_col: "quality"})
    df["quality"] = pd.to_numeric(df["quality"], errors="coerce")
if time_col:
    df = df.rename(columns={time_col: "time_min"})
    df["time_min"] = pd.to_numeric(df["time_min"], errors="coerce")

with st.spinner("Разбираю комментарии..."):
    df = process_df(df, "reviewer_comment")

if "date" in df.columns and df["date"].notna().any():
    df["week"] = df["date"].apply(to_week)
else:
    df["week"] = pd.NaT

total = len(df)
with_err = int(df["has_error"].sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Всего заданий", total)
c2.metric("С ошибками", with_err, f"{with_err/total*100:.1f}%")
c3.metric("Исполнителей", df["marker_id"].nunique())
if "quality" in df.columns:
    c4.metric("Ср. качество", f"{df['quality'].mean():.2%}")
else:
    c4.metric("Ср. качество", "—")

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Динамика", "❌ Ошибки по критериям", "👤 По исполнителям", "⏱ Время и мероприятия", "📥 Скачать"])

with tab1:
    st.subheader("Качество и ошибки по неделям")
    if "week" in df.columns and df["week"].notna().any():
        weekly = df.dropna(subset=["week"]).groupby("week").agg(
            tasks=("marker_id", "count"),
            error_rate=("has_error", "mean")
        ).reset_index().sort_values("week")
        if "quality" in df.columns:
            weekly["avg_quality"] = df.dropna(subset=["week"]).groupby("week")["quality"].mean().values
            st.line_chart(weekly.set_index("week")[["avg_quality"]])
        st.bar_chart(weekly.set_index("week")[["error_rate"]])
        st.dataframe(weekly, use_container_width=True)
    else:
        st.info("Нет дат — динамика недоступна")

with tab2:
    st.subheader("Ошибки по критериям")
    sums = df[CRITERIA].sum().sort_values(ascending=False)
    st.bar_chart(sums)
    st.dataframe(pd.DataFrame({
        "критерий": CRITERIA,
        "всего": [int(df[c].sum()) for c in CRITERIA],
        "доля": [f"{df[c].mean():.1%}" for c in CRITERIA]
    }), use_container_width=True)
    if "week" in df.columns and df["week"].notna().any():
        st.subheader("Ошибки по критериям × недели")
        week_crit = df.dropna(subset=["week"]).groupby("week")[CRITERIA].sum()
        st.dataframe(week_crit, use_container_width=True)

with tab3:
    st.subheader("Сводка по исполнителям")
    group_cols = ["marker_id"]
    if "surname" in df.columns:
        group_cols.append("surname")
    g = df.groupby(group_cols)
    summary = g[CRITERIA].sum()
    summary["всего_заданий"] = g.size()
    summary["с_ошибкой"] = g["has_error"].sum()
    st.dataframe(summary, use_container_width=True)
    sel = st.selectbox("Примеры замечаний", df["marker_id"].unique())
    sub = df[(df["marker_id"] == sel) & (df["has_error"])]
    if len(sub) > 0:
        st.dataframe(sub[["reviewer_comment"] + CRITERIA].head(15), use_container_width=True)
    else:
        st.success("Нет ошибок у этого исполнителя")

with tab4:
    st.subheader("Время выполнения")
    if "time_min" in df.columns and df["time_min"].notna().any():
        c1, c2, c3 = st.columns(3)
        c1.metric("Среднее (мин)", f"{df['time_min'].mean():.1f}")
        c2.metric("Медиана", f"{df['time_min'].median():.1f}")
        c3.metric("Макс", f"{df['time_min'].max():.0f}")
    else:
        st.info("Столбец времени не найден")
    st.subheader("Статус времени из комментариев")
    time_counts = df["time_status"].value_counts(dropna=False).rename({None: "Не указано"})
    st.write(time_counts)
    exceeded = df[df["time_status"] == "Превышено"]
    if len(exceeded) > 0:
        st.warning(f"Заданий с превышением времени: {len(exceeded)}")
        st.dataframe(exceeded[["marker_id", "reviewer_comment"]].head(10), use_container_width=True)
    st.subheader("Мероприятия (ВКС)")
    if events_df is not None and len(events_df) > 0:
        st.dataframe(events_df, use_container_width=True)
    else:
        st.info("Файл мероприятий не загружен")

with tab5:
    st.subheader("Скачать Excel-отчёт")
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="По_исполнителям")
        df.to_excel(writer, sheet_name="С_разбором", index=False)
        pd.DataFrame({"критерий": CRITERIA, "всего": [int(df[c].sum()) for c in CRITERIA]}).to_excel(writer, sheet_name="Критерии", index=False)
        if events_df is not None:
            events_df.to_excel(writer, sheet_name="Мероприятия", index=False)
    st.download_button("📥 Скачать отчёт", data=buffer.getvalue(),
                       file_name=f"quality_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
