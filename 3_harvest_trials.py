"""
3_harvest_trials.py — Cardiac-Regenerative-Lab-Autocrawler
Virelion Biotech

Harvests trial records from ClinicalTrials.gov (API v2) matching the domain
search terms in config.py. EU Clinical Trials Register is stubbed — its API
(CTIS) has a different schema and auth model, left for a fast-follow pass
rather than rushed into v1.

Output: data/<year>/raw_trials.json
    A list of trial records, each tagged with its source and matched term.

Usage:
    python 3_harvest_trials.py
"""

import json
import time
from typing import Any

import requests

import config

CTGOV_DELAY = 0.3
CTGOV_PAGE_SIZE = 100  # ClinicalTrials.gov v2 API max pageSize


def ctgov_search(term: str, page_size: int = CTGOV_PAGE_SIZE) -> list[dict[str, Any]]:
    """
    Paginates through ClinicalTrials.gov v2 API results for a single search
    term. Uses the API's cursor-based pageToken pagination.
    """
    records = []
    page_token = None

    fields = ",".join([
        "NCTId", "BriefTitle", "OfficialTitle", "OverallStatus", "Phase",
        "Condition", "InterventionName", "InterventionType",
        "LeadSponsorName", "ResponsiblePartyInvestigatorFullName",
        "ResponsiblePartyInvestigatorAffiliation", "LocationFacility",
        "LocationCity", "LocationCountry", "StartDate", "CompletionDate",
        "BriefSummary",
    ])

    while True:
        params = {
            "query.term": term,
            "fields": fields,
            "pageSize": page_size,
            "format": "json",
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(config.CLINICALTRIALS_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        studies = data.get("studies", [])
        for study in studies:
            records.append(_parse_ctgov_study(study))

        page_token = data.get("nextPageToken")
        time.sleep(CTGOV_DELAY)

        if not page_token or not studies:
            break

    return records


def _parse_ctgov_study(study: dict) -> dict[str, Any]:
    protocol = study.get("protocolSection", {})

    ident = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    design_mod = protocol.get("designModule", {})
    conditions_mod = protocol.get("conditionsModule", {})
    interventions_mod = protocol.get("armsInterventionsModule", {})
    contacts_mod = protocol.get("contactsLocationsModule", {})
    description_mod = protocol.get("descriptionModule", {})

    locations = []
    for loc in contacts_mod.get("locations", []) or []:
        locations.append({
            "facility": loc.get("facility", ""),
            "city": loc.get("city", ""),
            "country": loc.get("country", ""),
        })

    investigators = []
    for official in contacts_mod.get("overallOfficials", []) or []:
        investigators.append({
            "name": official.get("name", ""),
            "affiliation": official.get("affiliation", ""),
            "role": official.get("role", ""),
        })

    interventions = [
        i.get("name", "") for i in interventions_mod.get("interventions", []) or []
    ]

    return {
        "source": "clinicaltrials_gov",
        "nct_id": ident.get("nctId", ""),
        "title": ident.get("briefTitle", ""),
        "official_title": ident.get("officialTitle", ""),
        "status": status_mod.get("overallStatus", ""),
        "phase": (design_mod.get("phases") or [""])[0],
        "conditions": conditions_mod.get("conditions", []),
        "interventions": interventions,
        "lead_sponsor": sponsor_mod.get("leadSponsor", {}).get("name", ""),
        "investigators": investigators,
        "locations": locations,
        "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
        "completion_date": status_mod.get("completionDateStruct", {}).get("date", ""),
        "brief_summary": description_mod.get("briefSummary", ""),
    }


# ---------------------------------------------------------------------------
# Stub for fast-follow: EU Clinical Trials Register / CTIS
# ---------------------------------------------------------------------------

def harvest_eu_ctr(term: str) -> list[dict[str, Any]]:
    """
    TODO (fast-follow): EU Clinical Trials Information System (CTIS) API.
    Different schema/auth from ClinicalTrials.gov v2 — deliberately not
    implemented in v1.
    """
    return []


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def harvest_term(term: str) -> list[dict[str, Any]]:
    results = []

    print(f"  ClinicalTrials.gov: searching '{term}'")
    try:
        ct_results = ctgov_search(term)
        results.extend(ct_results)
        print(f"    -> {len(ct_results)} trial records")
    except requests.RequestException as e:
        print(f"    [warn] ClinicalTrials.gov search failed for '{term}': {e}")

    results.extend(harvest_eu_ctr(term))  # currently a no-op

    return results


def main():
    config.ensure_run_dir()

    print(f"Harvesting trials for {len(config.ALL_SEARCH_TERMS)} search terms...")
    print("(EU CTR pending fast-follow implementation)\n")

    all_records = []
    for term in config.ALL_SEARCH_TERMS:
        print(f"[{term}]")
        term_records = harvest_term(term)
        for rec in term_records:
            rec["matched_term"] = term
        all_records.extend(term_records)

    out_path = config.run_path("raw_trials")
    with open(out_path, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"\nDone. Wrote {len(all_records)} raw trial records (pre-dedup) to {out_path}")


if __name__ == "__main__":
    main()
