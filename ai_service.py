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
      "relationship": "<short label, < 15 words>",
      "strength": 0.5,
      "explanation": "<A detailed paragraph (3-5 sentences) explaining HOW and WHY these two topics intersect. Describe the conceptual bridge between them, what shared principles or dependencies exist, and how understanding one deepens understanding of the other.>"
    }}
  ],
  "blindspots": [
    {{
      "suggestion": "<a topic or concept the user should explore next>",
      "category": "<e.g. prerequisite, adjacent, deeper-dive>",
      "why_important": "<2-3 sentences explaining WHY the user should focus on this topic. What gap does it fill? What risks come from not knowing it?>",
      "how_it_helps": "<2-3 sentences explaining HOW learning this will make the user better. What concrete skills or understanding will they gain?>"
    }}
  ],
  "enhanced_summary": "<An enriched version of the user's summary. Keep their original meaning and voice but add: (1) technical precision and correct terminology, (2) important details or nuances they may have missed, (3) connections to broader concepts, (4) what they should pay special attention to going forward. This should be 2-3 paragraphs, substantively richer than the original.>"
}}

Rules:
- connections array should only reference IDs from the previous entries listed above. If there are no previous entries return an empty array [].
- Provide 2-5 blindspot suggestions.
- Keep relationship descriptions concise (< 15 words). The explanation field is where you provide the detailed analysis.
- The enhanced_summary should be meaningfully richer than the original summary, adding technical depth and learning-critical context.
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


def enhance_notes(topic: str, skills: list[str], summary: str) -> str:
    """Return an enhanced version of the user's study notes."""
    prompt = f"""You are a learning-analytics assistant. The user wrote the following study notes and wants them enhanced with more technical depth and detail.

**Topic:** {topic}
**Skills:** {', '.join(skills)}
**Original Notes:**
{summary}

Write an enriched version of these notes that:
1. Keeps the user's original meaning and voice
2. Adds technical precision and correct terminology
3. Fills in important details or nuances they may have missed
4. Connects ideas to broader concepts in the field
5. Highlights what they should pay special attention to going forward

Return ONLY the enhanced text (2-3 paragraphs). No JSON, no markdown fences, no preamble."""
    return _chat(prompt).strip()
