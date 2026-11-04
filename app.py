"""Entry point: sidebar navigation. The Today page lives in views/today.py."""
import streamlit as st

st.set_page_config(page_title="QuarterReady", page_icon="📅", layout="wide")

pages = [
    st.Page("views/today.py", title="Today", icon="🏠", default=True),
    st.Page("pages/1_Win_Leads.py", title="Win Leads", icon="🎯"),
    st.Page("pages/2_Clients.py", title="Clients", icon="🗂️"),
    st.Page("pages/3_MTD_Prep.py", title="MTD Prep", icon="📊"),
    st.Page("pages/4_Keep_Retention.py", title="Keep Retention", icon="❤️"),
    st.Page("pages/5_Evaluation_Safety.py", title="Evaluation & Safety", icon="🧪"),
]
st.navigation(pages).run()
