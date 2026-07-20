from __future__ import annotations

from .costs import normalize_cost_items
from .models import ProposalFacts


def validate_facts(facts: ProposalFacts) -> list[str]:
    missing: list[str] = []
    required_text = {
        "Proposal number": facts.proposal_number,
        "Client": facts.client_name,
        "Project name": facts.project_name,
        "Project location": facts.project_location,
        "Requested service/development description": facts.development_description,
    }
    missing.extend(label for label, value in required_text.items() if not value.strip())

    methods = {method.lower() for method in facts.investigation_methods}
    if "drilling" in methods:
        if not facts.borehole_program and (
            facts.borehole_quantity is None or facts.borehole_depth_m is None
        ):
            missing.append("Borehole quantity/depth program")
    if "test pits" in methods:
        if not facts.test_pit_program and (
            facts.test_pit_quantity is None or facts.test_pit_depth_m is None
        ):
            missing.append("Test-pit quantity/depth program")

    summary = normalize_cost_items(facts.cost_items)
    if not summary.items:
        missing.append("Cost table")
    missing.extend(summary.warnings)
    return missing
