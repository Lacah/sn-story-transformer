#!/usr/bin/env python3
"""
analyze_doc.py — Document → stories.json via AI

Reads an input document (e.g. GAP_ANALYSIS.md), analyses it with an AI model,
and writes stories.json — a structured backlog of epics and stories ready for
create_stories.py to push to ServiceNow.

Usage:
    python analyze_doc.py --input GAP_ANALYSIS.md

    Then run:
    python create_stories.py

AI model configuration (in .env):
    Set AI_MODEL to your provider's model string, plus the matching API key.
    If AI_MODEL is not set, the script auto-detects from whichever API key is present.

    Examples:
        AI_MODEL=claude-sonnet-4-6    + ANTHROPIC_API_KEY=...
        AI_MODEL=gpt-4o               + OPENAI_API_KEY=...
        AI_MODEL=gemini/gemini-1.5-pro + GEMINI_API_KEY=...

    See .env.example for a full provider reference.

Requirements:
    pip install litellm pyyaml python-dotenv
"""

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")

try:
    import litellm
    litellm.suppress_debug_info = True
except ImportError:
    sys.exit("Missing dependency: pip install litellm")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(SCRIPT_DIR, "schema.yaml")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "stories.json")

# Ordered list of (env key, default model) for auto-detection.
# The first key that is set in the environment wins.
_MODEL_DEFAULTS = [
    ("ANTHROPIC_API_KEY",  "claude-sonnet-4-6"),
    ("OPENAI_API_KEY",     "gpt-4o"),
    ("GEMINI_API_KEY",     "gemini/gemini-1.5-pro"),
    ("AZURE_API_KEY",      "azure/gpt-4o"),
    ("MISTRAL_API_KEY",    "mistral/mistral-large-latest"),
    ("COHERE_API_KEY",     "command-r-plus"),
]


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def resolve_model() -> str:
    """Return the AI model to use, auto-detecting from available API keys if needed."""
    model = os.getenv("AI_MODEL", "").strip()
    if model:
        return model

    for env_key, default_model in _MODEL_DEFAULTS:
        if os.getenv(env_key, "").strip():
            print(f"  AI_MODEL not set — detected {env_key}, defaulting to {default_model}")
            return default_model

    sys.exit(
        "\nCould not determine which AI model to use.\n\n"
        "Add AI_MODEL and a provider API key to your .env file. Examples:\n\n"
        "  Anthropic Claude  →  AI_MODEL=claude-sonnet-4-6    + ANTHROPIC_API_KEY=sk-ant-...\n"
        "  OpenAI GPT        →  AI_MODEL=gpt-4o               + OPENAI_API_KEY=sk-...\n"
        "  Google Gemini     →  AI_MODEL=gemini/gemini-1.5-pro + GEMINI_API_KEY=...\n\n"
        "See .env.example for the full provider reference."
    )


def load_schema() -> dict:
    if not os.path.exists(SCHEMA_FILE):
        sys.exit(
            f"\nschema.yaml not found at: {SCHEMA_FILE}\n"
            "Make sure schema.yaml is in the same directory as this script."
        )
    with open(SCHEMA_FILE) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_prompt(schema: dict, document: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) constructed from the schema's AI instructions."""
    ai = schema.get("ai", {}).get("instructions", {})
    priorities = schema.get("priorities", {})

    priority_block = "\n".join(
        f'  - "{key}": {cfg["guidance"]}'
        for key, cfg in priorities.items()
    )

    system_prompt = f"""You are a skilled business analyst. Analyse the provided document and \
produce a structured JSON backlog of epics and user stories.

EPIC GROUPING:
{ai.get("grouping", "Group related items into 3–7 logical epics.")}

STORY FORMAT:
{ai.get("story_format", "Write each user story as: As a <role>, I want <goal> so that <benefit>.")}

STORY DESCRIPTION FORMAT:
{ai.get("description_format", "Include a reference ID, the user story, and the current state.")}

ACCEPTANCE CRITERIA:
{ai.get("acceptance_criteria", "Provide 5–8 specific, testable criteria per story as plain text strings.")}

PRIORITY — use exactly these string keys:
{priority_block}

OUTPUT — return ONLY this JSON structure, no markdown fences, no explanation:
{{
  "epics": [
    {{
      "key": "snake_case_identifier",
      "short_description": "Epic title (50–80 chars)",
      "description": "One-paragraph epic summary",
      "stories": [
        {{
          "gap_id": "X-1",
          "short_description": "Story title (50–80 chars)",
          "description": "Reference line\\n\\nUser story sentence.\\n\\nCurrent state: ...",
          "acceptance_criteria": [
            "First testable criterion",
            "Second testable criterion"
          ],
          "priority": "critical"
        }}
      ]
    }}
  ]
}}

RULES:
- Include "gap_id" only if a reference ID exists in the source document; omit the field otherwise.
- Return ONLY the JSON object — no markdown code fences, no preamble, no commentary.
"""

    user_prompt = (
        "Analyse the following document and produce the JSON backlog described above.\n\n"
        "--- DOCUMENT START ---\n"
        f"{document}\n"
        "--- DOCUMENT END ---"
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# AI call
# ---------------------------------------------------------------------------

def call_ai(model: str, system_prompt: str, user_prompt: str) -> str:
    """Call the AI model via LiteLLM and return the raw response text."""
    print(f"  Sending to {model} ...")
    print("  This may take 15–60 seconds for larger documents.\n")

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,  # low temperature for consistent structured output
    )
    return response.choices[0].message.content


