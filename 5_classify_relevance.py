"""
5_classify_relevance.py — Cardiac-Regenerative-Lab-Autocrawler
Virelion Biotech

Loads everything harvested in steps 1-4 (papers, grants, trials, crawled lab
pages), normalizes each into a lightweight text candidate, and uses Claude to
classify each as in- or out-of-domain per the inclusion/exclusion taxonomy in
config.py (e.g. excluding general interventional cardiology or non-cardiac
stem cell work that isn't actually about cardiac regeneration).

Classification happens in batches (default 10 candidates/call) to control
API cost while keeping the model's context small enough for reliable JSON
output.

Output: data/<year>/filtered.json
    A list of the original records that passed classification, each with
    classification metadata attached (confidence, reason) and a
    "record_type" field (papers/grants/trials/lab_pages) so step 6 knows
    how to interpret it.

Usage:
    python 5_classify_relevance.py
"""

import json
import time
from typing import Any

import anthropic

import config

BATCH_SIZE = 10
API_RETRY_DELAY = 2.0
MAX_RETRIES = 2

INCLUSION_CRITERIA = """
INCLUDE if the item describes active research, funding, or a clinical trial on:
- Myocardial repair or regeneration via cell transplantation
- Direct cardiac cell lineage reprogramming
- Cardiac tissue engineering (engineered heart tissue, cardiac patches, decellularized matrices, 3D bioprinting)
- Biological pacing / bioartificial pacemakers
- Stem cell-derived cardiomyocytes (hiPSC-CM, ESC-CM) for cardiac repair
- Electromechanical integration or arrhythmia risk specifically in the context of regenerative cardiac grafts

EXCLUDE if the item is primarily about:
- Standard interventional cardiology (stenting, catheterization) with no regenerative component
- General electrophysiology/ablation unrelated to regenerative grafts
- General stem cell biology with no cardiac application
- Cardiology clinical care/diagnostics with no regenerative research angle
""".strip()


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# Loading & normalizing candidates from all four sources
# ---------------------------------------------------------------------------

def _load_json(key: str) -> list[dict[str, Any]]:
    path = config.run_path(key)
    if not path.exists():
        print(f"  [warn] {path.name} not found — skipping this source (did you run the harvest step for it?)")
        return []
    with open(path) as f:
        return json.load(f)


def normalize_candidates() -> list[dict[str, Any]]:
    """
    Builds a flat list of {id, record_type, source_index, text} candidates
    from all four raw data files, keeping a pointer back to the original
    full record so filtered.json can carry the complete original data.
    """
    candidates = []

    papers = _load_json("raw_papers")
    for i, rec in enumerate(papers):
        text = f"{rec.get('title', '')}\n\n{rec.get('abstract', '')}".strip()
        if text:
            candidates.append({"id": f"papers_{i}", "record_type": "papers", "source_index": i, "text": text[:3000]})

    grants = _load_json("raw_grants")
    for i, rec in enumerate(grants):
        text = f"{rec.get('title', '')}\n\n{rec.get('abstract', '')}".strip()
        if text:
            candidates.append({"id": f"grants_{i}", "record_type": "grants", "source_index": i, "text": text[:3000]})

    trials = _load_json("raw_trials")
    for i, rec in enumerate(trials):
        conditions = ", ".join(rec.get("conditions", []))
        interventions = ", ".join(rec.get("interventions", []))
        text = (
            f"{rec.get('title', '')}\n\n"
            f"Conditions: {conditions}\nInterventions: {interventions}\n\n"
            f"{rec.get('brief_summary', '')}"
        ).strip()
        if text:
            candidates.append({"id": f"trials_{i}", "record_type": "trials", "source_index": i, "text": text[:3000]})

    patents = _load_json("raw_patents")
    for i, rec in enumerate(patents):
        text = f"{rec.get('title', '')}\n\n{rec.get('abstract', '')}".strip()
        if text:
            candidates.append({"id": f"patents_{i}", "record_type": "patents", "source_index": i, "text": text[:3000]})

    lab_pages = _load_json("raw_lab_pages")
    for i, rec in enumerate(lab_pages):
        text = f"{rec.get('title', '')}\n\n{rec.get('text', '')}".strip()
        if text:
            candidates.append({"id": f"lab_pages_{i}", "record_type": "lab_pages", "source_index": i, "text": text[:3000]})

    return candidates


