import streamlit as st
import requests
import subprocess
import os

st.set_page_config(page_title="Offline E2E Chat", layout="centered")

st.title("🔵 Secure Offline E2E Chat")

# Start backend automatically
if "server_started" not in st.session_state:
    subprocess.Popen(["python", "server.py"])
    st.session_state.server_started = True

sender = st.text_input("Your Name")
message = st.text_input("Message")

if st.button("Send"):
    requests.post("http://127.0.0.1:5000/send",
                  json={"sender": sender, "message": message})
    st.success("Message Sent Securely")

st.markdown("### 💬 Chat History")

try:
    response = requests.get("http://127.0.0.1:5000/messages")
    data = response.json()

    for msg in data:
        st.write(f"**{msg['sender']}**: {msg['message']}")

except:
    st.warning("Server not ready yet...")

st.markdown("---")
st.markdown("All Rights Reserved © 2026")
