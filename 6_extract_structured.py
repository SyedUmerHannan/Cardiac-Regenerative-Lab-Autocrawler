"""
6_extract_structured.py — Cardiac-Regenerative-Lab-Autocrawler
Virelion Biotech

Converts filtered.json (step 5's output) into structured lab profile
candidates matching the extraction schema from the README.

Design: for papers/grants/trials, PI names, institution, and location are
already available as structured fields from steps 1-3's parsing — pulling
those out deterministically is more reliable than asking an LLM to re-derive
facts it doesn't need to guess at. Claude is used for the parts that
genuinely require judgment: categorizing research focus (cell/gene sources,
bioengineering constructs, functional vectors), translational stage, and
experimental model systems from free text — and, for crawled lab pages
(unstructured HTML text with no pre-parsed fields), extracting identity and
affiliation fields too.

Note: geographic coordinates are left null in this step. Geocoding city/
country into lat/long requires a separate geocoding API (e.g. Nominatim)
not yet wired up — a reasonable fast-follow addition to this script.

Output: data/<year>/labs_extracted.json
    A list of lab profile candidates (not yet deduplicated — that's step 7).

Usage:
    python 6_extract_structured.py
"""

import json
import time
from typing import Any

import anthropic

import config

BATCH_SIZE = 5  # smaller than step 5's batch size — schema per item is larger
API_RETRY_DELAY = 2.0
MAX_RETRIES = 2

TRANSLATIONAL_STAGES = [
    "Discovery/Basic Science",
    "Preclinical (Small Animal)",
    "Preclinical (Large Animal)",
    "Clinical Trial Phase I",
    "Clinical Trial Phase II",
    "Clinical Trial Phase III",
]

EXTRACTION_SCHEMA_INSTRUCTIONS = f"""
For each item, produce a lab profile object with exactly these fields:
- "id": the item id exactly as given
- "pi_full_name": string (use the known PI name if provided; otherwise extract from text; empty string if unknown)
- "department": string (empty if unknown)
- "institution": string (use known institution if provided; otherwise extract from text)
- "city": string (empty if unknown)
- "country": string (empty if unknown)
- "cell_gene_sources": array of strings, from: hiPSC-CM, ESC-CM, direct reprogramming, cardiac progenitor cells, mRNA therapy, other (only include ones actually evidenced in the text)
- "constructs_bioengineering": array of strings, from: engineered heart tissue, cardiac patch, 3D bioprinting, decellularized matrix, other
- "functional_vectors": array of strings, from: biological pacing, electromechanical integration, arrhythmia mitigation, vascularization, metabolic maturation, other
- "experimental_models": array of strings, from: in vitro, small animal, large animal
- "translational_stage": exactly one of {TRANSLATIONAL_STAGES}
- "lab_url": string, only if a URL is present in the source data (empty otherwise — do not guess a URL)
- "contact": string, only if an email or contact is present in the source data (empty otherwise)

Only include a category tag if the text actually provides evidence for it. Do not guess.
""".strip()


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# Deterministic pre-extraction of known fields (papers / grants / trials)
# ---------------------------------------------------------------------------

def _known_fields_for_record(rec: dict[str, Any]) -> dict[str, Any]:
    """
    Pulls out PI name / institution / location fields that are already
    structured from steps 1-3, so Claude doesn't have to re-derive facts
    that are already known with certainty. Returns {} for lab_pages, which
    have no pre-parsed structured fields.
    """
    record_type = rec.get("record_type")

    if record_type == "papers":
        authors = rec.get("authors", [])
        pi_name = ""
        institution = ""
        if authors:
            # Use the last-listed author as a heuristic for senior/PI author
            # (common convention in biomedical papers); true PI resolution
            # happens properly in step 7 via entity resolution.
            last_author = authors[-1]
            pi_name = f"{last_author.get('fore_name', '')} {last_author.get('last_name', '')}".strip()
            institution = last_author.get("affiliation", "")
        return {"pi_full_name": pi_name, "institution": institution, "doi": rec.get("doi", "")}

    if record_type == "grants":
        pis = rec.get("principal_investigators", [])
        pi_name = pis[0].get("full_name", "") if pis else rec.get("contact_pi_name", "")
        return {
            "pi_full_name": pi_name,
            "institution": rec.get("org_name", ""),
            "city": rec.get("org_city", ""),
            "country": rec.get("org_country", ""),
            "award_amount": rec.get("award_amount"),
            "project_num": rec.get("project_num", ""),
        }

    if record_type == "trials":
        investigators = rec.get("investigators", [])
        pi_name = investigators[0].get("name", "") if investigators else ""
        institution = investigators[0].get("affiliation", "") if investigators else rec.get("lead_sponsor", "")
        locations = rec.get("locations", [])
        city = locations[0].get("city", "") if locations else ""
        country = locations[0].get("country", "") if locations else ""
        return {
            "pi_full_name": pi_name,
            "institution": institution,
            "city": city,
            "country": country,
            "nct_id": rec.get("nct_id", ""),
        }

    return {}  # lab_pages: nothing pre-parsed, Claude extracts everything


