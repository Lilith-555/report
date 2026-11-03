import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO

st.set_page_config(page_title="Отчёт по качеству", page_icon="📊", layout="wide")

st.title("📊 Отчёт по качеству выполнения заданий")

# ----- Демо-данные -----
def create_sample_data(n=40):
    np.random.seed(42)
    executors = [(101, "Иванов"), (102, "Петрова"), (103, "Сидоров"), (104, "Козлова")]
    comments = [
        "Маркдаун: ошибка в иерархии. Грамматика: отсутствует наращение.",
        "РП: грубые повторы. Систем: нужно было поставить NICOR.",
        "без ошибок",
        "Доработка",
        "Контекст: неправильное обращение. Рекомендации: лучше перефразировать.",
        "Опечатки: двойные пробелы.",
        "Систем: верный некорр.",
        "Единообразие: нарушение оформления.",
        "Систем: искажение смысла. Время превышено.",
        "Рекомендованное время. Грамматика: пунктуация.",
    ]
    base = datetime(2026, 8, 1)
    rows = []
    for i in range(n):
        eid, name = executors[i % 4]
        rows.append({
            "marker_id": eid,
            "surname": name,
            "date": base + timedelta(days=int(np.random.randint(0, 50))),
            "quality": float(np.random.choice([0.75, 0.8, 0.85, 0.9, 0.95, 1.0])),
            "time_min": int(np.random.randint(20, 90)),
            "reviewer_comment": str(np.random.choice(comments))
        })
    return pd.DataFrame(rows)

# ----- Сайдбар -----
with st.sidebar:
    st.header("Настройки")
    use_sample = st.checkbox("Использовать демо-данные", value=True)
    uploaded = st.file_uploader("Загрузить Excel/CSV", type=["xlsx", "csv"], disabled=use_sample)

# ----- Данные -----
if use_sample:
    df = create_sample_data(40)
    st.info("Демо-данные (40 заданий). Снимите галочку, чтобы загрузить свой файл.")
else:
    if uploaded is None:
        st.warning("Загрузите файл или включите демо-данные")
        st.stop()
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

# ----- Метрики -----
st.subheader("Основные показатели")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Всего заданий", len(df))
c2.metric("Исполнителей", df["marker_id"].nunique() if "marker_id" in df.columns else "—")
if "quality" in df.columns:
    c3.metric("Среднее качество", f"{df['quality'].mean():.2%}")
else:
    c3.metric("Среднее качество", "—")
if "time_min" in df.columns:
    c4.metric("Среднее время (мин)", f"{df['time_min'].mean():.1f}")
else:
    c4.metric("Среднее время", "—")

st.markdown("---")

# ----- Таблица -----
st.subheader("Данные")
st.dataframe(df.head(20), use_container_width=True)

# ----- Скачать -----
st.subheader("Скачать")
buffer = BytesIO()
df.to_excel(buffer, index=False, engine="openpyxl")
st.download_button(
    "Скачать Excel",
    data=buffer.getvalue(),
    file_name="report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
