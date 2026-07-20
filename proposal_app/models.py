from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CostLineItem(BaseModel):
    section: str = "Field Program"
    item: str = ""
    description: str = ""
    unit: str = ""
    estimate: float | None = None
    rate: float | None = None
    total: float | None = None


class InvestigationDepthGroup(BaseModel):
    quantity: int = Field(gt=0)
    termination_depth_m: float = Field(gt=0)


class ProposalFacts(BaseModel):
    proposal_number: str = ""
    proposal_date: str = Field(default_factory=lambda: date.today().isoformat())
    client_name: str = ""
    client_address: str = ""
    contact_name: str = ""
    contact_title: str = ""
    contact_email: str = ""
    client_reference_number: str = ""
    project_name: str = ""
    project_location: str = ""
    development_description: str = ""
    project_type: str = "general building/site development"
    requested_services: list[str] = Field(default_factory=list)
    investigation_methods: list[str] = Field(default_factory=list)
    borehole_program: list[InvestigationDepthGroup] = Field(default_factory=list)
    test_pit_program: list[InvestigationDepthGroup] = Field(default_factory=list)
    borehole_quantity: int | None = None
    borehole_depth_m: float | None = None
    test_pit_quantity: int | None = None
    test_pit_depth_m: float | None = None
    access_notes: str = ""
    utility_locate_notes: str = ""
    groundwater_notes: str = ""
    laboratory_tests: list[str] = Field(default_factory=list)
    reporting_requirements: list[str] = Field(default_factory=list)
    other_notes: str = ""
    cost_items: list[CostLineItem] = Field(default_factory=list)


class ParagraphBlock(BaseModel):
    text: str
    style: Literal["body", "list"] = "body"


class DraftContent(BaseModel):
    introduction: str
    field_program_intro: str
    field_program_paragraphs: list[ParagraphBlock]
    cost_intro: str
    terms_and_conditions: str
    closure_paragraph_1: str
    closure_paragraph_2: str
    work_authorization_scope: str
    email_subject: str
    email_body: str
    warnings: list[str] = Field(default_factory=list)


class CostSummary(BaseModel):
    items: list[CostLineItem]
    section_totals: dict[str, float]
    final_total: float
    warnings: list[str]


class ReferenceMatch(BaseModel):
    filename: str
    project_type: str
    methods: list[str]
    score: float
    has_cost_table: bool
    sections: dict[str, str]


class RuleCandidate(BaseModel):
    key: str
    category: str = "wording"
    instruction: str
    reusable: bool = True
    rationale: str = ""


class RevisionAnalysis(BaseModel):
    summary: str
    candidates: list[RuleCandidate] = Field(default_factory=list)
