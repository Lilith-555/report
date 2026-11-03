import streamlit as st

st.set_page_config(page_title="Тест", page_icon="✅", layout="wide")

st.title("✅ Приложение работает!")
st.write("Если ты это видишь — Streamlit Cloud запустился нормально.")
st.success("Минимальная версия успешно загрузилась.")

st.markdown("---")
st.write("Теперь можно возвращать полный код.")
