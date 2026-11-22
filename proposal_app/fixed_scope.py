"""Approved scope copy. Only investigation facts and method-specific terms vary."""
from .investigation import legacy_program
from .models import ParagraphBlock, ProposalFacts

LABORATORY_SCOPE = (
    "Collection of suitable disturbed soil samples for laboratory testing, including relatively undisturbed Shelby tube soil samples at the discretion of Almor, where possible. Laboratory testing on selected "
    "samples to assist with the determination of engineering properties. The actual tests conducted "
    "will be a function of the soil conditions encountered."
)
STANDPIPE_SCOPE = (
    "Installation of 25 mm diameter standpipe piezometers in all boreholes, backfilled with "
    "cuttings and capped with bentonite. Groundwater readings will be taken at the end of "
    "drilling and during one follow-up visit two weeks after the field program."
)
BOREHOLE_GPS_SCOPE = (
    "Each of the completed boreholes shall be surveyed in the field using a medium precision handheld "
    "GPS (+/- 10 m) to obtain UTM northing, eastings and approximate elevations. If precision "
    "surveying is required, this work will be provided by others and is outside the scope of our proposal."
)
REPORT_SCOPE = (
    "Preparation of a geotechnical report describing the work performed, presenting the findings, and "
    "providing geotechnical recommendations to support the proposed development."
)
BOREHOLE_SCOPE_CLOSING = (
    " All work will be overseen by qualified and experienced Almor field staff who will log the soil "
    "and groundwater conditions encountered during the drilling program and collect suitable soil "
    "samples. Following the field work, the samples will be returned to our office for review, and "
    "submission to Almor’s laboratory for standard index testing. Almor understands the importance of "
    "environmental stewardship at the site locations and shall minimize the impact from drilling. We "
    "have assumed that all drill cuttings can be returned to the boreholes or scattered around the "
    "boreholes at surface."
)

BACKGROUND_SCOPE = "A review of available background geological and geotechnical information."
UTILITY_SCOPE = "Coordinate utility locates and secondary utility clearance before drilling."
LOGGING_SCOPE = (
    "Detailed logging of the soil stratigraphy, bedrock conditions and groundwater conditions "
    "encountered during drilling activities, based on logging procedures in accordance with the "
    "Modified Unified Soil Classification System (MUSCS) found in the Canadian Foundation "
    "Engineering Manual (CFEM) and applicable ASTM standards."
)
IN_SITU_SCOPE = (
    "Perform in-situ soil consistency tests (i.e. SPT) at 1.5m intervals, if soil conditions are "
    "favourable. Pocket penetrometer tests will be conducted in the field where possible."
)


def number_words(number: int) -> str:
    small = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
             "fourteen fifteen sixteen seventeen eighteen nineteen").split()
    tens = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
    if number < 20:
        return small[number]
    if number < 100:
        return tens[number // 10] + ("-" + small[number % 10] if number % 10 else "")
    for scale, name in ((1000000, "million"), (1000, "thousand"), (100, "hundred")):
        if number >= scale:
            return number_words(number // scale) + " " + name + (
                " " + number_words(number % scale) if number % scale else ""
            )
    raise ValueError("Invalid investigation quantity")


def quantity_depth_phrase(groups, quantity, depth, noun: str) -> str:
    pairs = [(g.quantity, g.termination_depth_m) for g in groups] or [(quantity, depth)]
    parts = []
    for count, metres in pairs:
        count_text = f"{number_words(count)} ({count})" if count else "[quantity]"
        depth_text = str(float(metres)) if metres else "[depth]"
        label = noun if count == 1 else noun + "s"
        parts.append(f"{count_text} {label} to a minimum depth of {depth_text} metres")
    return " and ".join(parts)


def approved_scope_blocks(facts: ProposalFacts) -> list[ParagraphBlock]:
    boreholes = facts.borehole_program or legacy_program(facts.borehole_quantity, facts.borehole_depth_m)
    pits = facts.test_pit_program or legacy_program(facts.test_pit_quantity, facts.test_pit_depth_m)
    methods = {method.strip().lower() for method in facts.investigation_methods}
    has_pits = bool(pits or facts.test_pit_quantity or "test pits" in methods)
    has_boreholes = bool(boreholes or facts.borehole_quantity or "drilling" in methods or not has_pits)
    actions = []
    if has_boreholes:
        actions.append("drilling/sampling of " + quantity_depth_phrase(
            boreholes, facts.borehole_quantity, facts.borehole_depth_m, "borehole"))
    if has_pits:
        actions.append("excavation/sampling of " + quantity_depth_phrase(
            pits, facts.test_pit_quantity, facts.test_pit_depth_m, "test pit"))
    location_label = "Borehole and test-pit" if has_boreholes and has_pits else ("Borehole" if has_boreholes else "Test-pit")
    investigation = (
        "Field examination of the proposed building site area and " + " and ".join(actions)
        + " below existing grade, refusal, or depths sufficient to establish subsurface conditions, "
        "whichever is least. " + location_label
        + " locations will be determined based on access and utility considerations."
    )
    activity = "drilling and test pitting" if has_boreholes and has_pits else ("drilling" if has_boreholes else "test pitting")
    laboratory = LABORATORY_SCOPE
    closing = BOREHOLE_SCOPE_CLOSING.replace("drilling program", activity + " program")
    gps = BOREHOLE_GPS_SCOPE
    if has_pits:
        gps = gps.replace("boreholes", "boreholes and test pits" if has_boreholes else "test pits")
    if not has_boreholes:
        laboratory = laboratory.replace(
            ", including relatively undisturbed Shelby tube soil samples at the discretion of Almor, where possible", "")
        closing = closing.replace("drilling", "test pitting").replace("drill cuttings", "excavated material").replace("boreholes", "test pits")
    elif has_pits:
        closing = closing.replace("impact from drilling", "impact from drilling and test pitting")
        closing = closing.replace("drill cuttings", "drill cuttings and excavated material").replace("boreholes", "boreholes or test pits")
    bullets = [
        BACKGROUND_SCOPE, UTILITY_SCOPE.replace("drilling", activity), investigation,
        LOGGING_SCOPE.replace("drilling activities", activity + " activities"),
        IN_SITU_SCOPE if has_boreholes else "Pocket penetrometer tests will be conducted in the field where possible.",
        laboratory,
    ]
    if has_boreholes:
        bullets.append(STANDPIPE_SCOPE)
    bullets.extend([gps, REPORT_SCOPE])
    return [ParagraphBlock(text=text, style="list") for text in bullets] + [ParagraphBlock(text=closing, style="body")]
