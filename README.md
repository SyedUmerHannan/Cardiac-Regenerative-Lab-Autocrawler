# Cardiac-Regenerative-Lab-Autocrawler

An end-to-end, multi-stage autonomous pipeline designed by Virelion Biotech to discover, extract, deduplicate, score, and monitor global academic and translational research laboratories specializing in **cardiac regeneration, engineered heart tissue (EHT), direct reprogramming, stem cell therapy, and biological pacing**.

By orchestrating academic literature APIs, global grant repositories, clinical trial registries, dynamic web crawlers, and LLM structured extraction, `cardiac_lab_finder` generates an exhaustive, active database of global PIs and research groups, complete with annual diff tracking.

---

## 📐 Architecture & Pipeline Overview

The engine operates as a sequential modular pipeline with data stored and versioned by run year (`data/YYYY/`).

```mermaid
graph LR
    subgraph Ingestion["Ingestion Layer"]
        A1[1. Academic Papers - PubMed/PMC]
        A2[2. Grant DBs - NIH/EU/UKRI]
        A3[3. Clinical Trials]
        A4[4. Targeted Web Crawling]
    end

    subgraph Intelligence["Intelligence & Resolution"]
        B1[5. Relevance Filtering - Claude]
        B2[6. Structured Field Extraction]
        B3[7. Entity Deduplication - ORCID/Email]
    end

    subgraph Analytics["Scoring & Analytics"]
        C1[8. Activity & Risk Scoring - AVI]
        C2[9. CSV Report & Annual Diffing]
    end

    Ingestion --> Intelligence --> Analytics

---

## 📁 Repository Structure

```text
cardiac_lab_finder/
├── config.py                 # Core configuration: Search terms, API key orchestration, output paths
├── 1_harvest_papers.py       # Queries PubMed, Europe PMC, bioRxiv, and medRxiv → raw_papers.json
├── 2_harvest_grants.py       # Harvests NIH RePORT, Horizon Europe, UKRI grant data → raw_grants.json
├── 3_harvest_trials.py       # Mines ClinicalTrials.gov & EU CTR for active trials → raw_trials.json
├── 4_crawl_lab_pages.py      # Async crawler for university & society directories → raw_lab_pages.json
├── 5_classify_relevance.py   # LLM Classifier (Claude): Filters non-cardiac or non-regen noise → filtered.json
├── 6_extract_structured.py   # LLM Extractor (Claude): Converts raw data to structured schemas → labs_extracted.json
├── 7_resolve_entities.py     # Entity resolution & PI deduplication (ORCID/email/name) → labs_deduped.json
├── 8_score_and_enrich.py     # Computes Activity Verification Index (AVI) & funding totals → labs_final.json
├── 9_export_csv.py           # Exports final dataset to CSV + generates diff vs. previous year → labs_report.csv
├── requirements.txt          # Pinned dependency manifest
└── data/
    ├── 2026/                 # Current run artifacts (raw data, intermediate states, final outputs)
    └── 2025/                 # Prior run data (used for delta/diff calculations)
```

---

## ✨ Key Features

- Multi-Source Ingestion: Aggregates data from scientific publications, active grants, clinical trial registries, and institutional websites.

- LLM Domain Filtering: Uses Anthropic's Claude API to eliminate false positives (e.g., non-regenerative clinical cardiology or general non-cardiac stem cell research).

- Schema-Enforced Extraction: Normalizes unstructured web pages and paper abstracts into precise, structured records (PI name, institution, sub-disciplines, therapeutic modalities, model systems).

- Canonical Entity Resolution: Unifies author variations (e.g., J. Zhang, Jianyi Zhang) across multiple databases using ORCID IDs, affiliation matching, and institutional email domains.

- Activity Verification Index (AVI): Scores labs based on 24–36 month publication velocity, grant funding continuity, and clinical translation stage.

- Automated Year-over-Year Diffing: Compares output against previous annual runs (data/2025/ vs data/2026/) to highlight emerging PIs, newly funded labs, and institutional migrations.

---

## ⚙️ Core Extracted Schema

- Each identified lab profile contains the following structured fields:

- PI Identification: Full Name, Canonical Name, ORCID, Email, Institutional Profile URL.

- Affiliation: Primary Department, University/Institute, City, Country, Geographic Coordinates.

- Core Research Focus:

  - Cell & Gene Sources: hiPSC-CMs, primary CMs, direct lineage reprogramming, cardiac progenitors, mRNA therapies.

  - Constructs & Bioengineering: Engineered Heart Tissue (EHT), cardiac patches, decellularized matrices, 3D bioprinting.

  - Functional Vectors: Biological pacing, electromechanical coupling/arrhythmia mitigation, vascularization.

- Experimental Models: In vitro (EHT/Organ-on-a-chip), Small Animal (murine), Large Animal (porcine/NHP).

- Metrics: Active Grant Funding ($USD equivalent), Publication Recency Index, Clinical Trial Identifiers.

---

## 🚀 Quickstart Guide

1. Prerequisites
Ensure you have Python 3.10+ installed. Clone the repository and install dependencies:

Bash
git clone [https://github.com/your-username/cardiac_lab_finder.git](https://github.com/your-username/cardiac_lab_finder.git)
cd cardiac_lab_finder
pip install -r requirements.txt
2. Environment Setup
Create a .env file in the root directory or configure your system environment variables:

Bash
# Required API Keys
export ANTHROPIC_API_KEY="your-claude-api-key"
export NCBI_EMAIL="your-email@institution.edu" # Required for Entrez / PubMed API
export SEMANTIC_SCHOLAR_API_KEY="your-key-if-available"
3. Execution Pipeline
You can run individual modules sequentially or execute the full workflow via shell script:

Execute step-by-step:
Bash
# Ingestion
python 1_harvest_papers.py
python 2_harvest_grants.py
python 3_harvest_trials.py
python 4_crawl_lab_pages.py

# Processing & LLM Structuring
python 5_classify_relevance.py
python 6_extract_structured.py
python 7_resolve_entities.py

# Scoring & Report Generation
python 8_score_and_enrich.py
python 9_export_csv.py

---

## 📊 Output & Reporting

Upon completing a run, outputs are saved to the current year directory in data/:

- data/YYYY/labs_final.json: Comprehensive JSON knowledge base containing full lineage and extraction history.

- data/YYYY/labs_report.csv: Clean tabular output formatted for downstream analytical tools, spreadsheets, or GIS software.

- data/YYYY/annual_diff_summary.md: Auto-generated summary detailing:

  - 🆕 Newly Discovered Labs (labs appearing for the first time).

  - 📈 Funding Shifts (significant variations in grant totals).

  - ⚠️ Inactive Status (labs with no publication/grant activity over the past 36 months).
