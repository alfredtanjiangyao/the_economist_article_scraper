import streamlit as st

st.set_page_config(layout="wide")

pages = [
    st.Page("user_agents_log_analysis.py", title="User Agent Performance Overview"),
    st.Page("single_user_agent_log_analysis.py", title="User Agent Performance Details"),
]

pg = st.navigation(pages)
pg.run()