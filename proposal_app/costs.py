from __future__ import annotations

import math
import re

from .config import SECTION_ORDER
from .models import CostLineItem, CostSummary


WORDING_REPLACEMENTS = {
    "Proffessional": "Professional",
    "milege": "mileage",
    "onsite": "on-site",
    "mob/demob": "Mobilization/demobilization",
    "Locates": "locates",
    "support vehicles milege": "support vehicle mileage",
    "ASTN": "ASTM",
    "Atterbergs": "Atterberg Limits",
    "Moistures": "Moisture Content Tests",
    "Sulphates": "Sulphate Content Tests",
    "Hydrometer": "Hydrometer Analysis",
    "Organic Content": "Organic Content Tests",
}


def as_number(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if cleaned in {"", "-", "."}:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
    if not math.isfinite(number):
        return None
    return number


def clean_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    for before, after in WORDING_REPLACEMENTS.items():
        text = text.replace(before, after)
    if text == "Background":
        return "background review"
    return text


def normalize_section(value: object) -> str:
    text = clean_text(value)
    lowered = text.lower()
    if "prelim" in lowered or "meeting" in lowered:
        return SECTION_ORDER[0]
    if "lab" in lowered:
        return SECTION_ORDER[2]
    if "engineering" in lowered or "report" in lowered or "analysis" in lowered:
        return SECTION_ORDER[3]
    return SECTION_ORDER[1]


def normalize_cost_items(items: list[CostLineItem | dict]) -> CostSummary:
    cleaned: list[CostLineItem] = []
    warnings: list[str] = []
    section_totals = {section: 0.0 for section in SECTION_ORDER}

    for raw in items:
        item = raw if isinstance(raw, CostLineItem) else CostLineItem.model_validate(raw)
        estimate = as_number(item.estimate)
        rate = as_number(item.rate)
        supplied_total = as_number(item.total)
        if estimate is None or abs(estimate) < 1e-9:
            continue

        calculated_total = estimate * rate if rate is not None else None
        if supplied_total is None and calculated_total is not None:
            total = calculated_total
        else:
            total = supplied_total
        if total is None:
            warnings.append(f"Missing total for cost item: {item.item or item.description}")
            total = 0.0
        if calculated_total is not None and abs(total - calculated_total) > 0.01:
            warnings.append(
                "Cost table total mismatch for "
                f"{item.item or item.description}: supplied ${total:,.2f}, "
                f"calculated ${calculated_total:,.2f}."
            )

        section = normalize_section(item.section)
        normalized = CostLineItem(
            section=section,
            item=clean_text(item.item),
            description=clean_text(item.description),
            unit=clean_text(item.unit),
            estimate=estimate,
            rate=rate,
            total=total,
        )
        cleaned.append(normalized)
        section_totals[section] += total

    return CostSummary(
        items=cleaned,
        section_totals={k: round(v, 2) for k, v in section_totals.items()},
        final_total=round(sum(item.total or 0.0 for item in cleaned), 2),
        warnings=warnings,
    )


def format_money(value: float | None) -> str:
    return "$-" if value is None else f"${value:,.2f}"

