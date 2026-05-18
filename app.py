import streamlit as st
import anthropic
import os
import io
import json
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Company Analyzer",
    page_icon="📊",
    layout="wide",
)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in {
    "documents": [],
    "deal_summary": "",
    "risk_analysis": "",
    "private_chat": [],
    "public_research": "",
    "public_chat": [],
    "memo": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_docx(data: bytes) -> str:
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(io.BytesIO(data))
    parts = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1]

        if tag == "p":
            text = "".join(
                node.text or ""
                for node in element.iter()
                if node.tag.endswith("}t")
            )
            if text.strip():
                parts.append(text)

        elif tag == "tbl":
            for row in element.findall(".//" + qn("w:tr")):
                cells = [
                    "".join(
                        node.text or ""
                        for node in cell.iter()
                        if node.tag.endswith("}t")
                    ).strip()
                    for cell in row.findall(".//" + qn("w:tc"))
                ]
                if any(cells):
                    parts.append(" | ".join(cells))

    return "\n".join(parts)


def docs_context(limit: int = 80_000) -> str:
    parts = [f"=== {d['name']} ===\n{d['text']}" for d in st.session_state.documents]
    return "\n\n".join(parts)[:limit]


def get_ollama_models() -> list[str]:
    try:
        import requests as req
        r = req.get("http://localhost:11434/api/tags", timeout=2)
        if r.ok:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def stream_claude(client, model: str, system: str, messages: list) -> str:
    full = ""
    slot = st.empty()
    with client.messages.stream(
        model=model, max_tokens=4096, system=system, messages=messages
    ) as s:
        for chunk in s.text_stream:
            full += chunk
            slot.markdown(full + "▌")
    slot.markdown(full)
    return full


def stream_ollama(model: str, system: str, messages: list) -> str:
    import requests as req
    full = ""
    slot = st.empty()
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": True,
    }
    try:
        with req.post(
            "http://localhost:11434/api/chat",
            json=payload,
            stream=True,
            timeout=180,
        ) as r:
            for line in r.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    full += token
                    slot.markdown(full + "▌")
    except Exception as e:
        st.error(f"Ollama error: {e}\n\nMake sure Ollama is running: `ollama serve`")
        return ""
    slot.markdown(full)
    return full


def run(system: str, messages: list, *, use_local: bool,
        claude_client, claude_model: str, ollama_model: str) -> str:
    if use_local:
        return stream_ollama(ollama_model, system, messages)
    return stream_claude(claude_client, claude_model, system, messages)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    backend = st.selectbox(
        "Private Document Mode",
        ["☁️ Cloud (Claude API)", "🖥️ Local (Ollama)"],
        help="Local mode keeps your private documents on your machine. Public Research and Memo always use the Claude API.",
    )
    use_local = backend.startswith("🖥️")

    if use_local:
        st.success("🔒 Private docs stay on your machine")
        ollama_models = get_ollama_models()
        if ollama_models:
            ollama_model = st.selectbox("Local Model", ollama_models)
        else:
            st.warning("Ollama not detected.\nStart it with: `ollama serve`")
            ollama_model = st.text_input(
                "Model name",
                value="llama3.2",
                help="Pull a model first: `ollama pull llama3.2`",
            )
    else:
        ollama_model = ""

    st.divider()

    api_key = st.text_input(
        "Anthropic API Key",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Required for Public Research and Memo. Also required for Analysis/Q&A in Cloud mode.",
    )
    if use_local:
        st.caption("API key used only for Public Research & Memo tabs.")

    claude_model = st.selectbox("Claude Model", ["claude-sonnet-4-6", "claude-opus-4-7"])

    st.divider()
    st.subheader("Loaded Documents")
    if st.session_state.documents:
        for d in st.session_state.documents:
            st.caption(f"📄 {d['name']}  ({len(d['text']):,} chars)")
    else:
        st.caption("None yet")

    st.divider()
    if st.button("🗑️ Reset Everything", use_container_width=True):
        for k, v in {
            "documents": [],
            "deal_summary": "",
            "risk_analysis": "",
            "private_chat": [],
            "public_research": "",
            "public_chat": [],
            "memo": "",
        }.items():
            st.session_state[k] = v
        st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("📊 Company Analyzer")

if use_local:
    st.info(
        "🖥️ **Local mode** — Analysis and Private Q&A run on your machine via Ollama. "
        "Private documents are never sent to the cloud for these features. "
        "Public Research and Memo always use the Claude API."
    )
else:
    st.info(
        "☁️ **Cloud mode** — All features use the Claude API (Anthropic). "
        "Private documents are sent over HTTPS for Analysis and Q&A."
    )

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📁 Documents", "🔍 Analysis", "🔒 Private Q&A", "🌐 Public Research", "📝 Memo"]
)

claude_client = anthropic.Anthropic(api_key=api_key) if api_key else None


