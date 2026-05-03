# ============================================================================
# VAALUKA VLSI AI - FINAL STABLE VERSION (NO SKLEARN)
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
    st.title("🔐 Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.session_state.user = res.user
        st.rerun()

    st.stop()

# ================= CHAT STATE =================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= DB =================
def save_chat(messages):
    data = {
        "user": st.session_state.user.id,
        "messages": messages
    }
    supabase.table("Chats").upsert(data).execute()

def load_chat():
    res = supabase.table("Chats").select("*").eq(
        "user", st.session_state.user.id
    ).execute()

    if res.data:
        return res.data[0]["messages"]

    return []

# ================= UI =================
st.title("⚡ Vaaluka VLSI AI Assistant")

if not st.session_state.messages:
    st.session_state.messages = load_chat()

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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
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

    with st.chat_message("assistant"):
        st.markdown(reply)