def _text_for_record(rec: dict[str, Any]) -> str:
    record_type = rec.get("record_type")
    if record_type in ("papers", "grants"):
        return f"{rec.get('title', '')}\n\n{rec.get('abstract', '')}"
    if record_type == "trials":
        return f"{rec.get('title', '')}\n\n{rec.get('brief_summary', '')}"
    if record_type == "lab_pages":
        return f"{rec.get('title', '')}\n\n{rec.get('text', '')}"
    return ""


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def build_batch_prompt(batch: list[dict[str, Any]]) -> str:
    items_block = ""
    for c in batch:
        known = c["known_fields"]
        known_str = ", ".join(f"{k}={v}" for k, v in known.items() if v) or "(none pre-known)"
        items_block += f"\n\n--- ITEM {c['id']} ---\nKnown fields: {known_str}\nText:\n{c['text']}"

    return f"""You are extracting structured lab profile data for a cardiac regeneration research database.

{EXTRACTION_SCHEMA_INSTRUCTIONS}

Where "Known fields" are given for an item, use them for pi_full_name/institution/city/country
rather than re-deriving them, unless the text clearly contradicts them.

Respond with ONLY a JSON array, no other text, no markdown fences.
{items_block}"""


def extract_batch(client: anthropic.Anthropic, batch: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
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

            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            extracted = json.loads(raw_text)
            return {e["id"]: e for e in extracted if "id" in e}

        except (json.JSONDecodeError, anthropic.APIError) as e:
            print(f"    [warn] batch extraction attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(API_RETRY_DELAY)

    print(f"    [warn] giving up on batch after {MAX_RETRIES + 1} attempts — "
          f"{len(batch)} items will be flagged for manual review")
    return {c["id"]: {"id": c["id"], "_extraction_failed": True} for c in batch}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main():
    config.check_required_env_vars()
    config.ensure_run_dir()

    filtered_path = config.run_path("filtered")
    if not filtered_path.exists():
        print(f"{filtered_path.name} not found — run step 5 first.")
        return

    with open(filtered_path) as f:
        filtered_records = json.load(f)

    print(f"Preparing {len(filtered_records)} filtered records for extraction...")
    candidates = []
    for i, rec in enumerate(filtered_records):
        candidates.append({
            "id": f"item_{i}",
            "source_index": i,
            "known_fields": _known_fields_for_record(rec),
            "text": _text_for_record(rec)[:4000],
        })

    client = _client()
    all_extractions = {}
    num_batches = (len(candidates) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_num in range(num_batches):
        batch = candidates[batch_num * BATCH_SIZE: (batch_num + 1) * BATCH_SIZE]
        print(f"  Extracting batch {batch_num + 1}/{num_batches} ({len(batch)} items)...")
        all_extractions.update(extract_batch(client, batch))

    labs_extracted = []
    needs_review = []

    for c in candidates:
        extraction = all_extractions.get(c["id"])
        original = filtered_records[c["source_index"]]

        if extraction is None or extraction.get("_extraction_failed"):
            needs_review.append(original)
            continue

        labs_extracted.append({
            "pi_full_name": extraction.get("pi_full_name", ""),
            "pi_canonical_name": extraction.get("pi_full_name", ""),  # true canonicalization happens in step 7
            "orcid": "",
            "email": extraction.get("contact", ""),
            "institutional_profile_url": extraction.get("lab_url", ""),
            "department": extraction.get("department", ""),
            "institution": extraction.get("institution", ""),
            "city": extraction.get("city", ""),
            "country": extraction.get("country", ""),
            "geo_coordinates": None,  # TODO fast-follow: geocode city/country
            "research_focus": {
                "cell_gene_sources": extraction.get("cell_gene_sources", []),
                "constructs_bioengineering": extraction.get("constructs_bioengineering", []),
                "functional_vectors": extraction.get("functional_vectors", []),
            },
            "experimental_models": extraction.get("experimental_models", []),
            "translational_stage": extraction.get("translational_stage", ""),
            "digital_footprint": {
                "lab_url": extraction.get("lab_url", ""),
                "google_scholar": "",
                "latest_pub_doi": original.get("doi", ""),
                "contact": extraction.get("contact", ""),
            },
            "metrics": {
                "grant_funding_usd": original.get("award_amount"),
                "clinical_trial_ids": [original["nct_id"]] if original.get("nct_id") else [],
            },
            "source_record_type": original.get("record_type", ""),
            "source_reference": {
                "title": original.get("title", ""),
                "doi": original.get("doi", ""),
                "project_num": original.get("project_num", ""),
                "nct_id": original.get("nct_id", ""),
                "url": original.get("url", ""),
            },
        })

    out_path = config.run_path("labs_extracted")
    with open(out_path, "w") as f:
        json.dump(labs_extracted, f, indent=2)

    if needs_review:
        review_path = config.CURRENT_RUN_DIR / "extraction_needs_review.json"
        with open(review_path, "w") as f:
            json.dump(needs_review, f, indent=2)
        print(f"\n[!] {len(needs_review)} items failed extraction and were written to {review_path}")

    print(f"\nDone. Extracted {len(labs_extracted)} lab profile candidates to {out_path}")


if __name__ == "__main__":
    main()
