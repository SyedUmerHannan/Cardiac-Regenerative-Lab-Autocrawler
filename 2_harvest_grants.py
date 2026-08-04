"""
2_harvest_grants.py — Cardiac-Regenerative-Lab-Autocrawler
Virelion Biotech

Harvests active/recent grant data from NIH RePORTER matching the domain
search terms in config.py. Horizon Europe and UKRI are stubbed (see
harvest_horizon_europe / harvest_ukri below) — their APIs have different
schemas and pagination models, and are intentionally left for a fast-follow
pass rather than rushed into v1.

Output: data/<year>/raw_grants.json
    A list of grant records, each tagged with its source and matched term.

Usage:
    python 2_harvest_grants.py
"""

import json
import time
from datetime import datetime
from typing import Any

import requests

import config

REPORTER_DELAY = 0.5  # polite delay between paginated requests
REPORTER_PAGE_SIZE = 500  # NIH RePORTER's max limit per request
REPORTER_LOOKBACK_YEARS = 5  # how many recent fiscal years to search


def _recent_fiscal_years(n: int = REPORTER_LOOKBACK_YEARS) -> list[int]:
    current_year = datetime.now().year
    return list(range(current_year - n + 1, current_year + 1))


def nih_reporter_search(term: str, page_size: int = REPORTER_PAGE_SIZE) -> list[dict[str, Any]]:
    """
    Paginates through NIH RePORTER results for a single search term across
    recent fiscal years. Returns parsed grant records.
    """
    records = []
    offset = 0
    fiscal_years = _recent_fiscal_years()

    while True:
        body = {
            "criteria": {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": "projecttitle,abstracttext,terms",
                    "search_text": term,
                },
                "fiscal_years": fiscal_years,
            },
            "include_fields": [
                "ProjectNum", "ProjectTitle", "AbstractText", "FiscalYear",
                "AwardAmount", "OrgName", "OrgCity", "OrgState", "OrgCountry",
                "ContactPiName", "PrincipalInvestigators", "ProjectStartDate",
                "ProjectEndDate", "AgencyIcAdmin",
            ],
            "offset": offset,
            "limit": page_size,
        }

        resp = requests.post(config.NIH_REPORTER_BASE, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        for item in results:
            records.append(_parse_reporter_item(item))

        total = data.get("meta", {}).get("total", 0)
        offset += page_size
        time.sleep(REPORTER_DELAY)

        if offset >= total or not results:
            break

    return records


def _parse_reporter_item(item: dict) -> dict[str, Any]:
    pis = []
    for pi in item.get("principal_investigators", []) or []:
        pis.append({
            "full_name": pi.get("full_name", ""),
            "first_name": pi.get("first_name", ""),
            "last_name": pi.get("last_name", ""),
        })

    return {
        "source": "nih_reporter",
        "project_num": item.get("project_num", ""),
        "title": item.get("project_title", ""),
        "abstract": item.get("abstract_text", ""),
        "fiscal_year": item.get("fiscal_year", ""),
        "award_amount": item.get("award_amount", None),
        "org_name": item.get("org_name", ""),
        "org_city": item.get("org_city", ""),
        "org_state": item.get("org_state", ""),
        "org_country": item.get("org_country", ""),
        "contact_pi_name": item.get("contact_pi_name", ""),
        "principal_investigators": pis,
        "project_start_date": item.get("project_start_date", ""),
        "project_end_date": item.get("project_end_date", ""),
        "funding_agency": item.get("agency_ic_admin", {}).get("name", "") if item.get("agency_ic_admin") else "",
    }


# ---------------------------------------------------------------------------
# Stubs for fast-follow: Horizon Europe & UKRI
# ---------------------------------------------------------------------------

def harvest_horizon_europe(term: str) -> list[dict[str, Any]]:
    """
    TODO (fast-follow): Horizon Europe grant data via the EU Funding &
    Tenders Portal API. Different auth model and response schema from NIH
    RePORTER — deliberately not implemented in v1. See config.GRANT_SOURCES_PENDING.
    """
    return []


def harvest_ukri(term: str) -> list[dict[str, Any]]:
    """
    TODO (fast-follow): UKRI Gateway to Research API
    (https://gtr.ukri.org/resources/api.html). Deliberately not implemented
    in v1. See config.GRANT_SOURCES_PENDING.
    """
    return []


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def harvest_term(term: str) -> list[dict[str, Any]]:
    results = []

    print(f"  NIH RePORTER: searching '{term}'")
    try:
        nih_results = nih_reporter_search(term)
        results.extend(nih_results)
        print(f"    -> {len(nih_results)} NIH grant records")
    except requests.RequestException as e:
        print(f"    [warn] NIH RePORTER search failed for '{term}': {e}")

    # Stubs — currently no-ops, kept in the loop so wiring them up later is a one-line change
    results.extend(harvest_horizon_europe(term))
    results.extend(harvest_ukri(term))

    return results


def main():
    config.ensure_run_dir()

    print(f"Harvesting grants for {len(config.ALL_SEARCH_TERMS)} search terms...")
    print(f"(Sources pending fast-follow implementation: {', '.join(config.GRANT_SOURCES_PENDING)})\n")

    all_records = []
    for term in config.ALL_SEARCH_TERMS:
        print(f"[{term}]")
        term_records = harvest_term(term)
        for rec in term_records:
            rec["matched_term"] = term
        all_records.extend(term_records)

    out_path = config.run_path("raw_grants")
    with open(out_path, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"\nDone. Wrote {len(all_records)} raw grant records (pre-dedup) to {out_path}")


if __name__ == "__main__":
    main()