def extract_json(raw: str) -> dict:
    """Parse JSON from the AI response, stripping markdown fences if the model added them."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        sys.exit(
            f"\nFailed to parse the AI response as JSON: {exc}\n\n"
            "First 500 characters of the response:\n"
            f"{cleaned[:500]}\n\n"
            "Try running again — this can happen if the model wrapped the output in unexpected text."
        )


# ---------------------------------------------------------------------------
# Validation and output
# ---------------------------------------------------------------------------

def validate_structure(data: dict, schema: dict) -> None:
    """Warn about any structural issues in the generated data."""
    epics = data.get("epics", [])
    if not epics:
        sys.exit(
            "\nThe AI returned no epics. "
            "The input document may not contain enough structured content, "
            "or the model may have returned a response in an unexpected format."
        )

    valid_priorities = set(schema.get("priorities", {}).keys())
    warnings = []

    for epic in epics:
        if not epic.get("stories"):
            warnings.append(f"  Epic '{epic.get('short_description', '?')}' has no stories.")
        for story in epic.get("stories", []):
            p = story.get("priority", "")
            if p not in valid_priorities:
                warnings.append(
                    f"  Story '{story.get('short_description', '?')}' has unknown priority "
                    f"'{p}' — valid values: {', '.join(valid_priorities)}"
                )

    if warnings:
        print("Warnings (review stories.json before running create_stories.py):")
        for w in warnings:
            print(w)
        print()


def print_summary(data: dict, schema: dict) -> None:
    priorities = schema.get("priorities", {})
    epic_count  = len(data.get("epics", []))
    story_count = sum(len(e.get("stories", [])) for e in data.get("epics", []))

    print(f"Generated {epic_count} epics, {story_count} stories:\n")
    for epic in data["epics"]:
        stories = epic.get("stories", [])
        print(f"  [{epic['key']}] {epic['short_description']} — {len(stories)} stories")
        for story in stories:
            gap   = f"[{story['gap_id']}] " if story.get("gap_id") else ""
            label = priorities.get(story.get("priority", ""), {}).get("label", story.get("priority", "?"))
            print(f"      {gap}{story['short_description']}  [{label}]")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse a document with AI and produce stories.json "
            "for create_stories.py to push to ServiceNow."
        )
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to the input document (e.g. GAP_ANALYSIS.md, requirements.txt)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"Input file not found: {args.input}")

    print(f"\n=== analyze_doc.py ===\n")
    print(f"  Input    : {os.path.abspath(args.input)}")
    print(f"  Schema   : {SCHEMA_FILE}")
    print(f"  Output   : {OUTPUT_FILE}\n")

    schema = load_schema()
    model  = resolve_model()
    print(f"  Model    : {model}\n")

    with open(args.input) as f:
        document = f.read()

    system_prompt, user_prompt = build_prompt(schema, document)
    raw_response = call_ai(model, system_prompt, user_prompt)

    data = extract_json(raw_response)
    validate_structure(data, schema)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written  : {OUTPUT_FILE}\n")

    print_summary(data, schema)

    print("Review stories.json, then create the records in ServiceNow:\n")
    print("    python create_stories.py\n")


if __name__ == "__main__":
    main()
