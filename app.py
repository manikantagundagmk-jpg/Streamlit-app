# ============================================================================
# VAALUKA VLSI AI - FINAL CLEAN VERSION (NO HEAVY ML)
# ============================================================================

import streamlit as st
from openai import OpenAI
import numpy as np
from supabase import create_client
import os
from datetime import datetime
import uuid
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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


@st.cache_resource
def build_vector_db(chunks):
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform(chunks)
    return vectorizer, vectors


knowledge_chunks = load_knowledge()
vectorizer, vectors = build_vector_db(knowledge_chunks)

# ================= RAG =================
def retrieve(query, k=3):
    results = []

    for chunk in knowledge_chunks:
        if query.lower() in chunk.lower():
            results.append(chunk)

    return "\n\n".join(results[:k])


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

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None


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

# Load chat on start
if not st.session_state.messages:
    st.session_state.messages = load_chat()

# Show chat
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

    # RAG
    context = retrieve(user_input)

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
