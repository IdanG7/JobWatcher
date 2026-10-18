"""Run the cover-letter candidates of tests/letters/test_letter_corpus.py through a local model.

The unit tests check the code around the model. This checks the model's part: that it reads each resume's roles
and exams right, and writes from the candidate's past letter, in their words, without leaving a status the resume
has changed since or calling an exam passed that isn't. Needs Ollama running with the model pulled; a candidate
takes a few minutes.

    python tools/letter_eval.py [--model qwen3:8b] [--posting posting.json] [--out DIR] [candidate id ...]

--posting is a JSON file {"title", "company", "location", "description"}; without it every letter is written for
the sample posting below. The letters are written the way the dashboard writes them (generate_cover_letter),
without the header it sets after.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intel import cover_letter, resume_facts  # noqa: E402
from tests.letters.test_letter_corpus import CANDIDATES, TODAY, facts_of  # noqa: E402

POSTING = {
    "title": "Investment Analyst, Summer Internship 2027", "company": "Northlake Capital Partners",
    "location": "Toronto, ON",
    "description": """Northlake Capital Partners is a mid-market private equity and credit firm. Our summer analysts work alongside the deal team from sourcing to close.

What you will do:
- Build three-statement financial models and valuation analyses (DCF, trading comparables, precedent transactions)
- Screen new investment opportunities and draft sections of investment committee memos
- Monitor portfolio company performance and prepare quarterly reporting
- Research industries and present findings to senior team members

What we are looking for:
- An undergraduate degree in progress in finance, accounting, economics or a related field, graduating 2027 or 2028
- Strong Excel and PowerPoint skills; experience with Python or SQL is an asset
- Progress toward the CFA, CPA or a similar designation is an asset
- Clear written and verbal communication and the judgment to work independently
- Attention to detail and the ability to manage several deadlines""",
}

# How a sentence presents a role or exam, for flagging; each flagged sentence is printed to be read.
_NOW = re.compile(r"\b(?:currently|presently|this (?:summer|fall|autumn|winter|spring|term|semester))\b|\bmy current\b|"
                  r"\bI am (?:\w+ing|an?|the)\b|\bI (?:work|manage|serve|lead|run|build|support|prepare|calculate|test|"
                  r"screen|automate|monitor|draft)\b", re.I)
_NOT_YET = re.compile(r"\bcandidate\b|\bpursuing\b|\bpreparing\b|\bworking toward|\bcompleting\b|\bstudying for\b|"
                      r"\b(?:will|plan to|intend to) (?:sit|write|take)\b|\bsitting\b|\bscheduled\b", re.I)
_ENDED = re.compile(r"\b(?:having (?:served|worked)|previously|formerly|former|most recently|during my time|"
                    r"I (?:was|served|worked) (?:as|at|an?|the)\b)", re.I)
_DONE = re.compile(r"\b(?:passed|completed|earned|obtained|hold|holder|achieved|cleared)\b", re.I)
_NUMBER = re.compile(r"\$?\d+(?:,\d{3})*\+?")


def write(model: str, job: dict, resume: str, base: str) -> tuple[dict, str]:
    """(the facts the model read, the letter), as generate_cover_letter writes it."""
    needs = cover_letter.key_requirements(model, job, resume)
    facts = cover_letter.read_facts(model, resume)
    story = cover_letter.check_status(model, {}, resume, base, facts, TODAY)
    messages = cover_letter.build_prompt(job, resume, story, today=TODAY, needs=needs, facts=facts)
    text = cover_letter.sign_as(cover_letter.generate(model, messages), resume)
    text = cover_letter.keep_experiences(story, text, facts)
    text = cover_letter.check_status(model, job, resume, text, facts, TODAY)
    return facts, cover_letter.tailor(model, job, resume, text, needs)


def facts_wrong(read: dict, truth: dict) -> list[str]:
    """Where the model's reading of the resume differs from the truth: a role missed or read as the wrong state,
    a credential missed, given the wrong status or not in the truth at all."""
    wrong = []
    for role in truth["roles"]:
        got = next((r for r in read["roles"] if resume_facts.mentions(role["employer"], r["employer"])), None)
        state = resume_facts.role_state(role["dates"], TODAY)
        if not got:
            wrong.append(f"role {role['employer']} missed")
        elif resume_facts.role_state(got["dates"], TODAY) != state:
            wrong.append(f"role {role['employer']} dated {got['dates']!r}, not {state}")
    names = [c["name"] for c in truth["credentials"]]
    for credential in read["credentials"]:
        name = next((n for n in names if n == credential["name"] or resume_facts.in_full(n, credential["name"])
                     or resume_facts.in_full(credential["name"], n)), None)
        status = dict((c["name"], c["status"]) for c in truth["credentials"]).get(name)
        if name is None:
            wrong.append(f"credential {credential['name']!r} ({credential['status']}) not in the truth")
        elif credential["status"] != status:
            wrong.append(f"credential {name} read as {credential['status']}, not {status}")
        if name in names:
            names.remove(name)
    return wrong + [f"credential {n} missed" for n in names]


def statuses(letter: str, truth: dict) -> dict:
    """The letter's sentences that may give a role or exam the wrong status, by the truth about the resume."""
    found = {"still_current": [], "current_as_past": [], "not_passed": [], "invented_passed": []}

    def names(sentence: str, passed: bool) -> bool:     # "I passed Level I and am a Level II Candidate" is right
        return any((c["status"] == "passed") == passed and resume_facts.in_full(c["name"], sentence)
                   for c in truth["credentials"])
    for item in cover_letter.status_items(letter, truth, TODAY):
        sentence = item["sentence"]
        if item["kind"] == "role" and item["status"] == "ended" and _NOW.search(sentence):
            found["still_current"].append(sentence)
        elif item["kind"] == "role" and item["status"] == "ongoing" and _ENDED.search(sentence):
            found["current_as_past"].append(sentence)
        elif item["kind"] == "credential" and item["status"] == "passed" and _NOT_YET.search(sentence) \
                and not names(sentence, passed=False):
            found["not_passed"].append(sentence)
        elif item["kind"] == "credential" and item["status"] != "passed" and _DONE.search(sentence) \
                and not names(sentence, passed=True):
            found["invented_passed"].append(sentence)
    return {kind: sorted(set(sentences)) for kind, sentences in found.items()}


