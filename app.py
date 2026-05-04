# ============================================================================
# VAALUKA VLSI AI - WITH PDF UPLOAD & IMPROVED RAG
# ============================================================================

import streamlit as st
from openai import OpenAI
from supabase import create_client
import os
from pypdf import PdfReader
import pdfplumber

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
SystemVerilog, UVM, AXI, PCIe, timing analysis, and digital design.

When answering:
- Provide clear, detailed explanations
- Include code examples in SystemVerilog/UVM when relevant
- Reference industry best practices
- Cite specific sections from provided documentation when available
- Be precise with technical terminology

If relevant context is provided from uploaded documents, reference it specifically.
"""

# ================= KNOWLEDGE BASE =================
def load_knowledge():
    """Load default knowledge base"""
    if not os.path.exists("vlsi_knowledge.txt"):
        with open("vlsi_knowledge.txt", "w") as f:
            f.write("Blocking vs non-blocking assignments explanation")

    with open("vlsi_knowledge.txt", "r") as f:
        text = f.read()

    return [c.strip() for c in text.split("\n\n") if c.strip()]

def extract_text_from_pdf(uploaded_file):
    """Extract text from uploaded PDF file"""
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Try pdfplumber first (better for structured content)
        text_chunks = []
        try:
            with pdfplumber.open(temp_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        # Split into chunks by paragraphs
                        paragraphs = [p.strip() for p in page_text.split('\n\n') if p.strip()]
                        text_chunks.extend(paragraphs)
        except:
            # Fallback to pypdf
            reader = PdfReader(temp_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    paragraphs = [p.strip() for p in page_text.split('\n\n') if p.strip()]
                    text_chunks.extend(paragraphs)
        
        # Clean up
        os.remove(temp_path)
        
        return text_chunks
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return []

# ================= SESSION STATE INITIALIZATION =================
if "user" not in st.session_state:
    st.session_state.user = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = "llama-3.3-70b-versatile"

if "knowledge_chunks" not in st.session_state:
    st.session_state.knowledge_chunks = load_knowledge()

if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = []

# ================= IMPROVED RAG =================
def retrieve(query, k=5):
    """Retrieve relevant context from knowledge base"""
    if not st.session_state.knowledge_chunks:
        return "No knowledge base loaded."
    
    results = []
    query_words = set(query.lower().split())
    
    for chunk in st.session_state.knowledge_chunks:
        chunk_words = set(chunk.lower().split())
        
        # Calculate overlap score
        overlap = len(query_words.intersection(chunk_words))
        
        # Bonus for exact phrase matches
        if query.lower() in chunk.lower():
            overlap += 10
        
        if overlap > 0:
            results.append((overlap, chunk))
    
    # Sort by relevance
    results = sorted(results, key=lambda x: x[0], reverse=True)
    
    # Return top k results
    relevant_chunks = [chunk for _, chunk in results[:k]]
    
    if relevant_chunks:
        return "\n\n---\n\n".join(relevant_chunks)
    return "No specific knowledge found. Answer based on your general VLSI expertise."

# ================= AUTH =================
if not st.session_state.user:
    st.title("🔐 Vaaluka VLSI AI - Authentication")
    
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

# ================= DB =================
def save_chat(messages):
    try:
        data = {
            "user": st.session_state.user.id,
            "messages": messages
        }
        supabase.table("chats").upsert(data).execute()
    except Exception as e:
        st.error(f"Error saving chat: {str(e)}")

def load_chat():
    try:
        res = supabase.table("chats").select("*").eq(
            "user", st.session_state.user.id
        ).execute()

        if res.data and len(res.data) > 0:
            return res.data[0]["messages"]
        
        return []
    except Exception as e:
        print(f"Load chat error (non-critical): {str(e)}")
        return []

# ================= SIDEBAR =================
with st.sidebar:
    st.write(f"👤 **User:** {st.session_state.user.email}")
    
    st.markdown("---")
    
    # Model Selection
    st.subheader("🤖 AI Model")
    model_display_name = st.selectbox(
        "Choose Model:",
        options=list(AVAILABLE_MODELS.keys()),
        index=0,
        help="Different models for different needs"
    )
    st.session_state.selected_model = AVAILABLE_MODELS[model_display_name]
    
    st.markdown("---")
    
    # PDF Upload Section
    st.subheader("📚 Knowledge Base")
    
    uploaded_files = st.file_uploader(
        "Upload VLSI PDFs/Docs",
        type=['pdf'],
        accept_multiple_files=True,
        help="Upload VLSI textbooks, protocol specs, verification guides, etc."
    )
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.uploaded_pdfs:
                with st.spinner(f"Processing {uploaded_file.name}..."):
                    new_chunks = extract_text_from_pdf(uploaded_file)
                    if new_chunks:
                        st.session_state.knowledge_chunks.extend(new_chunks)
                        st.session_state.uploaded_pdfs.append(uploaded_file.name)
                        st.success(f"✅ Added {len(new_chunks)} chunks from {uploaded_file.name}")
    
    # Show uploaded PDFs
    if st.session_state.uploaded_pdfs:
        st.write("**Loaded Documents:**")
        for pdf_name in st.session_state.uploaded_pdfs:
            st.write(f"📄 {pdf_name}")
    
    st.info(f"**Total Knowledge:** {len(st.session_state.knowledge_chunks)} chunks")
    
    if st.button("🗑️ Clear Uploaded PDFs"):
        st.session_state.knowledge_chunks = load_knowledge()
        st.session_state.uploaded_pdfs = []
        st.success("Cleared uploaded documents!")
        st.rerun()
    
    st.markdown("---")
    
    # Clear Chat
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.success("Chat cleared!")
        st.rerun()
    
    st.markdown("---")
    
    # Logout
    if st.button("🚪 Logout"):
        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.knowledge_chunks = load_knowledge()
        st.session_state.uploaded_pdfs = []
        st.rerun()

# ================= UI =================
st.title("⚡ Vaaluka VLSI AI Assistant")

# Load chat history
if not st.session_state.messages:
    st.session_state.messages = load_chat()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ================= INPUT =================
user_input = st.chat_input("Ask your VLSI question...")

if user_input:
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    with st.chat_message("user"):
        st.markdown(user_input)

    # Retrieve relevant context
    context = retrieve(user_input, k=5)

    # Build conversation history for context
    conversation_messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Add last 10 messages for context (but not the current one)
    for msg in st.session_state.messages[-11:-1]:
        conversation_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current question with retrieved context
    conversation_messages.append({
        "role": "user",
        "content": f"**Relevant Documentation/Context:**\n{context}\n\n**Question:** {user_input}"
    })

    # Generate response
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

    with st.chat_message("assistant"):
        with st.spinner(f"Thinking with {st.session_state.selected_model}..."):
            try:
                response = client.chat.completions.create(
                    model=st.session_state.selected_model,
                    messages=conversation_messages,
                    max_tokens=4096,  # Increased for longer responses
                    temperature=0.7
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
