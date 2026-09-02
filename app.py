"""Streamlit chat UI talking to the FastAPI backend."""
import requests
import streamlit as st
from config import API_URL

st.set_page_config(page_title="Samsung Phone Assistant", page_icon="📱", layout="wide")
st.title("📱 Samsung Phone Query & Review System")

if "messages" not in st.session_state:
    st.session_state.messages = []


@st.cache_data(ttl=300)
def get_phones():
    return requests.get(f"{API_URL}/phones", timeout=30).json()


with st.sidebar:
    st.header("Phones in database")
    try:
        phone_names = [p["name"] for p in get_phones()]
    except requests.ConnectionError:
        st.error("API is not running. Start it with:\n`uvicorn api:app`")
        st.stop()
    for name in phone_names:
        st.markdown(f"- {name}")

    st.divider()
    st.header("Generate a review")
    selected = st.selectbox("Phone", phone_names)
    if st.button("Write review", use_container_width=True):
        with st.spinner("Review agent is writing..."):
            r = requests.get(f"{API_URL}/review/{selected}", timeout=300).json()
        st.session_state.messages.append(
            {"role": "user", "content": f"Write a review of the {selected}"})
        st.session_state.messages.append(
            {"role": "assistant", "content": r["review"]})

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about any Samsung phone..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    f"{API_URL}/ask",
                    json={"question": prompt,
                          "history": st.session_state.messages[:-1]},
                    timeout=300,
                ).json()
                answer = resp["answer"]
            except Exception as e:
                answer = f"Error contacting API: {e}"
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
