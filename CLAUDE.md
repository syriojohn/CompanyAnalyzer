# Company Analyzer — CLAUDE.md

This file is the single source of truth for the Company Analyzer project. Claude Code should read this file before making any changes. A developer (or Claude Code) should be able to rebuild the entire application from scratch using only this document.

---

## What This App Does

Company Analyzer is a Streamlit-based due diligence tool designed for M&A and investment teams. It allows analysts to:

1. Upload confidential deal documents (PDF/DOCX) and extract their text locally
2. Summarize the deal and extract structured risks using AI
3. Ask questions directly over the private documents
4. Conduct separate public research Q&A using Claude's knowledge and pasted web findings
5. Generate a professional management memo that compares private document findings against public research
6. Choose whether private document analysis runs locally (Ollama) or via the cloud (Claude API)

The key design principle is **data separation**: private document content and public research are kept in separate processing pipelines, with the user in full control of what goes where.

---

## File Structure

```
CompanyAnalyzer/
├── app.py              # Entire application — single file, no modules
├── requirements.txt    # Python dependencies
├── .env.example        # Template for environment variables
├── .env                # Local env file (not committed) — holds ANTHROPIC_API_KEY
└── CLAUDE.md           # This file
```

The app is intentionally kept as a single file (`app.py`) for demo simplicity. Do not split into modules unless explicitly asked.

---

## Running the App

```powershell
cd C:\Users\syrio\CompanyAnalyzer
pip install -r requirements.txt
copy .env.example .env      # then add your ANTHROPIC_API_KEY to .env
streamlit run app.py
```

The app runs at `http://localhost:8501` by default. Streamlit hot-reloads on file save — no restart needed during development.

---

## Dependencies

```
streamlit>=1.35.0       # UI framework
anthropic>=0.40.0       # Claude API client (streaming supported)
python-dotenv>=1.0.0    # Load ANTHROPIC_API_KEY from .env
pypdf>=4.0.0            # PDF text extraction (pure Python, no system deps)
python-docx>=1.1.0      # DOCX text extraction
```

The `requests` library (stdlib-adjacent, always available) is used inside functions for Ollama API calls. No additional install needed.

---

## Architecture

### Session State

All persistent data lives in `st.session_state`. Initialized at startup:

| Key | Type | Purpose |
|---|---|---|
| `documents` | `list[dict]` | Each entry: `{"name": str, "text": str}` |
| `deal_summary` | `str` | Output of the Summarize Deal button |
| `risk_analysis` | `str` | Output of the Extract Risks button |
| `private_chat` | `list[dict]` | Chat history for Private Q&A tab |
| `public_research` | `str` | Raw text pasted by user in Public Research tab |
| `public_chat` | `list[dict]` | Chat history for Public Research tab |
| `memo` | `str` | Generated management memo |

### Backend Routing

Two AI backends are supported. The sidebar dropdown controls which one is used for private document processing:

**Cloud (Claude API)**
- All features use `anthropic.Anthropic(api_key=...)` 
- Documents are sent to Anthropic's servers over HTTPS
- Anthropic does not train on API data

**Local (Ollama)**
- Analysis and Private Q&A route to `http://localhost:11434/api/chat`
- Documents never leave the machine for these features
- Public Research and Memo tabs always use the Claude API regardless of this setting
- Ollama must be running (`ollama serve`) with at least one model pulled

The routing function `run(system, messages, *, use_local, claude_client, claude_model, ollama_model)` handles this dispatch. All streaming goes through either `stream_claude()` or `stream_ollama()`.

### Streaming

Both backends stream tokens in real time. The pattern is identical for both:

```python
full = ""
slot = st.empty()          # single placeholder in the UI
for token in stream:
    full += token
    slot.markdown(full + "▌")   # cursor effect
slot.markdown(full)         # final render, cursor removed
```

For Claude: uses `client.messages.stream()` from the Anthropic SDK.  
For Ollama: uses `requests.post(..., stream=True)` against `/api/chat`, parsing newline-delimited JSON.

### Document Context

`docs_context(limit=80_000)` concatenates all uploaded document texts with filename headers:

```
=== filename.pdf ===
<extracted text>

=== another.docx ===
<extracted text>
```

