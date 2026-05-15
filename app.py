import streamlit as st
from data_rules import RULES_BIAT_2023

st.set_page_config(page_title="BIAT Simulator", layout="wide")

st.title("🏦- Simulateur De Segmentation Client BIAT")

tab1, tab2 = st.tabs(["📊 Simulateur", "🤖 Chatbot"])

with tab1:
    st.header("Simulateur")
    with open("simulateur_biat_v5.py", "r", encoding="utf-8") as f:
        exec(f.read())

with tab2:
    st.header("Chatbot")
    with open("chatbot_biat.py", "r", encoding="utf-8") as f:
        exec(f.read())