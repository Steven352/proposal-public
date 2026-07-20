from __future__ import annotations

import re

from .costs import as_number, clean_text
from .models import CostLineItem, InvestigationDepthGroup


GROUP_SPLIT_RE = re.compile(r"[;,\n]+")
GROUP_RE = re.compile(
    r"^\s*(?P<quantity>\d+)\s*"
    r"(?P<method>(?:bore\s*-?\s*holes?|bh)|(?:test\s*-?\s*pits?|tp))?\s*"
    r"(?:to|at|@|x)\s*"
    r"(?P<depth>\d+(?:\.\d+)?)\s*"
    r"m(?:et(?:re|er)s?)?\s*$",
    re.IGNORECASE,
)


def parse_investigation_program(
    text: str,
    label: str,
) -> tuple[list[InvestigationDepthGroup], list[str]]:
    groups: list[InvestigationDepthGroup] = []
    errors: list[str] = []
    for raw in GROUP_SPLIT_RE.split(text.strip()):
        value = raw.strip()
        if not value:
            continue
        match = GROUP_RE.fullmatch(value)
        if not match:
            errors.append(
                f"Invalid {label} program entry: '{value}'. Use a format such as "
                f"'5 {label} to 5 m'."
            )
            continue
        supplied_method = (match.group("method") or "").lower().replace(" ", "")
        expects_test_pit = label.lower().startswith("test")
        is_test_pit = supplied_method.startswith("test") or supplied_method == "tp"
        if supplied_method and expects_test_pit != is_test_pit:
            errors.append(f"'{value}' was entered in the wrong investigation program field.")
            continue
        quantity = int(match.group("quantity"))
        depth = float(match.group("depth"))
        if quantity <= 0 or depth <= 0:
            errors.append(f"{label.title()} quantity and depth must both be greater than zero.")
            continue
        groups.append(
            InvestigationDepthGroup(
                quantity=quantity,
                termination_depth_m=depth,
            )
        )
    return groups, errors


def format_investigation_program(
    groups: list[InvestigationDepthGroup],
    noun: str,
) -> str:
    lines = []
    for group in groups:
        plural = noun if group.quantity == 1 else f"{noun}s"
        lines.append(f"{group.quantity} {plural} to {group.termination_depth_m:g} m")
    return "\n".join(lines)


def legacy_program(
    quantity: int | None,
    depth_m: float | None,
) -> list[InvestigationDepthGroup]:
    if quantity and depth_m:
        return [
            InvestigationDepthGroup(
                quantity=quantity,
                termination_depth_m=depth_m,
            )
        ]
    return []


def infer_methods_from_cost_items(items: list[CostLineItem]) -> set[str]:
    methods: set[str] = set()
    for item in items:
        estimate = as_number(item.estimate) or 0.0
        if estimate <= 0:
            continue
        name = clean_text(item.item).lower()
        if "drilling contractor" in name:
            methods.add("drilling")
        if "excavator contractor" in name:
            methods.add("test pits")
    return methods
