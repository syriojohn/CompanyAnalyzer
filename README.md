# Company Analyzer

AI-powered due diligence tool for M&A document analysis. Upload confidential deal documents, extract risks, ask questions, and generate management memos — with a choice of running privately on your machine or via the Claude API.

---

## What It Does

| Feature | Description |
|---|---|
| 📁 Document Upload | Upload multiple PDF and DOCX files |
| 🔍 Deal Analysis | Summarize the deal and extract risks (layoffs, asset sales, regulatory issues, data gaps) |
| 🔒 Private Q&A | Ask questions answered only from your documents |
| 🌐 Public Research | Paste web findings and ask questions using Claude's general knowledge |
| 📝 Management Memo | Generate a structured memo comparing private documents vs public research |
| 🖥️ Local Mode | Run Analysis and Q&A entirely on your machine via Ollama — private docs never leave |

---

## Prerequisites

- **Python 3.10 or higher** — https://www.python.org/downloads/
- **Git** — https://git-scm.com/downloads
- **An Anthropic API key** — https://console.anthropic.com (free tier available)
- **Ollama** *(optional, for Local mode)* — https://ollama.com/download

---

## Setup on a New Machine

### 1. Clone the repository

```powershell
git clone https://github.com/syriojohn/CompanyAnalyzer.git
cd CompanyAnalyzer
```

### 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 3. Add your API key

```powershell
copy .env.example .env
```

Open `.env` in any text editor and replace `your_api_key_here` with your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Run the app

```powershell
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**

---

## Local Mode Setup (Optional)

Local mode keeps your private documents on your machine — nothing is sent to the cloud for Analysis and Q&A. Requires Ollama.

### 1. Install Ollama

Download and install from https://ollama.com/download

### 2. Start the Ollama server

```powershell
ollama serve
```

### 3. Download a model

```powershell
ollama pull llama3.2        # recommended — 2GB, fast
# or
ollama pull mistral         # 4GB, stronger reasoning
```

### 4. Switch to Local mode in the app

Use the **Private Document Mode** dropdown in the sidebar to switch between Cloud and Local.

---

## Usage Flow

```
1. Documents tab  →  Upload your PDF / DOCX files
2. Analysis tab   →  Click "Summarize Deal" and "Extract Risks"
3. Private Q&A    →  Ask questions about the documents
4. Public Research→  Paste web findings, ask public questions
5. Memo tab       →  Generate and download the management memo
```

---

## Privacy Model

| Tab | What gets sent to the cloud |
|---|---|
| Documents | Nothing — text is extracted locally |
| Analysis (Cloud mode) | Full document text → Anthropic API |
| Analysis (Local mode) | Nothing — processed by Ollama on your machine |
| Private Q&A (Cloud mode) | Full document text → Anthropic API |
| Private Q&A (Local mode) | Nothing — processed by Ollama on your machine |
| Public Research | Only your pasted research text — never private documents |
| Memo | AI-generated summaries + pasted research (not raw documents) |

> Anthropic does not train on API data. See https://www.anthropic.com/privacy

---

## Sample Documents

Three fictional M&A documents are included for testing:

- `01_Dolphin_Intel_Acquisition_Proposal_FICTIONAL.docx`
- `02_Dolphin_Intel_Disclosure_Schedule_FICTIONAL.docx`
- `03_Dolphin_Board_Briefing_Note_FICTIONAL.docx`

These are entirely made up and safe to use for demos.

---

## After a Reboot

Streamlit and Ollama do not auto-start. Run these before opening the app:

```powershell
ollama serve                          # only needed for Local mode
streamlit run app.py
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| `ANTHROPIC_API_KEY not set` | Check your `.env` file exists and has the key |
| Ollama not detected | Run `ollama serve` in a terminal, keep it open |
| Tables missing from DOCX | Re-upload the file — older cached extractions used a buggy parser |
| App not loading | Check nothing else is using port 8501 |