# ── Tab 1: Documents ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Upload Documents")
    if use_local:
        st.caption("🔒 In Local mode, document text is only processed on your machine for Analysis and Q&A.")

    uploaded = st.file_uploader(
        "Drop PDF or DOCX files here",
        type=["pdf", "docx"],
        accept_multiple_files=True,
    )
    if uploaded:
        existing = {d["name"] for d in st.session_state.documents}
        added = 0
        for f in uploaded:
            if f.name in existing:
                continue
            with st.spinner(f"Extracting {f.name}…"):
                try:
                    raw = f.read()
                    text = extract_pdf(raw) if f.name.lower().endswith(".pdf") else extract_docx(raw)
                    st.session_state.documents.append({"name": f.name, "text": text})
                    added += 1
                except Exception as e:
                    st.error(f"❌ {f.name}: {e}")
        if added:
            st.success(f"✅ Added {added} file(s).")
            st.rerun()

    if st.session_state.documents:
        st.divider()
        for doc in st.session_state.documents:
            with st.expander(f"📄 {doc['name']}  —  {len(doc['text']):,} chars"):
                preview = doc["text"][:3000]
                if len(doc["text"]) > 3000:
                    preview += "\n\n[… truncated for preview — full text is used for analysis …]"
                st.text(preview)


# ── Tab 2: Analysis ───────────────────────────────────────────────────────────
with tab2:
    if not st.session_state.documents:
        st.info("📁 Upload documents in the Documents tab first.")
    elif use_local and not ollama_model:
        st.warning("Select a local model in the sidebar.")
    elif not use_local and not api_key:
        st.warning("🔑 Enter your Anthropic API key in the sidebar.")
    else:
        if use_local:
            st.caption(f"🖥️ Running locally via Ollama ({ollama_model}) — private docs stay on your machine")
        else:
            st.caption(f"☁️ Running via Claude API ({claude_model})")

        ctx = docs_context()
        col1, col2 = st.columns(2)
        run_summary = col1.button("📋 Summarize Deal", use_container_width=True, type="primary")
        run_risks = col2.button("⚠️ Extract Risks", use_container_width=True, type="primary")

        if run_summary:
            st.subheader("Deal Summary")
            result = run(
                system="You are a senior M&A analyst. Be concise, structured, and professional.",
                messages=[{"role": "user", "content": (
                    "Summarize this deal covering: deal structure, parties involved, "
                    "key terms, timeline, and financial highlights.\n\nDOCUMENTS:\n" + ctx
                )}],
                use_local=use_local,
                claude_client=claude_client,
                claude_model=claude_model,
                ollama_model=ollama_model,
            )
            st.session_state.deal_summary = result

        if run_risks:
            st.subheader("Risk Extraction")
            result = run(
                system="You are a senior due diligence analyst. Surface risks clearly and cite which document each point comes from.",
                messages=[{"role": "user", "content": (
                    "Extract findings under each heading. Cite the source document for each point. "
                    "Write 'None identified.' if nothing found.\n\n"
                    "## 🔴 Layoffs / Workforce Reductions\n"
                    "## 🟠 Asset Sales / Divestitures\n"
                    "## 🟡 Regulatory / Compliance Issues\n"
                    "## 🔵 Missing Information / Data Gaps\n"
                    "## ⚫ Other Red Flags\n\n"
                    "DOCUMENTS:\n" + ctx
                )}],
                use_local=use_local,
                claude_client=claude_client,
                claude_model=claude_model,
                ollama_model=ollama_model,
            )
            st.session_state.risk_analysis = result

        if st.session_state.deal_summary and not run_summary:
            st.divider()
            st.subheader("Deal Summary")
            st.markdown(st.session_state.deal_summary)

        if st.session_state.risk_analysis and not run_risks:
            st.divider()
            st.subheader("Risk Extraction")
            st.markdown(st.session_state.risk_analysis)


# ── Tab 3: Private Q&A ────────────────────────────────────────────────────────
with tab3:
    if not st.session_state.documents:
        st.info("📁 Upload documents in the Documents tab first.")
    elif use_local and not ollama_model:
        st.warning("Select a local model in the sidebar.")
    elif not use_local and not api_key:
        st.warning("🔑 Enter your Anthropic API key in the sidebar.")
    else:
        if use_local:
            st.caption(f"🖥️ Ollama ({ollama_model}) — answers drawn only from your documents, processed locally")
        else:
            st.caption(f"☁️ Claude API ({claude_model}) — answers drawn only from your uploaded documents")

        ctx = docs_context()
        system_private = (
            "You are a diligent analyst with access to the following confidential documents:\n\n"
            + ctx
            + "\n\nAnswer questions based ONLY on these documents. "
            "If the information is not present in the documents, say so explicitly. "
            "Do not use outside knowledge or make assumptions beyond what the documents state."
        )

        for msg in st.session_state.private_chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        question = st.chat_input("Ask anything about your private documents…", key="private_input")
        if question:
            st.session_state.private_chat.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                answer = run(
                    system=system_private,
                    messages=st.session_state.private_chat,
                    use_local=use_local,
                    claude_client=claude_client,
                    claude_model=claude_model,
                    ollama_model=ollama_model,
                )
            st.session_state.private_chat.append({"role": "assistant", "content": answer})

        if st.session_state.private_chat:
            if st.button("🗑️ Clear Chat", key="clear_private"):
                st.session_state.private_chat = []
                st.rerun()


