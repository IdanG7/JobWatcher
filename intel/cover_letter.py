"""Offline cover-letter drafts. Candidate claims come only from supplied text."""

LIMITS = {"candidate_name": 160, "background": 20000, "motivation": 3000, "content": 30000}


def clean_fields(payload: dict, *, generating: bool = False) -> dict:
    fields = {}
    for key, limit in LIMITS.items():
        if generating and key == "content":
            continue
        value = payload.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"{key} must be text")
        if len(value) > limit:
            raise ValueError(f"{key} must be {limit:,} characters or fewer")
        fields[key] = value.strip()
    required = ("candidate_name", "background") if generating else ("content",)
    for key in required:
        if not fields[key]:
            raise ValueError(f"{key} is required")
    return fields


def generate_letter(job: dict, fields: dict) -> str:
    """Create a plain-text draft without inferring experience from search defaults.

    Background should be candidate-written sentences. It is preserved verbatim;
    the surrounding prose ties it to the selected role without inventing facts.
    """
    title = job.get("title") or "the advertised role"
    company = job.get("company") or "your company"
    skills = [s["label"] for s in (job.get("facts") or {}).get("skills", []) if s.get("label")][:3]
    paragraphs = ["Dear Hiring Team,", f"I am applying for the {title} position at {company}.",
                  fields["background"]]
    if fields["motivation"]:
        paragraphs.append(fields["motivation"])
    if skills:
        paragraphs.append(f"The posting's focus on {', '.join(skills)} particularly interests me. "
                          "I would welcome the opportunity to discuss how my background could support your team.")
    else:
        paragraphs.append("I would welcome the opportunity to discuss how my background could support your team.")
    paragraphs.extend(["Thank you for considering my application.", f"Sincerely,\n{fields['candidate_name']}"])
    return "\n\n".join(paragraphs)
