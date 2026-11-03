"""
Сервис отчётов по качеству выполнения заданий.
Локальное Streamlit-приложение.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from io import BytesIO
import re

from comment_parser import (
    CRITERIA, process_dataframe, make_executor_summary,
    parse_comment, parse_time_info
)

st.set_page_config(
    page_title="Отчёт по качеству",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Стили ----------
st.markdown("""
<style>
    .main-header {font-size: 2rem; font-weight: 700; color: #1f77b4; margin-bottom: 0.5rem;}
    .sub-header {font-size: 1.2rem; color: #555; margin-bottom: 1.5rem;}
    .metric-card {background: #f8f9fa; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #1f77b4;}
    .stDownloadButton button {width: 100%;}
</style>
""", unsafe_allow_html=True)


# ---------- Вспомогательные функции ----------
def detect_columns(df: pd.DataFrame) -> dict:
    """Автоопределение столбцов по возможным названиям."""
    mapping = {}
    col_lower = {c: str(c).lower().strip() for c in df.columns}

    # marker_id
    for c, cl in col_lower.items():
        if any(x in cl for x in ["marker_id", "marker id", "id исполнителя", "исполнитель id", "id"]):
            mapping["marker_id"] = c
            break
    if "marker_id" not in mapping:
        for c, cl in col_lower.items():
            if "id" in cl and "marker" not in cl:
                mapping["marker_id"] = c
                break

    # surname
    for c, cl in col_lower.items():
        if any(x in cl for x in ["surname", "фамилия", "исполнитель", "name", "фио"]):
            mapping["surname"] = c
            break

    # date
    for c, cl in col_lower.items():
        if any(x in cl for x in ["date", "дата", "дата выполнения", "completed", "выполнен"]):
            mapping["date"] = c
            break

    # quality
    for c, cl in col_lower.items():
        if any(x in cl for x in ["quality", "качество", "оценка", "score", "балл"]):
            mapping["quality"] = c
            break

    # time
    for c, cl in col_lower.items():
        if any(x in cl for x in ["time", "время", "duration", "длительность", "мин"]):
            mapping["time"] = c
            break

    # comment
    for c, cl in col_lower.items():
        if any(x in cl for x in ["comment", "коммент", "reviewer", "проверяющ", "замечан"]):
            mapping["comment"] = c
            break

    return mapping


def to_week_start(dt):
    """Понедельник недели."""
    if pd.isna(dt):
        return pd.NaT
    return dt - pd.Timedelta(days=dt.weekday())


def create_sample_data(n=80) -> pd.DataFrame:
    """Генерирует тестовые данные для демонстрации."""
    np.random.seed(42)
    executors = [
        (101, "Иванов"), (102, "Петрова"), (103, "Сидоров"),
        (104, "Козлова"), (105, "Морозов"), (106, "Васильева")
    ]
    comments_pool = [
        "Маркдаун: ошибка в иерархии заголовков. Грамматика: отсутствует наращение. Опечатки: пропущенная ё.",
        "РП: грубые повторы. Систем: нужно было поставить NICOR.",
        "без ошибок",
        "Доработка",
        "Контекст: неправильное обращение (ты вместо вы). Рекомендации: лучше перефразировать висячее предложение.",
        "Опечатки: двойные пробелы. Грамматика: орфография.",
        "Систем: верный некорр. Рекомендации: можно убрать канцелярит.",
        "Единообразие: нарушение оформления списков. Комментарий: ошибка в editingComment.",
        "Маркдаун: отсутствие пробелов в LaTeX. РП: эмодзи лишние.",
        "Систем: искажение смысла + ПД. Время превышено.",
        "Рекомендованное время. Грамматика: пунктуация.",
        "Допустимое время. Опечатки: потерянная точка.",
        "Превышено время выполнения. Систем: это не core.",
        "**Маркдаун:** иерархия. **Грамматика:** не те слова.",
        "- Маркдаун: кодблоки. - Систем: NICOR проставлен неверно.",
        "Free form: опечатка и неправильные кавычки, а также ты/вы.",
        "без ошибки по всем критериям",
        "Рекомендации: штампы и усилители. Время в норме.",
        "РП: два двоеточия подряд. Контекст: гендер.",
        "Систем: нельзя было редактировать. Время: превышено."
    ]
    qualities = [0.7, 0.8, 0.85, 0.9, 0.95, 1.0, 0.75, 0.88]
    base_date = datetime(2026, 8, 1)

    rows = []
    for i in range(n):
        eid, sname = executors[i % len(executors)]
        days = np.random.randint(0, 90)
        d = base_date + timedelta(days=days)
        q = float(np.random.choice(qualities))
        t_min = np.random.randint(15, 120)
        comment = np.random.choice(comments_pool)
        rows.append({
            "marker_id": eid,
            "surname": sname,
            "date": d,
            "quality": q,
            "time_min": t_min,
            "reviewer_comment": comment
        })
    return pd.DataFrame(rows)


def create_sample_events() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-08-15", "2026-09-01", "2026-09-20", "2026-10-05"]),
        "type": ["индивидуальная", "малая группа", "индивидуальная", "малая группа"],
        "participants": ["Иванов", "Петрова, Сидоров", "Козлова", "Морозов, Васильева, Иванов"],
        "topic": ["Разбор системных ошибок", "Единообразие и РП", "Контекст и обращение", "Опечатки и грамматика"],
        "result": ["Улучшение по систем", "Снижение ошибок РП", "Закрепление", "Практика"]
    })


def df_to_excel_bytes(dfs: dict) -> bytes:
    """Несколько листов в один Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()


# ---------- Sidebar ----------
st.sidebar.title("⚙️ Настройки")
st.sidebar.markdown("---")

use_sample = st.sidebar.checkbox("Использовать демо-данные", value=True,
                                  help="Для первого запуска и тестирования")

uploaded_file = st.sidebar.file_uploader(
    "Основная таблица заданий (.xlsx)",
    type=["xlsx", "xls", "csv"],
    disabled=use_sample
)

uploaded_events = st.sidebar.file_uploader(
    "Файл мероприятий / ВКС (опционально)",
    type=["xlsx", "xls", "csv"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Соответствие столбцов")
st.sidebar.caption("Если автоопределение не сработало — укажи вручную после загрузки")

# ---------- Main ----------
st.markdown('<div class="main-header">📊 Отчёт по качеству выполнения заданий</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Загрузите исходную таблицу → получите динамику, ошибки по критериям, исполнителей и мероприятия</div>', unsafe_allow_html=True)

# Загрузка данных
df = None
events_df = None

if use_sample:
    df = create_sample_data(100)
    events_df = create_sample_events()
    st.info("Используются демо-данные (100 заданий, 6 исполнителей, 4 мероприятия). Снимите галочку слева, чтобы загрузить свои файлы.")
else:
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Ошибка чтения файла: {e}")
            st.stop()
    else:
        st.warning("Загрузите Excel-файл с заданиями в боковой панели или включите демо-данные.")
        st.stop()

    if uploaded_events is not None:
        try:
            if uploaded_events.name.endswith(".csv"):
                events_df = pd.read_csv(uploaded_events)
            else:
                events_df = pd.read_excel(uploaded_events)
        except Exception as e:
            st.warning(f"Не удалось прочитать файл мероприятий: {e}")

# Определяем столбцы
col_map = detect_columns(df)
st.sidebar.write("Автоопределённые столбцы:")
st.sidebar.json(col_map)

# Позволяем пользователю переопределить
with st.sidebar.expander("Переопределить столбцы"):
    id_col = st.selectbox("ID исполнителя", options=df.columns.tolist(),
                          index=df.columns.tolist().index(col_map.get("marker_id", df.columns[0])) if col_map.get("marker_id") in df.columns else 0)
    name_col = st.selectbox("Фамилия / имя", options=["(нет)"] + df.columns.tolist(),
                            index=(["(нет)"] + df.columns.tolist()).index(col_map.get("surname", "(нет)")) if col_map.get("surname") else 0)
    date_col = st.selectbox("Дата", options=["(нет)"] + df.columns.tolist(),
                            index=(["(нет)"] + df.columns.tolist()).index(col_map.get("date", "(нет)")) if col_map.get("date") else 0)
    quality_col = st.selectbox("Качество", options=["(нет)"] + df.columns.tolist(),
                               index=(["(нет)"] + df.columns.tolist()).index(col_map.get("quality", "(нет)")) if col_map.get("quality") else 0)
    time_col = st.selectbox("Время (мин)", options=["(нет)"] + df.columns.tolist(),
                            index=(["(нет)"] + df.columns.tolist()).index(col_map.get("time", "(нет)")) if col_map.get("time") else 0)
    comment_col = st.selectbox("Комментарий проверяющего", options=df.columns.tolist(),
                               index=df.columns.tolist().index(col_map.get("comment", df.columns[-1])) if col_map.get("comment") in df.columns else len(df.columns)-1)

# Применяем выбранные
if name_col == "(нет)":
    name_col = None
if date_col == "(нет)":
    date_col = None
if quality_col == "(нет)":
    quality_col = None
if time_col == "(нет)":
    time_col = None

# Подготовка данных
df = df.copy()
df = df.rename(columns={id_col: "marker_id", comment_col: "reviewer_comment"})
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

# Парсинг комментариев
with st.spinner("Разбираю комментарии по критериям..."):
    df = process_dataframe(df, comment_col="reviewer_comment")

# Добавляем неделю
if "date" in df.columns and df["date"].notna().any():
    df["week"] = df["date"].apply(to_week_start)
else:
    df["week"] = pd.NaT

# ---------- Метрики верхнего уровня ----------
total_tasks = len(df)
tasks_with_error = int(df["has_error"].sum())
error_rate = tasks_with_error / total_tasks * 100 if total_tasks else 0
avg_quality = df["quality"].mean() if "quality" in df.columns else None
unique_executors = df["marker_id"].nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Всего заданий", total_tasks)
c2.metric("С ошибками", tasks_with_error, f"{error_rate:.1f}%")
c3.metric("Исполнителей", unique_executors)
if avg_quality is not None:
    c4.metric("Среднее качество", f"{avg_quality:.2%}" if avg_quality <= 1 else f"{avg_quality:.2f}")
else:
    c4.metric("Среднее качество", "—")
rec_count = (df["time_status"] == "recommended").sum()
exc_count = (df["time_status"] == "exceeded").sum()
c5.metric("Превышено время", int(exc_count), f"рек. {int(rec_count)}")

st.markdown("---")

# ---------- Вкладки ----------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Динамика качества",
    "❌ Ошибки по критериям",
    "👤 По исполнителям",
    "⏱ Время",
    "📅 Мероприятия (ВКС)",
    "📥 Скачать отчёт"
])

# ===== TAB 1: Динамика =====
with tab1:
    st.subheader("Качество во времени (по неделям)")

    if "date" in df.columns and df["date"].notna().any() and "quality" in df.columns:
        weekly = df.dropna(subset=["week"]).groupby("week").agg(
            avg_quality=("quality", "mean"),
            tasks=("marker_id", "count"),
            error_rate=("has_error", "mean")
        ).reset_index().sort_values("week")

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(x=weekly["week"], y=weekly["avg_quality"], name="Среднее качество",
                       mode="lines+markers", line=dict(color="#1f77b4", width=3)),
            secondary_y=False
        )
        fig.add_trace(
            go.Bar(x=weekly["week"], y=weekly["error_rate"] * 100, name="% заданий с ошибками",
                   marker_color="rgba(255, 99, 71, 0.5)"),
            secondary_y=True
        )
        fig.update_layout(title="Качество и доля ошибок по неделям", height=450,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        fig.update_yaxes(title_text="Качество", secondary_y=False)
        fig.update_yaxes(title_text="% с ошибками", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(weekly.style.format({
            "avg_quality": "{:.2%}" if weekly["avg_quality"].max() <= 1 else "{:.2f}",
            "error_rate": "{:.1%}"
        }), use_container_width=True)
    else:
        st.warning("Нет столбца даты или качества — динамика недоступна.")

# ===== TAB 2: Ошибки по критериям =====
with tab2:
    st.subheader("Количество ошибок по критериям")

    # Общий подсчёт
    total_by_crit = df[CRITERIA].sum().sort_values(ascending=False)
    fig_bar = px.bar(
        x=total_by_crit.index, y=total_by_crit.values,
        labels={"x": "Критерий", "y": "Кол-во заданий с ошибкой"},
        title="Всего ошибок по критериям (за весь период)",
        color=total_by_crit.values, color_continuous_scale="Reds"
    )
    fig_bar.update_layout(height=400)
    st.plotly_chart(fig_bar, use_container_width=True)

    # По неделям
    if "week" in df.columns and df["week"].notna().any():
        st.subheader("Ошибки по критериям × недели (heatmap)")
        week_crit = df.dropna(subset=["week"]).groupby("week")[CRITERIA].sum().T
        fig_hm = px.imshow(
            week_crit,
            labels=dict(x="Неделя", y="Критерий", color="Кол-во"),
            aspect="auto", color_continuous_scale="YlOrRd",
            title="Тепловая карта ошибок"
        )
        fig_hm.update_layout(height=450)
        st.plotly_chart(fig_hm, use_container_width=True)

    # Детальная таблица
    st.subheader("Сводная по критериям")
    crit_summary = pd.DataFrame({
        "критерий": CRITERIA,
        "всего_ошибок": [df[c].sum() for c in CRITERIA],
        "доля_заданий": [df[c].mean() for c in CRITERIA]
    })
    st.dataframe(crit_summary.style.format({"доля_заданий": "{:.1%}"}), use_container_width=True)

# ===== TAB 3: По исполнителям =====
with tab3:
    st.subheader("Ошибки каждого исполнителя")

    exec_summary = make_executor_summary(df, id_col="marker_id", name_col="surname" if "surname" in df.columns else None)
    st.dataframe(exec_summary, use_container_width=True)

    # Топ проблемных
    if "surname" in df.columns:
        top = exec_summary[exec_summary["marker_id"] != "ИТОГО"].copy()
        top["error_share"] = top["заданий_с_ошибкой"] / top["всего_заданий"]
        top = top.sort_values("error_share", ascending=False).head(10)

        fig_top = px.bar(
            top, x="surname", y="error_share",
            title="Доля заданий с ошибками по исполнителям (топ)",
            labels={"error_share": "Доля с ошибками", "surname": "Исполнитель"},
            color="error_share", color_continuous_scale="OrRd"
        )
        fig_top.update_layout(height=400)
        st.plotly_chart(fig_top, use_container_width=True)

    # Детализация: причины (примеры комментариев с ошибками)
    st.subheader("Примеры замечаний по исполнителям")
    selected_exec = st.selectbox(
        "Выберите исполнителя",
        options=df["marker_id"].unique().tolist()
    )
    subset = df[(df["marker_id"] == selected_exec) & (df["has_error"])]
    if len(subset) > 0:
        show_cols = ["date", "quality", "reviewer_comment"] + [c for c in CRITERIA if subset[c].sum() > 0]
        show_cols = [c for c in show_cols if c in subset.columns]
        st.dataframe(subset[show_cols].head(20), use_container_width=True)
    else:
        st.success("У этого исполнителя нет заданий с ошибками в загруженных данных.")

# ===== TAB 4: Время =====
with tab4:
    st.subheader("Анализ времени выполнения")

    if "time_min" in df.columns and df["time_min"].notna().any():
        c1, c2, c3 = st.columns(3)
        c1.metric("Среднее время (мин)", f"{df['time_min'].mean():.1f}")
        c2.metric("Медиана", f"{df['time_min'].median():.1f}")
        c3.metric("Макс", f"{df['time_min'].max():.0f}")

        fig_time = px.histogram(df, x="time_min", nbins=20, title="Распределение времени выполнения")
        st.plotly_chart(fig_time, use_container_width=True)

        if "surname" in df.columns:
            time_by_exec = df.groupby("surname")["time_min"].agg(["mean", "median", "count"]).reset_index()
            st.dataframe(time_by_exec.style.format({"mean": "{:.1f}", "median": "{:.1f}"}), use_container_width=True)
    else:
        st.info("Столбец времени не найден или пуст.")

    st.subheader("Статус времени из комментариев")
    time_status_counts = df["time_status"].value_counts(dropna=False).rename({
        "recommended": "Рекомендованное",
        "acceptable": "Допустимое",
        "exceeded": "Превышено",
        "mentioned": "Упомянуто",
        None: "Не указано"
    })
    fig_ts = px.pie(values=time_status_counts.values, names=time_status_counts.index,
                    title="Статус времени по комментариям")
    st.plotly_chart(fig_ts, use_container_width=True)

    exceeded = df[df["time_status"] == "exceeded"]
    if len(exceeded) > 0:
        st.warning(f"Заданий с превышением времени: {len(exceeded)}")
        show = ["marker_id", "surname", "date", "time_min", "time_raw", "reviewer_comment"]
        show = [c for c in show if c in exceeded.columns]
        st.dataframe(exceeded[show].head(15), use_container_width=True)

# ===== TAB 5: Мероприятия =====
with tab5:
    st.subheader("Мероприятия (ВКС): индивидуальные и малые группы")

    if events_df is not None and len(events_df) > 0:
        st.dataframe(events_df, use_container_width=True)

        # Простая статистика
        if "type" in events_df.columns:
            type_counts = events_df["type"].value_counts()
            fig_ev = px.pie(values=type_counts.values, names=type_counts.index, title="Типы мероприятий")
            st.plotly_chart(fig_ev, use_container_width=True)
    else:
        st.info("Файл мероприятий не загружен. Можно добавить вручную ниже или загрузить в сайдбаре.")

        # Ручной ввод
        with st.form("add_event"):
            st.write("Добавить мероприятие")
            e_date = st.date_input("Дата")
            e_type = st.selectbox("Тип", ["индивидуальная", "малая группа"])
            e_part = st.text_input("Участники")
            e_topic = st.text_input("Тема")
            e_res = st.text_input("Результат / эффект")
            if st.form_submit_button("Добавить (в сессию)"):
                new_row = pd.DataFrame([{
                    "date": e_date, "type": e_type,
                    "participants": e_part, "topic": e_topic, "result": e_res
                }])
                if events_df is None:
                    events_df = new_row
                else:
                    events_df = pd.concat([events_df, new_row], ignore_index=True)
                st.success("Добавлено (для постоянного хранения сохраните через скачивание отчёта)")

# ===== TAB 6: Скачать =====
with tab6:
    st.subheader("Скачать готовый отчёт")

    exec_sum = make_executor_summary(df, "marker_id", "surname" if "surname" in df.columns else None)
    crit_sum = pd.DataFrame({
        "критерий": CRITERIA,
        "всего": [int(df[c].sum()) for c in CRITERIA]
    })

    weekly_df = pd.DataFrame()
    if "week" in df.columns and df["week"].notna().any() and "quality" in df.columns:
        weekly_df = df.dropna(subset=["week"]).groupby("week").agg(
            avg_quality=("quality", "mean"),
            tasks=("marker_id", "count"),
            error_rate=("has_error", "mean"),
            **{c: (c, "sum") for c in CRITERIA}
        ).reset_index()

    sheets = {
        "Сводка_исполнители": exec_sum,
        "Критерии_всего": crit_sum,
        "Исходные_с_разбором": df,
    }
    if not weekly_df.empty:
        sheets["По_неделям"] = weekly_df
    if events_df is not None:
        sheets["Мероприятия"] = events_df

    excel_bytes = df_to_excel_bytes(sheets)

    st.download_button(
        label="📥 Скачать полный Excel-отчёт",
        data=excel_bytes,
        file_name=f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("---")
    st.markdown("### Что внутри отчёта")
    st.markdown("""
    - **Сводка_исполнители** — по каждому marker_id / фамилии: сумма ошибок по критериям, всего заданий, заданий с ошибкой  
    - **Критерии_всего** — общие суммы по критериям  
    - **По_неделям** — качество, % ошибок и ошибки по критериям в динамике  
    - **Исходные_с_разбором** — исходные строки + флаги 0/1 по каждому критерию + time_status  
    - **Мероприятия** — если были загружены / добавлены  
    """)

    st.success("Готово! Можешь использовать этот отчёт для руководства.")

# ---------- Footer ----------
st.markdown("---")
st.caption("Сервис для вайб-кодинга отчётов · парсер комментариев по правилам критериев · локально на Streamlit")
