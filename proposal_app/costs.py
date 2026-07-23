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


def standard_cost_items() -> list[CostLineItem]:
    rows = [
        ("Preliminary Work / Meetings", "Intermediate Professional", "Procurement, utility locates, and background review", "hr", 0, 185.0),
        ("Field Program", "Excavator Contractor", "Excavating test pits", "LS", 0, 1000.0),
        ("Field Program", "Drilling Contractor", "Mobilization/demobilization and on-site drilling", "hr", 0, 325.0),
        ("Field Program", "Drilling Consumables", "PVC pipe, bentonite, etc.", "LS", 0, 150.0),
        ("Field Program", "Locate Contractor", "Secondary utility clearance", "hr", 0, 225.0),
        ("Field Program", "Engineering Field Personnel", "Logging and sampling", "hr", 0, 135.0),
        ("Field Program", "Field Personnel", "Groundwater level measurements", "hr", 0, 115.0),
        ("Field Program", "Field Equipment", "Support vehicle mileage", "Ea", 0, 200.0),
        ("Field Program", "Disbursements", "Field supplies, etc.", "LS", 0, 0.0),
        ("Laboratory Testing Program", "Moisture Content Tests", "ASTM D2216", "Ea", 0, 8.25),
        ("Laboratory Testing Program", "Atterberg Limits", "ASTM D4318", "Ea", 0, 225.0),
        ("Laboratory Testing Program", "Hydrometer Analysis", "ASTM D7928", "Ea", 0, 275.0),
        ("Laboratory Testing Program", "Organic Content Tests", "", "Ea", 0, 70.0),
        ("Laboratory Testing Program", "Sulphate Content Tests", "", "Ea", 0, 65.0),
        ("Laboratory Testing Program", "Standard Proctor", "ASTM D698", "Ea", 0, 265.0),
        ("Laboratory Testing Program", "Shelby Tubes", "Extrude", "Ea", 0, 65.0),
        ("Laboratory Testing Program", "pH", "G51", "Ea", 0, 20.0),
        ("Laboratory Testing Program", "Consolidation Test", "ASTM D2435", "Ea", 0, 1000.0),
        ("Laboratory Testing Program", "Unit Weight Determination", "", "Ea", 0, 65.0),
        ("Laboratory Testing Program", "Triaxial Permeability", "", "Ea", 0, 450.0),
        ("Laboratory Testing Program", "California Bearing Ratio Test", "CBR", "Ea", 0, 300.0),
        ("Laboratory Testing Program", "Unconfined Compressive Strength", "", "Ea", 0, 215.0),
        ("Laboratory Testing Program", "Direct Shear Test", "", "Ea", 0, 500.0),
        ("Engineering Analysis & Report Preparation", "Junior Professional", "", "hr", 0, 135.0),
        ("Engineering Analysis & Report Preparation", "Intermediate Professional", "", "hr", 0, 185.0),
        ("Engineering Analysis & Report Preparation", "Senior Professional", "", "hr", 0, 250.0),
    ]
    return [
        CostLineItem(
            section=section,
            item=item,
            description=description,
            unit=unit,
            estimate=estimate,
            rate=rate,
            total=round(estimate * rate, 2),
        )
        for section, item, description, unit, estimate, rate in rows
    ]


def merge_standard_cost_items(items: list[CostLineItem]) -> list[CostLineItem]:
    merged = standard_cost_items()
    positions = {clean_text(item.item).lower(): index for index, item in enumerate(merged)}
    for item in items:
        key = clean_text(item.item).lower()
        if key in positions:
            merged[positions[key]] = item
        else:
            merged.append(item)
    return merged


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