Truncated at 80,000 characters (~20,000 tokens), well within Claude's 200k context window. This string is injected into the system prompt or user message depending on the feature.

---

## The Five Tabs

### Tab 1 — Documents (`📁`)

- `st.file_uploader` with `accept_multiple_files=True`, accepts `.pdf` and `.docx`
- `extract_pdf(bytes)` uses `pypdf.PdfReader` — works on text-based PDFs only (not scanned)
- `extract_docx(bytes)` uses `python-docx` — walks `doc.element.body` directly to extract both paragraphs (`w:p`) and tables (`w:tbl`) in document order. Tables are rendered as pipe-separated rows (`Cell1 | Cell2 | ...`). Using `doc.paragraphs` alone silently skips all table content.
- Deduplicates by filename (will not re-add a file already loaded)
- Stores `{"name": filename, "text": extracted_text}` in `st.session_state.documents`
- Shows collapsible expanders with a 3,000-char preview per document
- In Local mode, shows a note that documents are only processed on-machine for Analysis/Q&A

### Tab 2 — Analysis (`🔍`)

- Two side-by-side buttons: **Summarize Deal** and **Extract Risks**
- Both use the `run()` dispatcher — routes to Ollama or Claude depending on sidebar setting
- Answers are stored in session state and persist across reruns

**Summarize Deal** system prompt: Senior M&A analyst. Covers deal structure, parties, key terms, timeline, financial highlights.

**Extract Risks** system prompt: Senior due diligence analyst. Returns findings under five fixed headings:
- 🔴 Layoffs / Workforce Reductions
- 🟠 Asset Sales / Divestitures
- 🟡 Regulatory / Compliance Issues
- 🔵 Missing Information / Data Gaps
- ⚫ Other Red Flags

Each finding must cite which document it came from. If nothing found, writes "None identified."

Results are stored in `st.session_state.deal_summary` and `st.session_state.risk_analysis` and re-displayed on subsequent visits without re-running.

### Tab 3 — Private Q&A (`🔒`)

- Multi-turn chat interface over the uploaded documents
- Answers drawn **only** from uploaded documents — the system prompt explicitly forbids outside knowledge
- Uses the `run()` dispatcher (Ollama or Claude)
- Document context is injected into the system prompt (not in the message thread), keeping the conversation history clean
- Chat history stored in `st.session_state.private_chat`
- "Clear Chat" button resets history

System prompt pattern:
```
You are a diligent analyst with access to the following confidential documents:

=== doc1.pdf ===
<text>...

Answer questions based ONLY on these documents. If the information is not present, say so explicitly. Do not use outside knowledge.
```

### Tab 4 — Public Research (`🌐`)

- **Always uses Claude API. Private document content is never sent here.**
- Text area for pasting public research (news, analyst reports, LinkedIn, market data, etc.)
- Separate multi-turn chat: `st.session_state.public_chat`
- System prompt gives Claude two explicit sources:
  1. User-provided research (pasted text, injected into system prompt)
  2. General training knowledge
- Claude must label each answer: `[User Research]` or `[General Knowledge]`
- Knowledge cutoff noted as August 2025

This tab exists to completely separate public-domain questions from private document analysis. No cross-contamination of private content into this pipeline.

### Tab 5 — Memo (`📝`)

- **Always uses Claude API.**
- Shows a preview of what will be sent: the deal summary snippet + public research snippet
- What gets sent to Claude: AI-generated summaries (deal summary text, risk analysis text) + pasted public research
- **Raw document text is NOT sent** — only the AI-generated output from Tab 2
- This is intentional: in Local mode, the summaries were generated locally; only those summaries (not the source docs) travel to the cloud for memo generation

Memo structure (7 sections):
1. Executive Summary
2. Private Document Findings
3. Public Research Findings
4. Private vs. Public Comparison
5. Red Flags & Discrepancies
6. Missing Information
7. Recommendation

Output is displayed as markdown and downloadable as `management_memo.md`.

---

## Privacy Model

This is the most important design decision. The table below is the authoritative reference:

| Feature | Cloud mode | Local mode |
|---|---|---|
| Text extraction (PDF/DOCX) | On-machine (always) | On-machine (always) |
| Analysis (Summarize/Risks) | Docs → Anthropic API | Docs → Ollama (local) |
| Private Q&A | Docs → Anthropic API | Docs → Ollama (local) |
| Public Research Q&A | No private docs sent (ever) | No private docs sent (ever) |
| Memo generation | AI summaries + public research → Anthropic API | AI summaries + public research → Anthropic API |

In Local mode, the Memo tab sends the *output* of local analysis (the deal summary and risk extraction text), not the raw document content. Users see a preview of exactly what will be sent before clicking Generate.

---

## Ollama Setup (Local Mode)

Ollama must be installed and running for Local mode to work.

```powershell
# Install from https://ollama.com/download
ollama serve                    # start the inference server
ollama pull llama3.2            # download the default model (~2GB)
```

The app queries `http://localhost:11434/api/tags` to detect installed models and populates the model dropdown automatically. If Ollama is not running, a warning is shown with the startup command.

**Recommended models** (in order of preference for document analysis):
- `llama3.2` — 3B params, 2GB, fast, good for structured extraction
- `mistral` — 7B params, 4GB, stronger reasoning, slower
- `phi3` — 3.8B params, 2.3GB, Microsoft model, good instruction following

First inference after startup is slow (~30s) as the model loads into RAM. Subsequent calls are fast.

---

## Key Implementation Details

### Why document context goes in the system prompt (not user messages)
The document text is embedded in the system prompt for Private Q&A. This keeps the actual conversation history (`private_chat`) as clean alternating user/assistant pairs, which is required by the Anthropic API. It also means the full document context is present for every turn without re-injecting it.

### Why `st.empty()` is used for streaming
`st.empty()` creates a single placeholder element that gets overwritten on each token. Without it, each token append would create a new element in the DOM. The cursor character `▌` is appended during streaming and removed on final render.

### Why the Memo tab sends summaries, not raw docs
Two reasons: (1) privacy — in Local mode, the summaries were generated on-machine and the raw docs should not travel to the cloud; (2) token efficiency — summaries are ~2,000 chars vs potentially 80,000 chars for raw docs.

### Deduplication on upload
Files are deduplicated by name (`{d["name"] for d in st.session_state.documents}`). Uploading the same file twice does nothing. This prevents accidental double-context.

---

## How to Rebuild This From Scratch With Claude Code

This section exists specifically for demo purposes — to show that a CLAUDE.md file alone is sufficient for Claude Code to recreate a production-ready tool.

**Steps for the demo:**

1. Create a new empty folder
2. Copy only this `CLAUDE.md` file into it
3. Open Claude Code in that folder
4. Say: *"Build the application described in CLAUDE.md"*

Claude Code will:
- Read this file as its specification
- Create `app.py` with all five tabs and the dual-backend architecture
- Create `requirements.txt` with the correct dependencies
- Create `.env.example`
- Implement the exact privacy model described above

**Why this works:**  
Claude Code treats `CLAUDE.md` as authoritative project instructions. A sufficiently detailed CLAUDE.md functions as a machine-readable specification — not just documentation for humans. Every architectural decision documented here (streaming pattern, session state keys, system prompts, privacy routing) gives Claude Code enough context to make correct implementation choices without ambiguity.

**What to emphasize in the demo:**
- The CLAUDE.md was written *by* Claude Code after building the app, then used to *rebuild* it — a self-documenting development loop
- The privacy model (which tabs send data where) was a human design decision captured in the CLAUDE.md, not something Claude inferred
- Claude Code can iterate on the rebuild interactively — show attendees they can say "add a 6th tab for competitor comparison" and it extends the spec

---

## What This App Is Not

- **Not a RAG system**: Documents are injected as raw text into the context window, not chunked and embedded. This is intentional for demo simplicity. For production with large document sets, replace `docs_context()` with a vector search (ChromaDB + sentence-transformers).
- **Not a web search tool**: The Public Research tab requires manual paste. For automated web retrieval, integrate a search API (Tavily, Serper) and expose it as a tool call.
- **Not multi-user**: Session state is per-browser-session. For multi-user deployment, move state to a database.
- **Not OCR-capable**: `pypdf` extracts text from text-based PDFs only. Scanned documents require an OCR step (e.g. `pytesseract`, Azure Document Intelligence).
