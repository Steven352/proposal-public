"""Approved Geotechnical Field Program copy.

Only the field examination bullet (quantities, depths and method) changes between
proposals. Borehole, test-pit and mixed programs each use their own fixed wording.
"""
from .investigation import legacy_program
from .models import ParagraphBlock, ProposalFacts

FIELD_PROGRAM_INTRO = (
    "Based on information supplied by the Client, Almor provides the following estimated cost to "
    "perform the geotechnical assessment, and any additional work directed by the Client will "
    "constitute a change in the scope of work. The geotechnical field program could be initiated "
    "within two weeks subject to rig availability and locates, subsequent to authorization. The "
    "estimated costs do not include environmental considerations of the development. The field "
    "program will include geotechnical boreholes advanced using a track mounted solid stem auger "
    "drilling rig. It is our understanding access and clearing, if required, to the boreholes is "
    "suitable for a track mounted drilling rig and will be provided by the client as this work is "
    "outside the scope of our proposal. The proposed scope of work for this project includes:"
)
FIELD_PROGRAM_INTRO_TEST_PITS = (
    "Based on information supplied by the Client, Almor provides the following estimated cost to "
    "perform the geotechnical assessment, and any additional work directed by the Client will "
    "constitute a change in the scope of work. The geotechnical field program could be initiated "
    "within two weeks subject to equipment availability and locates, subsequent to authorization. "
    "The estimated costs do not include environmental considerations of the development. The field "
    "program will include geotechnical test pits advanced using a suitable excavator. It is our "
    "understanding access and clearing, if required, to the test pits is suitable for an excavator "
    "and will be provided by the client as this work is outside the scope of our proposal. The "
    "proposed scope of work for this project includes:"
)
FIELD_PROGRAM_INTRO_MIXED = (
    "Based on information supplied by the Client, Almor provides the following estimated cost to "
    "perform the geotechnical assessment, and any additional work directed by the Client will "
    "constitute a change in the scope of work. The geotechnical field program could be initiated "
    "within two weeks subject to rig and equipment availability and locates, subsequent to "
    "authorization. The estimated costs do not include environmental considerations of the "
    "development. The field program will include geotechnical boreholes advanced using a track "
    "mounted solid stem auger drilling rig and geotechnical test pits advanced using a suitable "
    "excavator. It is our understanding access and clearing, if required, to the boreholes and test "
    "pits is suitable for a track mounted drilling rig and an excavator and will be provided by the "
    "client as this work is outside the scope of our proposal. The proposed scope of work for this "
    "project includes:"
)

BACKGROUND_SCOPE = "A review of available background geological and geotechnical information."
UTILITY_SCOPE = "Coordinate utility locates and secondary utility clearance before drilling."
UTILITY_SCOPE_TEST_PITS = "Coordinate utility locates and secondary utility clearance before test pit excavation."
UTILITY_SCOPE_MIXED = (
    "Coordinate utility locates and secondary utility clearance before drilling and test pit excavation."
)
LOGGING_SCOPE = (
    "Detailed logging of the soil stratigraphy, bedrock conditions, and groundwater conditions "
    "encountered during drilling, based on logging procedures in accordance with the Modified "
    "Unified Soil Classification System (MUSCS) found in the Canadian Foundation Engineering "
    "Manual (CFEM) and applicable ASTM standards."
)
LOGGING_SCOPE_TEST_PITS = LOGGING_SCOPE.replace("during drilling,", "during test pit excavation,")
LOGGING_SCOPE_MIXED = LOGGING_SCOPE.replace("during drilling,", "during drilling and test pit excavation,")
SPT_SCOPE = (
    "Standard Penetration Testing (SPT) at 1.5 m intervals where soil conditions permit. Pocket "
    "penetrometer tests will be conducted in the field where possible."
)
SPT_SCOPE_MIXED = SPT_SCOPE.replace("at 1.5 m intervals where", "at 1.5 m intervals in the boreholes where")
POCKET_PENETROMETER_SCOPE = "Pocket penetrometer tests will be conducted in the field where possible."
LABORATORY_SCOPE = (
    "Collection of suitable disturbed soil samples for laboratory testing, including relatively "
    "undisturbed Shelby tube soil samples at the discretion of Almor, where possible. Laboratory "
    "testing on selected samples to assist with the determination of engineering properties. The "
    "actual tests conducted will be a function of the soil conditions encountered."
)
# Shelby tubes are taken from boreholes only.
LABORATORY_SCOPE_TEST_PITS = LABORATORY_SCOPE.replace(
    ", including relatively undisturbed Shelby tube soil samples at the discretion of Almor, where possible", "")
