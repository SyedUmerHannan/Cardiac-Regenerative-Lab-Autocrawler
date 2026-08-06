"""
config.py — Cardiac-Regenerative-Lab-Autocrawler
Virelion Biotech

Core configuration: API keys, search terms, output paths, and shared constants.
All other scripts import from this file. Nothing here executes network calls.
"""

import os
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

CURRENT_YEAR = str(datetime.now().year)
CURRENT_RUN_DIR = DATA_DIR / CURRENT_YEAR


def get_previous_run_dir() -> Path | None:
    """
    Finds the most recent prior year's data directory (for diffing), if one exists.
    Does not assume a fixed prior year — looks at whatever folders are actually on disk.
    """
    if not DATA_DIR.exists():
        return None
    year_dirs = sorted(
        (p for p in DATA_DIR.iterdir() if p.is_dir() and p.name.isdigit() and p.name != CURRENT_YEAR),
        key=lambda p: int(p.name),
        reverse=True,
    )
    return year_dirs[0] if year_dirs else None


def ensure_run_dir() -> Path:
    """Creates this year's data directory if it doesn't exist yet."""
    CURRENT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    return CURRENT_RUN_DIR


# Standard filenames used across the pipeline (kept in one place to avoid typos/drift)
FILES = {
    "raw_papers": "raw_papers.json",
    "raw_grants": "raw_grants.json",
    "raw_trials": "raw_trials.json",
    "raw_lab_pages": "raw_lab_pages.json",
    "raw_patents": "raw_patents.json",
    "funding_leaderboard_csv": "funding_leaderboard.csv",
    "funding_leaderboard_institutions_csv": "funding_leaderboard_institutions.csv",
    "trial_dashboard_html": "trial_dashboard.html",
    "filtered": "filtered.json",
    "labs_extracted": "labs_extracted.json",
    "labs_deduped": "labs_deduped.json",
    "labs_final": "labs_final.json",
    "labs_report_csv": "labs_report.csv",
    "annual_diff_summary": "annual_diff_summary.md",
}


def run_path(key: str) -> Path:
    """Shortcut for CURRENT_RUN_DIR / FILES[key]."""
    return CURRENT_RUN_DIR / FILES[key]


# ---------------------------------------------------------------------------
# API keys & credentials (read from environment — never hardcode secrets)
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")  # required by NCBI Entrez usage policy
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")  # optional, raises Entrez rate limit
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")  # optional

REQUIRED_ENV_VARS = ["ANTHROPIC_API_KEY", "NCBI_EMAIL"]


def check_required_env_vars():
    """Call at the start of any script that needs these. Fails loudly and early."""
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Set them before running this script."
        )


# ---------------------------------------------------------------------------
# Claude / Anthropic API settings
# ---------------------------------------------------------------------------

CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 4096

# ---------------------------------------------------------------------------
# Source API endpoints
# ---------------------------------------------------------------------------

PUBMED_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
BIORXIV_API_BASE = "https://api.biorxiv.org/details"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"

NIH_REPORTER_BASE = "https://api.reporter.nih.gov/v2/projects/search"

CLINICALTRIALS_BASE = "https://clinicaltrials.gov/api/v2/studies"

# USPTO PatentsView API v1. Requires a free API key (register at
# https://patentsview.org/apis/keyrequest) sent as an X-Api-Key header.
# US-only coverage — Lens.org would give global coverage but requires a paid
# subscription, so PatentsView is the v1 default. Revisit if international
# patent coverage becomes a priority.
USPTO_PATENTSVIEW_BASE = "https://search.patentsview.org/api/v1/patent/"
USPTO_PATENTSVIEW_API_KEY = os.environ.get("USPTO_PATENTSVIEW_API_KEY", "")

# Grant sources beyond NIH RePORTER (Horizon Europe, UKRI) are NOT yet wired up
# in v1 — NIH RePORTER has the cleanest public API and is built first.
# These are placeholders for a fast-follow pass.
GRANT_SOURCES_PENDING = ["horizon_europe", "ukri"]

# ---------------------------------------------------------------------------
# Domain search terms
# ---------------------------------------------------------------------------

CELL_SOURCE_TERMS = [
    "hiPSC-CM",
    "induced pluripotent stem cell cardiomyocyte",
    "embryonic stem cell cardiomyocyte",
    "direct cardiac reprogramming",
    "cardiac progenitor cell",
]

CONSTRUCT_TERMS = [
    "engineered heart tissue",
    "cardiac patch",
    "3D bioprinting myocardium",
    "decellularized cardiac matrix",
]

ELECTROPHYSIOLOGY_TERMS = [
    "biological pacemaker",
    "electromechanical integration cardiac graft",
    "arrhythmogenesis cardiac graft transplantation",
]

ALL_SEARCH_TERMS = CELL_SOURCE_TERMS + CONSTRUCT_TERMS + ELECTROPHYSIOLOGY_TERMS

# Terms used to explicitly exclude noise during classification (step 5)
EXCLUSION_HINTS = [
    "interventional cardiology stenting",
    "general electrophysiology ablation (non-regenerative)",
    "general stem cell biology unrelated to cardiac application",
]

# ---------------------------------------------------------------------------
# Crawling settings (step 4)
# ---------------------------------------------------------------------------

CRAWL_USER_AGENT = "VirelionBiotech-CardiacLabResearchBot/1.0 (+contact: research@virelion.example)"
CRAWL_REQUEST_DELAY_SECONDS = 2.0  # polite delay between requests to the same domain
CRAWL_MAX_PAGES_PER_DOMAIN = 25
CRAWL_TIMEOUT_SECONDS = 15
CRAWL_RESPECT_ROBOTS_TXT = True

# Seed list of institutional/society directories to crawl from.
# Kept intentionally small and public-facing in v1 — gated membership directories
# (e.g. society member-only pages) are excluded pending a ToS review per source.
CRAWL_SEED_DIRECTORIES = [
    # Example format — populate with real, public, non-gated directory URLs:
    # "https://example.edu/cardiology/faculty",
]

# ---------------------------------------------------------------------------
# Activity Verification Index (AVI) settings (step 8)
# ---------------------------------------------------------------------------

AVI_ACTIVE_WINDOW_MONTHS = 30  # midpoint of the 24-36mo spec range
AVI_INACTIVE_THRESHOLD_MONTHS = 36
