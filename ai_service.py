"""
AI classification service using Ollama (local, free).

Responsibilities:
  1. Classify a learning entry (domain, sub-topics, complexity).
  2. Find connections to previous entries.
  3. Identify blindspots / suggested next areas to explore.

Requires: Ollama running locally with a model pulled.
  - Install: https://ollama.com
  - Pull a model: ollama pull llama3.2
"""

import json
import os
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def _chat(prompt: str) -> str:
    """Send a prompt to Ollama and return the response text."""
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def classify_entry(topic: str, skills: list[str], summary: str,
                   existing_entries: list[dict]) -> dict:
    """Return classification, connections, and blindspots for a new entry.

    Returns a dict with keys:
        classification: {domain, sub_topics, complexity, key_concepts}
        connections:    [{entry_id, relationship, strength}]
        blindspots:     [{suggestion, category}]
    """
    existing_context = ""
    if existing_entries:
        lines = []
        for e in existing_entries:
            lines.append(
                f"- Entry #{e['id']} | Topic: {e['topic_title']} | "
                f"Skills: {e.get('skills', 'N/A')} | Summary: {e['summary'][:200]}"
            )
        existing_context = (
            "Here are the user's previous learning entries:\n"
            + "\n".join(lines)
        )

    prompt = f"""You are a learning-analytics assistant. The user just logged a study session.

**New entry:**
- Topic/Title: {topic}
- Skills/Courses: {', '.join(skills)}
- Summary: {summary}

{existing_context}

Respond with ONLY valid JSON (no markdown fences, no explanation) matching this exact schema:
{{
  "classification": {{
    "domain": "<broad field, e.g. Software Engineering>",
    "sub_topics": ["<specific sub-topic>"],
    "complexity": "<beginner | intermediate | advanced>",
    "key_concepts": ["<concept>"]
  }},
  "connections": [
    {{
      "entry_id": 0,
      "relationship": "<short description>",
      "strength": 0.5
    }}
  ],
  "blindspots": [
    {{
      "suggestion": "<a topic or concept the user should explore next>",
      "category": "<why – e.g. prerequisite, adjacent, deeper-dive>"
    }}
  ]
}}

Rules:
- connections array should only reference IDs from the previous entries listed above. If there are no previous entries return an empty array [].
- Provide 2-5 blindspot suggestions.
- Keep relationship descriptions concise (< 15 words).
- Output ONLY the JSON object, nothing else.
"""

    raw = _chat(prompt).strip()

    # Strip markdown fences if the model wraps them
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    # Try to extract JSON if there's extra text around it
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    return json.loads(raw)