STANDPIPE_SCOPE = (
    "Installation of 25 mm diameter standpipe piezometers in all boreholes, backfilled with "
    "cuttings and capped with bentonite. Groundwater readings will be taken at the end of "
    "drilling and during one follow-up visit two weeks after the field program."
)
TEST_PIT_GROUNDWATER_SCOPE = (
    "Groundwater conditions, if encountered, will be observed and documented at the time of test "
    "pit excavation."
)
BOREHOLE_GPS_SCOPE = (
    "Each of the completed boreholes shall be surveyed in the field using a medium precision handheld "
    "GPS (+/- 10 m) to obtain UTM northing, eastings and approximate elevations. If precision "
    "surveying is required, this work will be provided by others and is outside the scope of our proposal."
)
TEST_PIT_GPS_SCOPE = BOREHOLE_GPS_SCOPE.replace("completed boreholes", "completed test pits")
MIXED_GPS_SCOPE = BOREHOLE_GPS_SCOPE.replace("completed boreholes", "completed boreholes and test pits")
REPORT_SCOPE = (
    "Preparation of a geotechnical report describing the work performed, presenting the findings, and "
    "providing geotechnical recommendations to support the proposed development."
)
BOREHOLE_SCOPE_CLOSING = (
    "All work will be overseen by qualified and experienced Almor field staff who will log the soil "
    "and groundwater conditions encountered during the drilling program and collect suitable soil "
    "samples. Following the field work, the samples will be returned to our office for review, and "
    "submission to Almor’s laboratory for standard index testing. Almor understands the importance of "
    "environmental stewardship at the site locations and shall minimize the impact from drilling. We "
    "have assumed that all drill cuttings can be returned to the boreholes or scattered around the "
    "boreholes at surface."
)
TEST_PIT_SCOPE_CLOSING = (
    "All work will be overseen by qualified and experienced Almor field staff who will log the soil "
    "and groundwater conditions encountered during the test pit program and collect suitable soil "
    "samples. Following the field work, the samples will be returned to our office for review, and "
    "submission to Almor’s laboratory for standard index testing. Almor understands the importance of "
    "environmental stewardship at the site locations and shall minimize the impact from excavation. "
    "We have assumed that all excavated soils can be returned to the test pits or scattered around "
    "the test pits at surface."
)
MIXED_SCOPE_CLOSING = (
    "All work will be overseen by qualified and experienced Almor field staff who will log the soil "
    "and groundwater conditions encountered during the drilling and test pit programs and collect "
    "suitable soil samples. Following the field work, the samples will be returned to our office for "
    "review, and submission to Almor’s laboratory for standard index testing. Almor understands the "
    "importance of environmental stewardship at the site locations and shall minimize the impact from "
    "drilling and excavation. We have assumed that all drill cuttings and excavated soils can be "
    "returned to the boreholes and test pits or scattered around them at surface."
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
        depth_text = f"{float(metres):.1f} m" if metres else "[depth] m"
        label = noun if count == 1 else noun + "s"
        parts.append(f"{count_text} {label} to a minimum depth of {depth_text}")
    return " and ".join(parts)


def investigation_methods(facts: ProposalFacts) -> tuple[bool, bool]:
    """Return (has_boreholes, has_test_pits); boreholes are the default."""
    boreholes = facts.borehole_program or legacy_program(facts.borehole_quantity, facts.borehole_depth_m)
    pits = facts.test_pit_program or legacy_program(facts.test_pit_quantity, facts.test_pit_depth_m)
    methods = {method.strip().lower() for method in facts.investigation_methods}
    has_pits = bool(pits or facts.test_pit_quantity or "test pits" in methods)
    has_boreholes = bool(boreholes or facts.borehole_quantity or "drilling" in methods or not has_pits)
    return has_boreholes, has_pits


def field_examination_scope(facts: ProposalFacts) -> str:
    has_boreholes, has_pits = investigation_methods(facts)
    actions = []
    if has_boreholes:
        actions.append("drilling/sampling of " + quantity_depth_phrase(
            facts.borehole_program, facts.borehole_quantity, facts.borehole_depth_m, "borehole"))
    if has_pits:
        actions.append("excavation/sampling of " + quantity_depth_phrase(
            facts.test_pit_program, facts.test_pit_quantity, facts.test_pit_depth_m, "test pit"))
    locations = ("Borehole and test pit" if has_boreholes and has_pits
                 else "Borehole" if has_boreholes else "Test pit")
    return (
        "Field examination and " + " and ".join(actions)
        + " below existing grade, refusal, or to depths sufficient to establish subsurface conditions, "
        "whichever is the least. " + locations
        + " locations will be selected based on site access and utility considerations."
    )


def approved_field_program_blocks(facts: ProposalFacts) -> list[ParagraphBlock]:
    """Introductory paragraph, bullets and closing paragraph of the field program."""
    has_boreholes, has_pits = investigation_methods(facts)
    field = field_examination_scope(facts)
    if has_boreholes and has_pits:
        intro, closing = FIELD_PROGRAM_INTRO_MIXED, MIXED_SCOPE_CLOSING
        bullets = [BACKGROUND_SCOPE, UTILITY_SCOPE_MIXED, field, LOGGING_SCOPE_MIXED, SPT_SCOPE_MIXED,
                   LABORATORY_SCOPE, STANDPIPE_SCOPE, TEST_PIT_GROUNDWATER_SCOPE, MIXED_GPS_SCOPE,
                   REPORT_SCOPE]
    elif has_pits:
        intro, closing = FIELD_PROGRAM_INTRO_TEST_PITS, TEST_PIT_SCOPE_CLOSING
        bullets = [BACKGROUND_SCOPE, UTILITY_SCOPE_TEST_PITS, field, LOGGING_SCOPE_TEST_PITS,
                   POCKET_PENETROMETER_SCOPE, LABORATORY_SCOPE_TEST_PITS, TEST_PIT_GROUNDWATER_SCOPE,
                   TEST_PIT_GPS_SCOPE, REPORT_SCOPE]
    else:
        intro, closing = FIELD_PROGRAM_INTRO, BOREHOLE_SCOPE_CLOSING
        bullets = [BACKGROUND_SCOPE, UTILITY_SCOPE, field, LOGGING_SCOPE, SPT_SCOPE, LABORATORY_SCOPE,
                   STANDPIPE_SCOPE, BOREHOLE_GPS_SCOPE, REPORT_SCOPE]
    return [
        ParagraphBlock(text=intro, style="body"),
        *(ParagraphBlock(text=text, style="list") for text in bullets),
        ParagraphBlock(text=closing, style="body"),
    ]


def approved_scope_blocks(facts: ProposalFacts) -> list[ParagraphBlock]:
    """Bullets and closing paragraph only (without the introductory paragraph)."""
    return approved_field_program_blocks(facts)[1:]
