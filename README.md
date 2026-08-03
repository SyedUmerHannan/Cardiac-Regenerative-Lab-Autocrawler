# Cardiac-Regenerative-Lab-Autocrawler

An end-to-end, multi-stage autonomous pipeline designed to discover, extract, deduplicate, score, and monitor global academic and translational research laboratories specializing in **cardiac regeneration, engineered heart tissue (EHT), direct reprogramming, stem cell therapy, and biological pacing**.

By orchestrating academic literature APIs, global grant repositories, clinical trial registries, dynamic web crawlers, and LLM structured extraction, `cardiac_lab_finder` generates an exhaustive, active database of global PIs and research groups, complete with annual diff tracking.

---

## 📐 Architecture & Pipeline Overview

The engine operates as a sequential modular pipeline with data stored and versioned by run year (`data/YYYY/`).

[ Ingestion Layer ] ──────────────► [ Intelligence & Resolution ] ──────► [ Scoring & Analytics ]
├── 1. Academic Papers (PubMed/PMC) ├── 5. Relevance Filtering (Claude)   ├── 8. Activity & Risk Scoring (AVI)
├── 2. Grant DBs (NIH/EU/UKRI)      ├── 6. Structured Field Extraction     └── 9. CSV Report & Annual Diffing
├── 3. Clinical Trials              └── 7. Entity Deduplication (ORCID/Email)
└── 4. Targeted Web Crawling
