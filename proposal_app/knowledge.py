from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import HISTORICAL_DIR, KNOWLEDGE_INDEX, LIBRARY_INDEX_ADDITIONS
from .models import ProposalFacts, ReferenceMatch


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if len(token) > 2}


@lru_cache(maxsize=4)
def load_index(
    path: Path = KNOWLEDGE_INDEX,
    additions_path: Path = LIBRARY_INDEX_ADDITIONS,
) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Proposal knowledge index not found at {path}. Run scripts/build_knowledge.py."
        )
    base = json.loads(path.read_text(encoding="utf-8"))["proposals"]
    additions: list[dict] = []
    if additions_path.exists():
        additions = json.loads(additions_path.read_text(encoding="utf-8")).get("proposals", [])

    merged: dict[str, dict] = {}
    for proposal in [*base, *additions]:
        key = proposal.get("proposal_number") or proposal["filename"]
        merged[key.upper()] = proposal
    return list(merged.values())


def build_query(facts: ProposalFacts) -> str:
    fields = [
        facts.project_name,
        facts.project_location,
        facts.development_description,
        facts.project_type,
        " ".join(facts.requested_services),
        " ".join(facts.investigation_methods),
        " ".join(facts.laboratory_tests),
        " ".join(facts.reporting_requirements),
        facts.other_notes,
    ]
    return " ".join(field for field in fields if field)


def retrieve_references(facts: ProposalFacts, limit: int = 5) -> list[ReferenceMatch]:
    query_tokens = tokenize(build_query(facts))
    query_methods = {method.lower() for method in facts.investigation_methods}
    project_type = facts.project_type.lower().strip()
    matches: list[ReferenceMatch] = []

    for proposal in load_index():
        corpus_tokens = set(proposal.get("tokens", []))
        overlap = len(query_tokens & corpus_tokens)
        union = max(1, len(query_tokens | corpus_tokens))
        score = 12.0 * overlap / union

        candidate_type = proposal.get("project_type", "").lower()
        if project_type and candidate_type:
            if project_type == candidate_type:
                score += 8.0
            elif tokenize(project_type) & tokenize(candidate_type):
                score += 3.0

        methods = {method.lower() for method in proposal.get("methods", [])}
        score += 2.5 * len(query_methods & methods)
        if proposal.get("proposal_number", "").startswith("P026-1"):
            score += 0.5
        if proposal.get("has_cost_table"):
            score += 0.25

        matches.append(
            ReferenceMatch(
                filename=proposal["filename"],
                project_type=proposal.get("project_type", "general"),
                methods=proposal.get("methods", []),
                score=round(score, 4),
                has_cost_table=bool(proposal.get("has_cost_table")),
                sections=proposal.get("sections", {}),
            )
        )

    return sorted(matches, key=lambda match: match.score, reverse=True)[:limit]


def choose_template(matches: list[ReferenceMatch]) -> Path:
    for match in matches:
        candidate = HISTORICAL_DIR / match.filename
        if match.has_cost_table and candidate.exists():
            return candidate
    raise FileNotFoundError("No compatible geotechnical proposal template was found.")


def reference_context(matches: list[ReferenceMatch], max_chars: int = 30_000) -> str:
    parts: list[str] = []
    used = 0
    for index, match in enumerate(matches[:3], start=1):
        sections = "\n\n".join(
            f"### {heading}\n{text}"
            for heading, text in match.sections.items()
            if text.strip()
        )
        block = (
            f"## Reference {index}: {match.filename}\n"
            f"Project type: {match.project_type}\n"
            f"Methods: {', '.join(match.methods)}\n\n{sections}"
        )
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)
