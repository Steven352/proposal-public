from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .models import ProposalFacts


DRAFT_SCHEMA = "almor-proposal-draft"
DRAFT_VERSION = 1


@dataclass(frozen=True)
class RestoredDraft:
    facts: ProposalFacts
    scope_rows: list[dict[str, Any]]
    cost_rows: list[dict[str, Any]]
    request_email: str
    notes: str
    include_proposed_project_personnel: bool


def _frame_rows(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if frame is None:
        return []
    return frame.fillna("").to_dict(orient="records")


def export_draft(
    *,
    facts: ProposalFacts,
    scope_frame: pd.DataFrame | None,
    cost_frame: pd.DataFrame | None,
    request_email: str = "",
    notes: str = "",
    include_proposed_project_personnel: bool = True,
) -> dict[str, Any]:
    """Create a portable, JSON-serializable snapshot of the editable workflow."""
    return {
        "schema": DRAFT_SCHEMA,
        "version": DRAFT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "facts": facts.model_dump(mode="json"),
        "scope_rows": _frame_rows(scope_frame),
        "cost_rows": _frame_rows(cost_frame),
        "request_email": request_email,
        "notes": notes,
        "include_proposed_project_personnel": bool(include_proposed_project_personnel),
    }


def import_draft(payload: dict[str, Any]) -> RestoredDraft:
    if not isinstance(payload, dict) or payload.get("schema") != DRAFT_SCHEMA:
        raise ValueError("This file is not an Almor proposal draft.")
    if payload.get("version") != DRAFT_VERSION:
        raise ValueError("This Almor proposal draft version is not supported.")
    facts_payload = payload.get("facts")
    if not isinstance(facts_payload, dict):
        raise ValueError("The draft does not contain proposal facts.")
    try:
        facts = ProposalFacts.model_validate(facts_payload)
    except Exception as exc:
        raise ValueError(f"The proposal facts in this draft are invalid: {exc}") from exc
    scope_rows = payload.get("scope_rows", [])
    cost_rows = payload.get("cost_rows", [])
    if not isinstance(scope_rows, list) or not isinstance(cost_rows, list):
        raise ValueError("The draft editor data is invalid.")
    return RestoredDraft(
        facts=facts,
        scope_rows=[row for row in scope_rows if isinstance(row, dict)],
        cost_rows=[row for row in cost_rows if isinstance(row, dict)],
        request_email=str(payload.get("request_email", "")),
        notes=str(payload.get("notes", "")),
        include_proposed_project_personnel=bool(payload.get("include_proposed_project_personnel", True)),
    )
