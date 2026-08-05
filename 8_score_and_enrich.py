"""
8_score_and_enrich.py — Cardiac-Regenerative-Lab-Autocrawler
Virelion Biotech

Scores and enriches each deduplicated lab profile from step 7:

- Activity Verification Index (AVI): a recency-based status derived from the
  most recent dated source evidence (paper pub_year, grant fiscal_year, or
  trial start/completion year) attached to the lab during step 6/7.
  Categorizes each lab as Active / Aging / Inactive-Legacy / Unknown, using
  the windows defined in config.py (AVI_ACTIVE_WINDOW_MONTHS,
  AVI_INACTIVE_THRESHOLD_MONTHS).
- Funding totals: already summed in step 7 (grant_funding_usd) — carried
  through here unchanged.
- Electromechanical Risk Profile Tagging: flags labs whose research_focus
  includes electromechanical integration or arrhythmia mitigation vectors.

NOT computed in this step (left as explicit null/None with a note, rather
than faked): citation impact (would require Semantic Scholar citation counts,
not harvested in step 1) and industry/startup spinoff affiliation (no data
source for this in v1). Both are reasonable fast-follow additions.

Output: data/<year>/labs_final.json

Usage:
    python 8_score_and_enrich.py
"""

import json
from datetime import datetime
from typing import Any

import config

CURRENT_YEAR = datetime.now().year

RISK_TAG_VECTORS = {"electromechanical integration", "arrhythmia mitigation"}


# ---------------------------------------------------------------------------
# Activity Verification Index
# ---------------------------------------------------------------------------

def _most_recent_year(lab: dict[str, Any]) -> int | None:
    years = [
        ref.get("year") for ref in lab.get("source_references", [])
        if isinstance(ref.get("year"), int)
    ]
    return max(years) if years else None


def compute_avi(lab: dict[str, Any]) -> dict[str, Any]:
    most_recent_year = _most_recent_year(lab)

    if most_recent_year is None:
        return {
            "status": "Unknown",
            "most_recent_activity_year": None,
            "months_since_last_activity": None,
            "avi_score": None,
            "note": "No dated source evidence (e.g. lab only appears via crawled pages, which aren't dated).",
        }

    months_since = (CURRENT_YEAR - most_recent_year) * 12

    if months_since <= config.AVI_ACTIVE_WINDOW_MONTHS:
        status = "Active"
    elif months_since <= config.AVI_INACTIVE_THRESHOLD_MONTHS:
        status = "Aging"
    else:
        status = "Inactive/Legacy"

    # Simple linear score: 100 at zero months since activity, 0 at the
    # inactive threshold and beyond. A rough, comparative measure only —
    # not a precision instrument, given year-level date granularity.
    avi_score = max(0, round(100 - (months_since / config.AVI_INACTIVE_THRESHOLD_MONTHS) * 100))

    return {
        "status": status,
        "most_recent_activity_year": most_recent_year,
        "months_since_last_activity": months_since,
        "avi_score": avi_score,
        "note": "",
    }


# ---------------------------------------------------------------------------
# Risk tagging
# ---------------------------------------------------------------------------

def compute_risk_flags(lab: dict[str, Any]) -> dict[str, Any]:
    vectors = set(lab.get("research_focus", {}).get("functional_vectors", []))
    matched = sorted(vectors & RISK_TAG_VECTORS)
    return {
        "electromechanical_risk_profile": bool(matched),
        "matched_risk_vectors": matched,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main():
    config.ensure_run_dir()

    in_path = config.run_path("labs_deduped")
    if not in_path.exists():
        print(f"{in_path.name} not found — run step 7 first.")
        return

    with open(in_path) as f:
        labs = json.load(f)

    print(f"Scoring and enriching {len(labs)} deduplicated lab profiles...")

    final = []
    status_counts: dict[str, int] = {}

    for lab in labs:
        avi = compute_avi(lab)
        risk = compute_risk_flags(lab)
        status_counts[avi["status"]] = status_counts.get(avi["status"], 0) + 1

        enriched = {
            **lab,
            "activity_verification_index": avi,
            "risk_flags": risk,
            "translation_scale_metrics": {
                "grant_funding_usd": lab.get("metrics", {}).get("grant_funding_usd"),
                "citation_impact": None,  # TODO fast-follow: Semantic Scholar citation counts
                "industry_spinoff_affiliation": None,  # TODO fast-follow: no data source in v1
            },
        }
        final.append(enriched)

    # Sort by AVI score (most active first), unscored labs last
    final.sort(key=lambda lab: (lab["activity_verification_index"]["avi_score"] is None,
                                 -(lab["activity_verification_index"]["avi_score"] or 0)))

    out_path = config.run_path("labs_final")
    with open(out_path, "w") as f:
        json.dump(final, f, indent=2)

    print("  Activity status breakdown:")
    for status, count in sorted(status_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {status}: {count}")

    risk_count = sum(1 for lab in final if lab["risk_flags"]["electromechanical_risk_profile"])
    print(f"  {risk_count} labs flagged with an electromechanical risk profile")

    print(f"\nDone. Wrote {len(final)} scored/enriched lab profiles to {out_path}")


if __name__ == "__main__":
    main()
