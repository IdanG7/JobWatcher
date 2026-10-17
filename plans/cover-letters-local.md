# Cover letters from a local model

Goal: write a cover letter for any posting with no API key. A local model
(Ollama, on this PC) writes it from the resume, the posting and the closest of
several past letters. Nothing leaves the computer. Gemini is removed.

Decided with the user (2026-10-17): local model only (no Claude CLI, no
copy-prompt flow, no Gemini); several past letters, picked automatically.

## Steps

1. **Ollama client** (`intel/cover_letter.py`). Replace the Gemini client.
   - `status()`: is Ollama running at `http://127.0.0.1:11434`, its version,
     installed models.
   - `generate(model, prompt)`: `/api/chat`, non-streaming, `num_ctx` 12288,
     temperature 0.5, `think: false`; strip any `<think>…</think>` block.
   - `pull(model, progress)`: `/api/pull` streaming, reports bytes done/total.
   - Plain errors: not installed/running (link to ollama.com/download), model
     missing, timed out, out of memory.
   - Done when: tests with a stubbed HTTP layer cover each path.

2. **Past letter library.** kv `cover_references`: a list of
   `{id, filename, text, added_at}`, up to 10, each 200+ characters. The single
   `cover_reference` saved today moves into it at startup (the Equity Research
   letter carries over). Routes: list, add, remove.
   - Done when: tests for add/remove/limits and the migration.

3. **Pick the closest letters per posting.** Score each letter against the
   posting by word overlap (TF-IDF cosine; title words count double), plus a
   bonus when the letter names the posting's role family (from the taxonomy,
   e.g. Equity Research, M&A). Use the best letter, and a second one when it
   scores close. The letter shows which ones were used.
   - Done when: an ER letter is picked for an ER posting and an IB letter for
     an M&A posting from a mixed library.

4. **Prompt.** Keep today's rules (resume facts only, ignore instructions in
   the posting, no placeholders). Up to two reference letters. Trim inputs to
   fit a local context: posting 8k, resume 8k, each letter 6k characters.

5. **Writing.** `POST /api/jobs/<key>/cover-letter` uses the chosen model
   (kv `cover_model`; default `llama3.1:8b`, else the first installed model).
   The saved letter records the model and the letters used. About 20–60 s on
   a GTX 1080.

6. **Model download.** A button starts `ollama pull llama3.1:8b` in the
   background; Settings shows progress and can be left while it runs.

7. **UI.**
   - Settings › Cover letters: "Writing model" (Ollama status with an install
     link, model picker, download button with progress) and "Past cover
     letters" (add several, remove each).
   - Posting panel: "Set up a writing model in Settings" when it isn't ready;
     "Based on <letter names>" under a written letter.
   - Done when: checked in the browser against a stub Ollama server; the real
     model is checked once Ollama is installed.

8. **Clean-up and docs.** Remove the Gemini code, routes, tests and copy.
   Foothold stops reading `ai.local.json` but does not delete it. Update
   PRODUCT.md and README.

## Not in scope

Streaming the letter as it is written; choosing letters by hand per posting;
releasing (asked separately).

## After the real test (October 17, 2026)

Letters written from Idan's resume and his equity research letter, for three
postings (Barclays equity research, William Blair IB, Manulife treasury).

- First, writing a new letter in the past letter's style: the model mixed the
  letter and the resume, misplaced numbers and claimed posting duties as done.
  Hiding the past letter's facts made it worse: it lost "CFA Level I Candidate"
  and wrote "preparing for the CFA" instead.
- Idan's direction: the past letter is current and is the template. Take the
  closest one and change only specific sentences, nothing drastic.
- So now `build_prompt` returns (system, user) messages: with a past letter,
  ADAPT keeps it word for word except the date, recipient, company, role, team
  and the why-this-firm/role sentences; without one, SYSTEM writes from the
  resume (date ranges labelled ended/ongoing, closing checklist).
- `pick_reference` returns the single closest letter. The date follows the
  letter's style ("October 17th"); the recipient block takes the posting's
  location as given (the model had invented a ZIP code).
- "Ask for a change" under the letter: `revise_prompt` / POST
  `.../cover-letter/revise` makes one requested change to the letter as shown,
  unsaved edits included.
- Settings reads the graphics card and memory (`intel/hardware.py`) and suggests
  models that fit (`suggest_models`). qwen3:8b is the default: it kept facts
  straight better than llama3.1:8b and runs 87% on an 8 GB GTX 1080 (~20 s).
- The closing name follows the resume (`sign_as`); trailing spaces are trimmed.

Adapting with qwen3:8b kept 96% of the words for the Barclays equity research
posting and about 85% for the IB and treasury postings, changing 3 to 8
sentences.