# ── Tab 4: Public Research ────────────────────────────────────────────────────
with tab4:
    st.caption("☁️ Always uses the Claude API. Your private document content is **never sent** in this tab.")

    if not api_key:
        st.warning("🔑 Enter your Anthropic API key in the sidebar.")
    else:
        research = st.text_area(
            "Paste public research context",
            value=st.session_state.public_research,
            height=150,
            placeholder=(
                "Paste news articles, analyst reports, press releases, "
                "LinkedIn data, competitor info, market cap, EPS, industry data…"
            ),
        )
        st.session_state.public_research = research

        st.divider()
        st.subheader("Research Q&A")
        st.caption(
            "Ask about the company using public knowledge and what you've pasted above. "
            "No private documents are involved here."
        )

        public_context_section = (
            "\n\nUSER-PROVIDED RESEARCH:\n" + research.strip()
            if research.strip()
            else "\n\nUSER-PROVIDED RESEARCH: None pasted yet."
        )
        system_public = (
            "You are a senior analyst answering questions using publicly available information.\n"
            "You have two sources:\n"
            "1. Research pasted by the user (USER-PROVIDED RESEARCH below)\n"
            "2. Your own general training knowledge\n\n"
            "Label the source of each answer clearly: [User Research] or [General Knowledge].\n"
            "Your knowledge cutoff is August 2025 — note this when citing market data or recent events.\n"
            "You do NOT have access to any private or confidential documents."
            + public_context_section
        )

        for msg in st.session_state.public_chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        pub_question = st.chat_input(
            "Ask about market cap, competitors, news, industry trends…",
            key="public_input",
        )
        if pub_question:
            st.session_state.public_chat.append({"role": "user", "content": pub_question})
            with st.chat_message("user"):
                st.markdown(pub_question)
            with st.chat_message("assistant"):
                answer = stream_claude(
                    claude_client, claude_model, system_public, st.session_state.public_chat
                )
            st.session_state.public_chat.append({"role": "assistant", "content": answer})

        if st.session_state.public_chat:
            if st.button("🗑️ Clear Research Chat", key="clear_public"):
                st.session_state.public_chat = []
                st.rerun()


# ── Tab 5: Memo ───────────────────────────────────────────────────────────────
with tab5:
    st.caption(
        "☁️ Always uses the Claude API. "
        "Sends the AI-generated analysis summaries (not your raw documents) plus public research."
    )

    if not api_key:
        st.warning("🔑 Enter your Anthropic API key in the sidebar.")
    elif not st.session_state.documents:
        st.info("📁 Upload documents and run Analysis first.")
    else:
        if not st.session_state.deal_summary and not st.session_state.risk_analysis:
            st.warning("⚠️ Run Deal Summary and/or Risk Extraction in the Analysis tab first.")

        st.subheader("What gets sent to generate the memo")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Private analysis output:**")
            if st.session_state.deal_summary:
                st.caption(st.session_state.deal_summary[:300] + "…")
            else:
                st.caption("No deal summary generated yet.")
        with col2:
            st.markdown("**Public research (pasted):**")
            if st.session_state.public_research.strip():
                st.caption(st.session_state.public_research[:300] + "…")
            else:
                st.caption("No public research pasted yet.")

        st.divider()

        if st.button("📝 Generate Management Memo", type="primary", use_container_width=True):
            prompt = f"""Write a professional management memo with the structure below.
Be direct, precise, and flag concerns clearly.

---
**MEMO**
**To:** Senior Management / Investment Committee
**Re:** Due Diligence Summary
**Classification:** Confidential
---

## 1. Executive Summary
## 2. Private Document Findings
## 3. Public Research Findings
## 4. Private vs. Public Comparison
## 5. Red Flags & Discrepancies
## 6. Missing Information
## 7. Recommendation

---

PRIVATE ANALYSIS — Deal Summary:
{st.session_state.deal_summary[:2000] if st.session_state.deal_summary else "Not generated."}

PRIVATE ANALYSIS — Risk Extraction:
{st.session_state.risk_analysis[:2000] if st.session_state.risk_analysis else "Not generated."}

PUBLIC RESEARCH:
{st.session_state.public_research.strip() if st.session_state.public_research.strip() else "None provided."}
"""
            st.subheader("Management Memo")
            memo = stream_claude(
                claude_client,
                claude_model,
                "You are a senior investment analyst writing a confidential management memo. "
                "Be professional, precise, and direct. Surface concerns without softening them.",
                [{"role": "user", "content": prompt}],
            )
            st.session_state.memo = memo

        if st.session_state.memo:
            st.divider()
            st.markdown(st.session_state.memo)
            st.download_button(
                "⬇️ Download Memo (.md)",
                data=st.session_state.memo,
                file_name="management_memo.md",
                mime="text/markdown",
                use_container_width=True,
            )
