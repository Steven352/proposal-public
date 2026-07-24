from __future__ import annotations

from .costs import normalize_cost_items
from .models import ProposalFacts


def validate_facts(facts: ProposalFacts) -> list[str]:
    summary = normalize_cost_items(facts.cost_items)
    return summary.warnings
