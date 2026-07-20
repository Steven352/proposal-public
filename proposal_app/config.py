from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
HISTORICAL_DIR = DATA_DIR / "historical_proposals"
ASSET_DIR = DATA_DIR / "assets"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
KNOWLEDGE_INDEX = KNOWLEDGE_DIR / "proposal_index.json"
RULES_PATH = KNOWLEDGE_DIR / "rules.md"

STANDARD_TERMS_PATH = ASSET_DIR / "standard_terms.pdf"
WORK_AUTHORIZATION_PATH = ASSET_DIR / "work_authorization.pdf"
STEVEN_SIGNATURE_PATH = ASSET_DIR / "signature_steven.png"
ABDUL_SIGNATURE_PATH = ASSET_DIR / "signature_abdul.png"

DEFAULT_EXTRACTION_MODEL = "gpt-5.6-luna"
DEFAULT_DRAFT_MODEL = "gpt-5.6-terra"

PREPARED_BY = "Steven Lai"
PREPARED_BY_TITLE = "Engineer In Training"
REVIEWED_BY = "Abdul Alemi, P.Eng."
REVIEWED_BY_TITLE = "Project Engineer"
ATS_CONTACT = "Abdul Alemi"

SECTION_ORDER = (
    "Preliminary Work / Meetings",
    "Field Program",
    "Laboratory Testing Program",
    "Engineering Analysis & Report Preparation",
)
