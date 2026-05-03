# ============================================================================
# VAALUKA VLSI AI - WITH MODEL SELECTION & FIXED TABLE NAME
# ============================================================================

import streamlit as st
from openai import OpenAI
from supabase import create_client
import os

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="Vaaluka VLSI AI",
    page_icon="⚡",
    layout="wide"
)

# ================= CONFIG =================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= GROQ MODELS =================
AVAILABLE_MODELS = {
    "Llama 3.3 70B (Versatile)": "llama-3.3-70b-versatile",
    "Llama 3.1 70B (Versatile)": "llama-3.1-70b-versatile",
    "Llama 3.1 8B (Fast)": "llama-3.1-8b-instant",
    "Mixtral 8x7B": "mixtral-8x7b-32768",
    "Gemma 2 9B": "gemma2-9b-it",
}

SYSTEM_PROMPT = """You are a senior VLSI verification engineer with deep expertise in:
SystemVerilog, UVM, AXI, PCIe.

Give:
- Clear explanations
- Code examples
- Practical insights
"""

# ================= KNOWLEDGE BASE =================
def load_knowledge():
    if not os.path.exists("vlsi_knowledge.txt"):
        with open("vlsi_knowledge.txt", "w") as f:
            f.write("Blocking vs non-blocking assignments explanation")

    with open("vlsi_knowledge.txt", "r") as f:
        text = f.read()

    return [c.strip() for c in text.split("\n\n") if c.strip()]


knowledge_chunks = load_knowledge()

# ================= LIGHTWEIGHT RAG =================
def retrieve(query, k=3):
    results = []
    query_words = query.lower().split()

    for chunk in knowledge_chunks:
        score = sum(1 for word in query_words if word in chunk.lower())
        if score > 0:
            results.append((score, chunk))

    results = sorted(results, key=lambda x: x[0], reverse=True)

    return "\n\n".join([chunk for _, chunk in results[:k]])

# ================= AUTH =================
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🔐 Vaaluka VLSI AI - Authentication")
    
    # Tab selection for Login/Signup
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to Your Account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", key="login_btn"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.user = res.user
                st.success("✅ Login successful!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Login failed: {str(e)}")
    
    with tab2:
        st.subheader("Create New Account")
        signup_email = st.text_input("Email", key="signup_email")
        signup_password = st.text_input("Password (min 6 characters)", type="password", key="signup_password")
        signup_password_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
        
        if st.button("Sign Up", key="signup_btn"):
            if signup_password != signup_password_confirm:
                st.error("❌ Passwords do not match!")
            elif len(signup_password) < 6:
                st.error("❌ Password must be at least 6 characters!")
            else:
                try:
                    res = supabase.auth.sign_up({
                        "email": signup_email,
                        "password": signup_password
                    })
                    st.success("✅ Account created! Please check your email to verify your account.")
                    st.info("After verification, use the Login tab to sign in.")
                except Exception as e:
                    st.error(f"❌ Signup failed: {str(e)}")

    st.stop()

# ================= CHAT STATE =================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = "llama-3.3-70b-versatile"

# ================= DB (FIXED - lowercase table name) =================
def save_chat(messages):
    try:
        data = {
            "user": st.session_state.user.id,
            "messages": messages
        }
        # FIXED: Changed "Chats" to "chats" (lowercase)
        supabase.table("chats").upsert(data).execute()
    except Exception as e:
        st.error(f"Error saving chat: {str(e)}")

def load_chat():
    try:
        # FIXED: Changed "Chats" to "chats" (lowercase)
        res = supabase.table("chats").select("*").eq(
            "user", st.session_state.user.id
        ).execute()

        if res.data and len(res.data) > 0:
            return res.data[0]["messages"]
        
        return []
    except Exception as e:
        # If table is empty or query fails, return empty list
        print(f"Load chat error (non-critical): {str(e)}")
        return []

# ================= SIDEBAR =================
with st.sidebar:
    st.write(f"👤 **User:** {st.session_state.user.email}")
    
    st.markdown("---")
    
    # Model Selection
    st.subheader("🤖 Select AI Model")
    
    model_display_name = st.selectbox(
        "Choose Model:",
        options=list(AVAILABLE_MODELS.keys()),
        index=0,
        help="Different models for different needs:\n- Llama 3.3 70B: Most capable\n- Llama 3.1 8B: Fastest responses\n- Mixtral: Good for reasoning\n- Gemma 2: Balanced performance"
    )
    
    st.session_state.selected_model = AVAILABLE_MODELS[model_display_name]
    
    st.info(f"**Current Model:**\n`{st.session_state.selected_model}`")
    
    st.markdown("---")
    
    # Clear Chat History
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.success("Chat cleared!")
        st.rerun()
    
    st.markdown("---")
    
    # Logout
    if st.button("🚪 Logout"):
        st.session_state.user = None
        st.session_state.messages = []
        st.rerun()

# ================= UI =================
st.title("⚡ Vaaluka VLSI AI Assistant")

# Load chat history only once
if not st.session_state.messages:
    st.session_state.messages = load_chat()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ================= INPUT =================
user_input = st.chat_input("Ask your VLSI question...")

if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    context = retrieve(user_input)

    if not context:
        context = "No specific knowledge found. Answer generally."

    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

    with st.chat_message("assistant"):
        with st.spinner(f"Thinking with {st.session_state.selected_model}..."):
            try:
                response = client.chat.completions.create(
                    model=st.session_state.selected_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"{context}\n\nQuestion: {user_input}"
                        }
                    ],
                    max_tokens=1024
                )

                reply = response.choices[0].message.content

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply
                })

                save_chat(st.session_state.messages)

                st.markdown(reply)
                
            except Exception as e:
                st.error(f"Error generating response: {str(e)}")
