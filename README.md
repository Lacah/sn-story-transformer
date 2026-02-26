# ServiceNow Story Transformer

Turn any requirements doc or gap analysis into ServiceNow epics and stories, powered by your AI of choice via LiteLLM.

---

## Why this exists

Writing a gap analysis or PRD is one thing. Manually translating it into dozens of epics and user stories in ServiceNow is another matter entirely: tedious, time-consuming, and error-prone.

This tool bridges that gap. Give it any document (a gap analysis, a product requirements doc, a feature list) and it uses AI to extract the intent, structure it into epics and user stories, and push them directly into your ServiceNow Agile 2.0 product, ready for refinement, estimation, and sprint planning.

The workflow fits however you prefer to work. You can run the scripts from a terminal, or use your IDE's integrated terminal and edit the intermediate `stories.json` file in the editor before pushing to ServiceNow. The two-step design is intentional: AI does the heavy lifting, you stay in control of what actually gets created.

### The bigger picture

Requirements rarely start as a clean document. They live in meeting recordings, Miro boards, Figma files, Confluence pages, email threads, and whiteboard photos. Today's AI tools make it easier than ever to consolidate that scattered input into a coherent requirements doc or gap analysis: summarise a transcript, describe a wireframe, pull together notes from multiple sources.

Once you have that document, this tool takes over: turning it into a structured, reviewable backlog in ServiceNow with minimal manual effort. Think of it as the last mile between "we know what we need to build" and "it's in the backlog and ready to plan."

---

## How it works

```
1. analyze_doc.py --input <doc>   →  stories.json   (AI step)
2. create_stories.py              →  ServiceNow      (API step)
```

**Step 1** sends your document to an AI model, which produces a structured `stories.json` file containing epics and user stories.

**Step 2** reads `stories.json` and pushes the records to your ServiceNow instance via the Table API.

`stories.json` is intentionally a human-readable intermediate file. Open it in your editor, review the output, make any adjustments, then run step 2.

---

## Requirements

**Python 3.9+** is required. On macOS and Linux, the command is typically `python3`. On Windows it is usually `python`. Verify your version with:

```bash
python3 --version
```

**pip** is the standard Python package installer and is included with Python 3.4+. If it is missing, run:

```bash
python3 -m ensurepip --upgrade
```

It is recommended to use a **virtual environment** to keep dependencies isolated:

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows
```

Then install the dependencies:

```bash
pip install litellm requests pyyaml python-dotenv
```

| Package | Used by | Purpose |
|---------|---------|---------|
| `litellm` | `analyze_doc.py` | Model-agnostic AI gateway, normalises calls across Anthropic, OpenAI, Gemini, and others |
| `requests` | `create_stories.py` | HTTP client for the ServiceNow Table API |
| `pyyaml` | both | Reads `schema.yaml` |
| `python-dotenv` | both | Loads credentials from `.env` into the environment |

---

## Setup

**1. Copy the example env file and fill in your values:**

```
cp .env.example .env
```

**2. Configure ServiceNow connection** (in `.env`):

```env
SERVICENOW_INSTANCE=https://your-instance.service-now.com
SERVICENOW_PRODUCT_SYS_ID=your_product_sys_id_here
```

**3. Choose an auth method** (in `.env`):

OAuth 2.0 (default):
```env
SERVICENOW_AUTH=oauth
SERVICENOW_CLIENT_ID=your_client_id
SERVICENOW_CLIENT_SECRET=your_client_secret
```

Basic auth:
```env
SERVICENOW_AUTH=basic
SERVICENOW_USERNAME=your_username
SERVICENOW_PASSWORD=your_password
```

**4. Configure an AI model** (in `.env`):

```env
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

If `AI_MODEL` is not set, the script auto-detects from whichever API key is present. Supported providers via [LiteLLM](https://docs.litellm.ai/docs/providers): Anthropic, OpenAI, Google Gemini, Azure OpenAI, Mistral, Cohere, and more.

---

## Usage

**Step 1: Analyse your document**

Run `analyze_doc.py` with the path to your input file (from your terminal or IDE integrated terminal):

```bash
python scripts/analyze_doc.py --input path/to/GAP_ANALYSIS.md
```

This generates `scripts/stories.json`. Open it in your editor, review the epics and stories the AI produced, and make any edits before continuing.

**Step 2: Push to ServiceNow**

```bash
# Preview what would be created (no API calls made):
python scripts/create_stories.py --dry-run

# Create all epics and stories:
python scripts/create_stories.py

# Update content on already-created stories (matched by title):
python scripts/create_stories.py --update
```

---

## Configuration: `schema.yaml`

`scripts/schema.yaml` is the single config file for everything structural. Edit it to customise behaviour without touching the scripts:

| Section | What it controls |
|---------|-----------------|
| `tables` | Target ServiceNow table names (`rm_epic` / `rm_story` by default) and field definitions |
| `priorities` | Human-readable priority keys → ServiceNow numeric values, plus guidance injected into the AI prompt |
| `ai.instructions` | Prompt instructions for how the AI groups epics, formats stories, and writes acceptance criteria |

---

## Make it your own

This project is intentionally minimal. Fork it and tailor it to your workflow:

- **Different tables?** Update `tables` in `schema.yaml` to target any ServiceNow table, not just `rm_epic` / `rm_story`.
- **Different fields?** Add or remove entries under `tables.epic.fields` and `tables.story.fields` with no code changes needed.
- **Different priorities?** Edit the `priorities` section to match your team's values and ServiceNow field options.
- **Different AI behaviour?** Tweak the `ai.instructions` section in `schema.yaml` to change how epics are grouped, how stories are written, or what acceptance criteria look like.
- **Different input format?** The scripts accept any plain text file: markdown, plain text, CSV exports, whatever your team produces.

---

## File reference

| File | Purpose |
|------|---------|
| `scripts/analyze_doc.py` | Step 1: AI analysis, writes `stories.json` |
| `scripts/create_stories.py` | Step 2: ServiceNow API, reads `stories.json` |
| `scripts/schema.yaml` | Shared config for tables, priorities, and AI instructions |
| `.env.example` | Template for credentials, copy to `.env` |
| `scripts/stories.json` | Generated intermediate file (gitignored) |
