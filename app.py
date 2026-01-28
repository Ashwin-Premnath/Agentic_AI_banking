import streamlit as st
from crews import DepositCrew
from datetime import datetime

# 1. Setup Page Config
st.set_page_config(page_title="AI Banking Assistant", layout="centered")

# 2. Initialize Session State
if 'history' not in st.session_state:
    st.session_state.history = []
if 'chat_sessions' not in st.session_state:
    st.session_state.chat_sessions = {}
if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    st.session_state.chat_sessions[st.session_state.current_session_id] = {
        'history': [],
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# 3. Sidebar Controls
with st.sidebar:
    st.header("💬 Chat Management")
    
    # New Chat Button
    if st.button("➕ New Chat", use_container_width=True):
        # Save current chat before creating new one
        if st.session_state.history:
            st.session_state.chat_sessions[st.session_state.current_session_id]['history'] = st.session_state.history.copy()
        
        # Create new chat session
        new_session_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.current_session_id = new_session_id
        st.session_state.chat_sessions[new_session_id] = {
            'history': [],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        st.session_state.history = []
        st.rerun()
    
    # Clear Current Chat Button
    if st.button("🗑️ Clear Current Chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.chat_sessions[st.session_state.current_session_id]['history'] = []
        st.rerun()
    
    st.divider()
    
    # Chat History Section
    st.subheader("📚 Chat History")
    
    if len(st.session_state.chat_sessions) > 0:
        # Sort sessions by creation time (newest first)
        sorted_sessions = sorted(
            st.session_state.chat_sessions.items(),
            key=lambda x: x[1]['created_at'],
            reverse=True
        )
        
        for session_id, session_data in sorted_sessions:
            chat_length = len(session_data['history'])
            is_current = session_id == st.session_state.current_session_id
            
            # Create a preview of the first user message
            preview = "Empty chat"
            if chat_length > 0:
                first_user_msg = next((msg['content'] for msg in session_data['history'] if msg['role'] == 'user'), None)
                if first_user_msg:
                    preview = first_user_msg[:30] + "..." if len(first_user_msg) > 30 else first_user_msg
            
            # Display session button
            col1, col2 = st.columns([4, 1])
            with col1:
                button_label = f"{'🟢 ' if is_current else ''}{preview}"
                if st.button(button_label, key=f"load_{session_id}", use_container_width=True):
                    # Save current chat before switching
                    if st.session_state.history:
                        st.session_state.chat_sessions[st.session_state.current_session_id]['history'] = st.session_state.history.copy()
                    
                    # Load selected chat
                    st.session_state.current_session_id = session_id
                    st.session_state.history = session_data['history'].copy()
                    st.rerun()
            
            with col2:
                # Delete button (don't allow deleting current active chat if it's the only one)
                if len(st.session_state.chat_sessions) > 1 or not is_current:
                    if st.button("🗑️", key=f"del_{session_id}"):
                        del st.session_state.chat_sessions[session_id]
                        
                        # If deleted current chat, switch to another one or create new
                        if is_current:
                            if st.session_state.chat_sessions:
                                # Switch to most recent chat
                                st.session_state.current_session_id = sorted_sessions[1][0] if len(sorted_sessions) > 1 else sorted_sessions[0][0]
                                st.session_state.history = st.session_state.chat_sessions[st.session_state.current_session_id]['history'].copy()
                            else:
                                # Create new chat if no chats left
                                new_session_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                st.session_state.current_session_id = new_session_id
                                st.session_state.chat_sessions[new_session_id] = {
                                    'history': [],
                                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                st.session_state.history = []
                        
                        st.rerun()
            
            # Show metadata
            st.caption(f"📅 {session_data['created_at']} | 💬 {chat_length} messages")
            st.divider()
    else:
        st.info("No chat history yet")
    
    # Export chat option
    if st.session_state.history:
        st.divider()
        if st.button("📥 Download Current Chat", use_container_width=True):
            chat_text = ""
            for message in st.session_state.history:
                role = "You" if message['role'] == 'user' else "Agent"
                chat_text += f"{role}: {message['content']}\n\n"
            
            st.download_button(
                label="💾 Save as TXT",
                data=chat_text,
                file_name=f"chat_{st.session_state.current_session_id}.txt",
                mime="text/plain",
                use_container_width=True
            )

# 4. Main Chat Interface
st.title("🏦 Omni-Channel Banking Assistant")
st.markdown("I can help you **Open**, **Renew**, or check **Rates** naturally.")

# Display current session info
st.caption(f"Current Session: {st.session_state.chat_sessions[st.session_state.current_session_id]['created_at']}")

# 5. Display Chat History
chat_container = st.container()
with chat_container:
    for message in st.session_state.history:
        if message['role'] == 'user':
            st.info(f"**You:** {message['content']}")
        else:
            st.success(f"**Agent:** {message['content']}")

with st.form(key='chat_form', clear_on_submit=True):
    user_input = st.text_input(
        "Type your message here:", 
        key="chat_input_widget",
        placeholder="Ask about opening deposits, renewals, or rates..."
    )
    submit_button = st.form_submit_button("Send", type="primary", use_container_width=True)

if submit_button and user_input and user_input.strip():
    # Add user message to history
    st.session_state.history.append({"role": "user", "content": user_input})
    
    with st.spinner("Processing..."):
        try:
            deposit_crew = DepositCrew()
            recent_history = st.session_state.history[-5:]
            result = deposit_crew.kickoff(user_input, recent_history)

            response_text = str(result).replace("TaskOutput:", "").strip()

            st.session_state.history.append({"role": "assistant", "content": response_text})

            st.session_state.chat_sessions[st.session_state.current_session_id]['history'] = st.session_state.history.copy()
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.history.pop()