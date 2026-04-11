import streamlit as st
from assistant.agent import ask

st.set_page_config(page_title="AI Assistant", page_icon="🤖")
st.title("AI Assistant")
st.caption("Powered by Groq + LangChain · Asks a calculator when it needs one")

# Initialize conversation history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Render existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle new input
if prompt := st.chat_input("Ask me anything..."):
    # Show and store user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get assistant response (pass history minus the message we just added)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            history = st.session_state.messages[:-1]  # exclude current message
            response = ask(prompt, history)
        st.markdown(response)

    # Store assistant message
    st.session_state.messages.append({"role": "assistant", "content": response})
