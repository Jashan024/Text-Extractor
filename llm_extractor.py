import json
import os

from cerebras.cloud.sdk import Cerebras

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("CEREBRAS_API_KEY")
        if not api_key:
            raise RuntimeError("CEREBRAS_API_KEY not set")
        _client = Cerebras(api_key=api_key)
    return _client


SYSTEM_PROMPT = (
    "You are a precise data-extraction tool. You always return valid JSON "
    "matching the schema the user gives you. You never invent data."
)

USER_PROMPT_TEMPLATE = """Extract every distinct person from the text below.

For each person, return three fields:
- name: full name only. Strip credentials/suffixes like RN, BSN, MBA, MD, PhD, DDS, DO, NP, etc. Strip "Dr." prefix.
- location: any geographic location associated with the person (city, region, state, country, or any combination). If the text contains something that looks like a place — return it verbatim. Examples that ALL count as valid locations: "Boston, MA", "Boston, MA, USA", "Boston, Massachusetts", "Burlington, Vermont, United States", "Greater New York Area", "London", "Pittsburgh, PA". Only return empty string if NO place name appears at all. Do NOT include labels like "Location:".
- title: current or most-recent job title; otherwise empty string. Do NOT include the company name.

Rules:
- Do NOT invent data. Missing field => empty string.
- Skip placeholders like "LinkedIn Member" only if no real name is given.
- Skip duplicates (same person appearing twice).
- Ignore navigation/UI noise (followers, "Send message", "Save to project", page numbers, etc.).
- The text may come from Indeed, LinkedIn, SignalHire, LinkedIn Recruiter, or any other recruiter source — handle them all the same way.

Return ONLY a JSON object in this exact shape:
{{
  "people": [
    {{"name": "...", "location": "...", "title": "..."}}
  ]
}}

TEXT:
{text}
"""


def extract_with_llm(text):
    """Send raw recruiter text to Cerebras and return the standard output shape."""
    client = _get_client()
    model = os.environ.get("CEREBRAS_MODEL", "llama3.1-8b")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(text=text)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    people_in = data.get("people", []) or []

    names, locations, titles, structured = [], [], [], []
    for p in people_in:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "").strip()
        loc = (p.get("location") or "").strip()
        title = (p.get("title") or "").strip()

        if not name:
            continue

        if name not in names:
            names.append(name)
        if loc and loc not in locations:
            locations.append(loc)
        if title and title not in titles:
            titles.append(title)

        structured.append({
            "name": name,
            "location": loc,
            "titles": [title] if title else [],
        })

    return {
        "names": names,
        "locations": locations,
        "titles": titles,
        "people": structured,
    }
