import streamlit as st
import os
import tempfile
from main import BankingFlow, BankingState

st.set_page_config(page_title="Banking AI Assistant", page_icon="🏦", layout="wide")

st.title("🏦 Banking AI Assistant")
st.markdown("Powered by CrewAI Flows & NVIDIA NIM")

# Sidebar for User Context
with st.sidebar:
    st.header("User Authentication")
    account_number = st.text_input("Account Number", value="ACC123456")
    
    st.divider()
    
    st.header("Document Upload")
    uploaded_file = st.file_uploader("Upload Documents (KYC, FD Forms, etc.)", type=["png", "jpg", "jpeg", "pdf"])
    
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        if "banking_flow" in st.session_state:
            # Safer access in case the session has an older version of the class
            def safe_set(obj, attr, val):
                if hasattr(obj, attr): setattr(obj, attr, val)
            
            state = st.session_state.banking_flow.state
            safe_set(state, "pending_fd_data", None)
            safe_set(state, "pending_kyc_data", None)
            safe_set(state, "pending_onboarding_data", None)
        st.rerun()

    # Safer check for the progress indicator
    if "banking_flow" in st.session_state:
        flow_state = st.session_state.banking_flow.state
        if getattr(flow_state, "pending_fd_data", None):
            st.info("📝 **FD Application In Progress**\nThe agents are currently collecting details for your Fixed Deposit.")

# Initialize session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "banking_flow" not in st.session_state:
    st.session_state.banking_flow = BankingFlow()

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("How can I help you today?"):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # Process with BankingFlow
    with st.spinner("Banking Agents are working..."):
        # Handle file upload persistence
        temp_file_path = None
        if uploaded_file:
            # Save uploaded file to a temporary location for the flow to pick up
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as f:
                f.write(uploaded_file.getbuffer())
                temp_file_path = f.name
        
        # Initialize and kickoff flow
        flow = st.session_state.banking_flow
        flow.state.account_number = account_number
        flow.state.query = prompt
        
        # Only update file_path if a new file is actually uploaded
        if temp_file_path:
            flow.state.file_path = temp_file_path
        
        try:
            flow.kickoff()
            response = flow.state.response
        except Exception as e:
            response = f"An error occurred: {str(e)}"
        finally:
            # Cleanup temp file if it was created
            if temp_file_path and os.path.exists(temp_file_path):
                # We don't delete it here because the flow might have moved it, 
                # but if it didn't move it, we should clean up.
                # However, main.py moves/copies it. So we can delete the temp one.
                try:
                    os.remove(temp_file_path)
                except:
                    pass

    # Display assistant response
    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.chat_history.append({"role": "assistant", "content": response})