# ---------------------------------------------------------------------------
# Claude classification
# ---------------------------------------------------------------------------

def build_batch_prompt(batch: list[dict[str, Any]]) -> str:
    items_block = "\n\n".join(
        f"--- ITEM {c['id']} ---\n{c['text']}" for c in batch
    )
    return f"""You are classifying research items for a cardiac regeneration lab discovery database.

{INCLUSION_CRITERIA}

Classify each item below. Respond with ONLY a JSON array, no other text, no markdown fences.
Each element must have exactly these fields:
- "id": the item id exactly as given
- "include": true or false
- "confidence": a number from 0.0 to 1.0
- "reason": a brief (one sentence) justification

{items_block}"""


def classify_batch(client: anthropic.Anthropic, batch: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Calls Claude once for a batch of candidates. Returns a dict mapping
    candidate id -> {include, confidence, reason}. On unparseable output,
    retries up to MAX_RETRIES times before giving up on the batch (those
    candidates are then excluded by default, logged as needing review).
    """
    prompt = build_batch_prompt(batch)

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()

            # Defensive: strip markdown fences if the model added them despite instructions
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            decisions = json.loads(raw_text)
            return {d["id"]: d for d in decisions if "id" in d}

        except (json.JSONDecodeError, anthropic.APIError) as e:
            print(f"    [warn] batch classification attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(API_RETRY_DELAY)

    print(f"    [warn] giving up on batch after {MAX_RETRIES + 1} attempts — "
          f"{len(batch)} items will be excluded by default and flagged for manual review")
    return {
        c["id"]: {"id": c["id"], "include": False, "confidence": 0.0, "reason": "CLASSIFICATION_FAILED_NEEDS_REVIEW"}
        for c in batch
    }


def classify_all(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    client = _client()
    all_decisions = {}

    num_batches = (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num in range(num_batches):
        batch = candidates[batch_num * BATCH_SIZE: (batch_num + 1) * BATCH_SIZE]
        print(f"  Classifying batch {batch_num + 1}/{num_batches} ({len(batch)} items)...")
        decisions = classify_batch(client, batch)
        all_decisions.update(decisions)

    return all_decisions


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main():
    config.check_required_env_vars()
    config.ensure_run_dir()

    print("Loading and normalizing candidates from all four sources...")
    candidates = normalize_candidates()
    print(f"  -> {len(candidates)} total candidates to classify\n")

    if not candidates:
        print("No candidates found. Did steps 1-4 run successfully?")
        with open(config.run_path("filtered"), "w") as f:
            json.dump([], f, indent=2)
        return

    decisions = classify_all(candidates)

    # Reload raw source files once (not per-candidate) to attach full original records
    raw_by_type = {
        "papers": _load_json("raw_papers"),
        "grants": _load_json("raw_grants"),
        "trials": _load_json("raw_trials"),
        "patents": _load_json("raw_patents"),
        "lab_pages": _load_json("raw_lab_pages"),
    }

    filtered = []
    needs_review = []
    excluded_count = 0

    for c in candidates:
        decision = decisions.get(c["id"])
        if decision is None:
            continue  # model dropped this id from its response; treat as excluded

        original_record = raw_by_type[c["record_type"]][c["source_index"]]

        if decision["reason"] == "CLASSIFICATION_FAILED_NEEDS_REVIEW":
            needs_review.append({**original_record, "record_type": c["record_type"]})
            continue

        if decision.get("include"):
            filtered.append({
                **original_record,
                "record_type": c["record_type"],
                "classification_confidence": decision.get("confidence"),
                "classification_reason": decision.get("reason"),
            })
        else:
            excluded_count += 1

    out_path = config.run_path("filtered")
    with open(out_path, "w") as f:
        json.dump(filtered, f, indent=2)

    if needs_review:
        review_path = config.CURRENT_RUN_DIR / "needs_manual_review.json"
        with open(review_path, "w") as f:
            json.dump(needs_review, f, indent=2)
        print(f"\n[!] {len(needs_review)} items failed classification and were written to {review_path} for manual review.")

    print(f"\nDone. {len(filtered)} included, {excluded_count} excluded, {len(needs_review)} needs review.")
    print(f"Wrote filtered candidates to {out_path}")


if __name__ == "__main__":
    main()
