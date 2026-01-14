import streamlit as st
from main import main_gui, inject_security

# Este archivo existe para compatibilidad automática con Streamlit Cloud
# Si 'main.py' falla, Cloud buscará 'streamlit_app.py'

if __name__ == "__main__":
    st.set_page_config(page_title="IA TRADING INSTITUCIONAL", layout="wide", page_icon="📈", initial_sidebar_state="collapsed")
    inject_security()
    main_gui()