def _body(letter: str) -> list[str]:
    return [sentence for label, text in cover_letter.letter_sections(letter)[1] if label.isdigit()
            for sentence in cover_letter._SENTENCE.split(text)]


def story(base: str, letter: str) -> dict:
    """How much of the past letter's story the new one keeps: for each sentence of its body (but the first, which
    names the posting it was for), the share of its words one sentence of the new letter has; and its numbers."""
    old, new = _body(base)[1:], [cover_letter._stems(s) for s in _body(letter)]
    shares = []
    for sentence in old:
        stems = cover_letter._stems(sentence)
        if stems:
            shares.append(max((len(stems & n) / len(stems) for n in new), default=0))
    numbers = set(_NUMBER.findall("\n".join(old)))
    return {"sentences": len(shares), "kept": sum(share >= 0.6 for share in shares),
            "mean": round(sum(shares) / len(shares), 2) if shares else None,
            "numbers_lost": sorted(n for n in numbers if n not in letter)}


def evaluate(model: str, candidate: dict, job: dict) -> dict:
    """One candidate's letter for ``job``, and what's wrong with it. ``candidate`` is as in test_letter_corpus;
    without "roles" the model's reading of the resume is taken as the truth."""
    start = time.time()
    read, letter = write(model, job, candidate["resume"], candidate["letter"])
    truth = facts_of(candidate) if "roles" in candidate else read
    lower = letter.lower()
    return {"id": candidate["id"], "seconds": round(time.time() - start),
            "facts_wrong": facts_wrong(read, truth) if "roles" in candidate else None,
            "stale_left": [phrase for phrase in candidate.get("stale", []) if phrase.lower() in lower],
            **statuses(letter, truth),
            "keep_lost": [phrase for phrase in candidate.get("keep", []) if phrase.lower() not in lower],
            "story": story(candidate["letter"], letter), "words": cover_letter.letter_words(letter), "facts": read,
            "letter": letter}


def summary(results: list[dict]) -> dict:
    total = {key: sum(len(r[key] or []) for r in results)
             for key in ("facts_wrong", "stale_left", "still_current", "current_as_past", "not_passed",
                         "invented_passed", "keep_lost")}
    kept = [r["story"] for r in results if r["story"]["sentences"]]
    return {"candidates": len(results), **total,
            "story_kept": f'{sum(s["kept"] for s in kept)}/{sum(s["sentences"] for s in kept)} sentences',
            "numbers_lost": sum(len(r["story"]["numbers_lost"]) for r in results),
            "minutes": round(sum(r["seconds"] for r in results) / 60, 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ids", nargs="*", help="candidates to run (default: all)")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--posting", type=Path, help="a JSON file with the posting to write for")
    parser.add_argument("--out", type=Path, help="a folder to write each letter to")
    args = parser.parse_args()
    job = json.loads(args.posting.read_text(encoding="utf-8")) if args.posting else POSTING
    picked = [c for c in CANDIDATES if not args.ids or c["id"] in args.ids]
    results = []
    for candidate in picked:
        result = evaluate(args.model, candidate, job)
        results.append(result)
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{candidate['id']}.txt").write_text(result["letter"], encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "letter"}, ensure_ascii=False, indent=1), flush=True)
    print(json.dumps(summary(results), indent=1))


if __name__ == "__main__":
    main()
