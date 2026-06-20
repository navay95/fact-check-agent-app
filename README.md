# 🔎 Fact-Check Agent — The Truth Layer for Marketing PDFs

An AI agent that reads a PDF, pulls out its specific factual claims (stats, dates,
financial/technical figures), checks each one against **live web data**, and reports
back whether it's **Verified**, **Inaccurate** (outdated/stale), or **False** (no
evidence found / contradicted) — with the correct current fact and sources.

Built for the CogCulture Product Management Trainee assessment, Part 2.
Runs on **Google's Gemini API** (free tier via Google AI Studio).

---

## How it works

```
PDF upload
   │
   ▼
1. EXTRACT   pdfplumber pulls raw text out of the PDF
   │
   ▼
2. IDENTIFY  Gemini reads the text and returns a structured JSON list of
             specific, checkable claims — stats, dates, financial figures,
             technical specs, competitor comparisons
   │
   ▼
3. VERIFY    Gemini, with Grounding with Google Search enabled, searches the
             web for each claim and decides: Verified / Inaccurate / False /
             Unverifiable, plus the correct current fact and sources used
   │
   ▼
4. REPORT    Streamlit renders a color-coded verdict card per claim, a summary
             scorecard, the search queries that were run, and CSV/JSON export
```

The verification step uses Google's hosted **Grounding with Google Search** tool —
the model decides what to search for and the search itself runs server-side, so
there's no separate search API key to manage. You only need one secret:
`GEMINI_API_KEY`.

---

## Project structure

```
fact-check-agent/
├── app.py                          # the whole app
├── requirements.txt
├── sample_trap_document.pdf        # test PDF with intentionally wrong/outdated stats
├── _gen_sample_pdf.py              # regenerates the file above (optional, not needed to run the app)
├── .streamlit/
│   ├── config.toml                 # theme
│   └── secrets.toml.example        # copy → secrets.toml for local dev (gitignored)
├── .gitignore
└── README.md
```

---

## Get a free API key

1. Go to **[aistudio.google.com](https://aistudio.google.com)**, sign in with a Google account
2. Click **"Get API key"** in the left sidebar → **Create API key**
3. Copy it (starts with `AIza...`)

This is free for the Flash/Flash-Lite models, rate-limited rather than billed.
Google changes free-tier quotas every few months, so if you hit a quota error,
check the current limits on the AI Studio dashboard.

---

## Run it locally

```bash
git clone <your-repo-url>
cd fact-check-agent
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

export GEMINI_API_KEY=AIza-your-key-here              # macOS/Linux
# setx GEMINI_API_KEY "AIza-your-key-here"             # Windows

streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`), upload
`sample_trap_document.pdf`, and click **Run Fact-Check**.

> If you get a model-not-found or quota error, open the sidebar in the app and
> change the **Model** field — Google renames/retires free-tier model names
> periodically (try `gemini-2.5-flash` or `gemini-2.0-flash` if the default
> doesn't work for your account).

---

## Deploy it live (Streamlit Community Cloud — free, ~5 minutes)

This is the **mandatory** step the assessment asks for.

1. **Push this folder to a new GitHub repo.**
   ```bash
   git init
   git add .
   git commit -m "Fact-Check Agent"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.
3. Click **New app** → pick your repo, branch `main`, and main file path `app.py`.
4. Before clicking Deploy, open **Advanced settings → Secrets** and paste:
   ```toml
   GEMINI_API_KEY = "AIza-your-key-here"
   ```
5. Click **Deploy**. After the build finishes (1–2 minutes) you'll get a URL like
   `https://your-app-name.streamlit.app` — that's the link to submit.

---

## Testing it (what the evaluator will do)

Upload any PDF with factual claims. To see all verdict types at once, use the
included **`sample_trap_document.pdf`**, which intentionally contains:

| Claim in the document | Why it's a trap |
|---|---|
| "ChatGPT was released by OpenAI in 2019" | False — it launched in November 2022 |
| "Apple's iPhone, first launched in 2005" | False — it launched in 2007 |
| "Microsoft's acquisition of LinkedIn in 2014 for $26.2 billion" | False — the deal was announced in 2016 |
| "The global cloud computing market reached $1.3 trillion in 2023" | Inaccurate/outdated — figure doesn't match independent market estimates for that year |
| "As of 2024, Tesla's market capitalization stands at $1.2 trillion" | Inaccurate — stale, since superseded by actual market moves |
| "BrightWave Analytics... 50,000 enterprise clients" | False / no evidence found — BrightWave is a fictional company |

Expected result: the report should flag the false/outdated items above and
explain what the correct, current fact is.

---

## Design decisions & trade-offs

- **Why Gemini + Grounding instead of a separate search API?** Fewer moving
  parts, fewer secrets to manage, and it's free — the model decides *how* to
  search rather than relying on a fixed search-API wrapper.
- **Why a model-name field in the sidebar?** Google's free-tier model names and
  availability shift every few months. Rather than hard-coding a model name
  that might be retired, you can swap it live without touching code.
- **Claim cap (12)** — keeps each run fast and within free-tier rate limits.
  Raise `MAX_CLAIMS` in `app.py` for denser documents (watch your daily quota).
- **No OCR** — this MVP assumes a text-based PDF (the overwhelming majority of
  marketing collateral). Scanned/image-only PDFs would need an OCR pre-pass.
- **Verdicts are AI-generated.** They're a fast first pass, not a legal or
  compliance sign-off — the report includes sources so a human can spot-check.

## Possible next steps

- Add OCR fallback for scanned PDFs.
- Batch mode (multiple PDFs at once) and a history view across past reports.
- Swap the claim cap for pagination so very long documents get full coverage.
- Add an Anthropic/Claude fallback path for higher-volume or higher-accuracy needs.

---

## Tech stack

`Streamlit` · `Google Gemini API (Grounding with Google Search)` · `pdfplumber` · `pandas`
