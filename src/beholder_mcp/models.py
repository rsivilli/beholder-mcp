from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Enum literals derived from the Beholder OpenAPI schema
SignalType = Literal[
    "CompetitionRisk",
    "ModificationGrowth",
    "VendorConcentration",
    "TimingRisk",
    "DocumentationGap",
    "DescriptionOpacity",
    "RelatedContractCluster",
    "PSCConcentration",
    "FundingAgencyDivergence",
]

SignalSeverity = Literal["critical", "high", "medium", "low", "info", "none"]

RiskEntityType = Literal["Contract", "Contractor", "Office", "Agency", "AwardVehicle"]

AwardTypeCategory = Literal[
    "delivery_order", "purchase_order", "bpa_call", "idv", "definitive_contract"
]


# ---------------------------------------------------------------------------
# Shared / nested models
# ---------------------------------------------------------------------------


class RiskEvidence(BaseModel):
    evidence_type: str = Field(
        description="Category of evidence supporting this risk signal"
    )
    source_field: str = Field(
        description="The data field from which the evidence was extracted"
    )
    evidence_value: str = Field(description="Raw value observed in the source field")
    evidence_text: str = Field(description="Human-readable description of the evidence")
    confidence: float = Field(
        description="Confidence score for this piece of evidence (0–1)"
    )


class RiskIndicator(BaseModel):
    id: str = Field(description="Unique identifier for this risk indicator instance")
    entity_type: RiskEntityType = Field(
        description="Type of entity this indicator applies to: Contract, Contractor, Office, Agency, or AwardVehicle"
    )
    entity_id: str = Field(description="UUID of the entity this indicator applies to")
    signal_type: SignalType = Field(
        description=(
            "Machine-readable signal category: CompetitionRisk, ModificationGrowth, "
            "VendorConcentration, TimingRisk, DocumentationGap, DescriptionOpacity, "
            "RelatedContractCluster, PSCConcentration, or FundingAgencyDivergence"
        )
    )
    signal_name: str = Field(description="Human-readable name for the signal type")
    severity: SignalSeverity = Field(
        description="Severity level: critical, high, medium, low, info, or none"
    )
    score: int = Field(description="Numeric risk score for this indicator")
    raw_value: Optional[float] = Field(
        default=None,
        description="Raw underlying metric value that triggered the signal",
    )
    percentile: Optional[float] = Field(
        default=None,
        description="Percentile rank of this entity's raw value relative to all entities (0–100)",
    )
    explanation: str = Field(
        description="Plain-language explanation of why this signal was raised"
    )
    caveat: str = Field(
        description="Limitations or caveats to consider when interpreting this signal"
    )
    methodology_version: str = Field(
        description="Version of the scoring methodology used"
    )
    evidence: list[RiskEvidence] = Field(
        description="Supporting evidence items for this indicator"
    )


class TopAgency(BaseModel):
    agency_name: str = Field(description="Name of the awarding agency")
    obligation: float = Field(
        description="Total dollars obligated by this agency to the contractor"
    )
    share: float = Field(
        description="Fraction of the contractor's total obligations from this agency (0–1)"
    )


class TopPscCode(BaseModel):
    psc_code: str = Field(description="Product Service Code (PSC)")
    description: str = Field(description="Human-readable description of the PSC")
    obligation: float = Field(description="Total dollars obligated under this PSC code")


class VehicleSummary(BaseModel):
    vehicle_id: str = Field(description="Beholder UUID for the contract vehicle (IDV)")
    solicitation_identifier: str = Field(
        description="Solicitation identifier (e.g. OASIS, SEWP V) used as the vehicle key"
    )
    title: Optional[str] = Field(
        default=None, description="Human-readable title of the contract vehicle"
    )
    vehicle_type: Optional[str] = Field(
        default=None, description="Type of vehicle, e.g. GWAC, IDIQ, BPA"
    )
    idv_piid: str = Field(
        description="PIID of the indefinite-delivery vehicle (IDV) base contract"
    )
    total_task_order_value: Optional[float] = Field(
        default=None,
        description="Total obligated value across all task/delivery orders under this vehicle",
    )
    task_order_count: int = Field(
        default=0,
        description="Number of task or delivery orders issued under this vehicle",
    )
    ordering_period_end_date: Optional[str] = Field(
        default=None,
        description="ISO date when new orders can no longer be placed against this vehicle",
    )


class ContractorContract(BaseModel):
    contract_id: str = Field(description="Beholder UUID for this contract")
    piid: str = Field(
        description="Procurement Instrument Identifier — the official contract number"
    )
    status: str = Field(
        default="active", description="Contract status: active or closed"
    )
    contract_description: Optional[str] = Field(
        default=None, description="Free-text description of the contract's scope"
    )
    awarding_agency: Optional[str] = Field(
        default=None, description="Name of the agency that awarded this contract"
    )
    awarding_office: Optional[str] = Field(
        default=None,
        description="Name of the contracting office within the awarding agency",
    )
    total_obligation: Optional[float] = Field(
        default=None, description="Total dollars obligated to date under this contract"
    )
    signed_date: Optional[str] = Field(
        default=None, description="ISO date the contract was signed"
    )
    fiscal_year: Optional[int] = Field(
        default=None, description="Federal fiscal year in which the contract was signed"
    )
    psc_code: Optional[str] = Field(
        default=None, description="Product Service Code classifying the work performed"
    )
    extent_competed: Optional[str] = Field(
        default=None, description="Competition extent, e.g. Full and Open, Not Competed"
    )
    review_priority_score: int = Field(
        default=0,
        description="Beholder-computed review priority score (higher = more scrutiny warranted)",
    )
    award_type_category: Optional[AwardTypeCategory] = Field(
        default=None,
        description="Award type: delivery_order, purchase_order, bpa_call, idv, or definitive_contract",
    )
    potential_total_value: Optional[float] = Field(
        default=None, description="Maximum potential value if all options are exercised"
    )
    start_date: Optional[str] = Field(
        default=None, description="ISO date the period of performance begins"
    )
    end_date: Optional[str] = Field(
        default=None, description="ISO date the period of performance ends"
    )
    ordering_period_end_date: Optional[str] = Field(
        default=None,
        description="For IDVs: ISO date after which no new orders may be placed",
    )


# ---------------------------------------------------------------------------
# Contractor responses
# ---------------------------------------------------------------------------


class ContractorListItem(BaseModel):
    id: str = Field(description="Beholder UUID for this contractor")
    legal_name: str = Field(description="Legal registered name of the contractor")
    display_name: Optional[str] = Field(
        default=None, description="Preferred display name, if different from legal name"
    )
    uei: Optional[str] = Field(
        default=None, description="SAM.gov Unique Entity Identifier (UEI)"
    )
    address_city: Optional[str] = Field(
        default=None, description="City of the contractor's primary registered address"
    )
    address_state: Optional[str] = Field(
        default=None,
        description="Two-letter state code of the contractor's primary registered address",
    )
    total_obligation: float = Field(
        description="Total dollars obligated to this contractor across all contracts"
    )
    contract_count: int = Field(
        description="Number of contracts awarded to this contractor"
    )
    agency_count: int = Field(
        description="Number of distinct agencies that have awarded to this contractor"
    )
    review_priority_score: int = Field(
        description="Beholder-computed review priority score (higher = more scrutiny warranted)"
    )


class ContractorListResponse(BaseModel):
    items: list[ContractorListItem] = Field(
        description="Contractor records matching the query"
    )
    total: int = Field(
        description="Total number of matching contractors across all pages"
    )
    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")


class ContractorProfile(BaseModel):
    id: str = Field(description="Beholder UUID for this contractor")
    uei: Optional[str] = Field(
        default=None, description="SAM.gov Unique Entity Identifier (UEI)"
    )
    legal_name: str = Field(description="Legal registered name of the contractor")
    display_name: Optional[str] = Field(
        default=None, description="Preferred display name, if different from legal name"
    )
    entity_type: Optional[str] = Field(
        default=None, description="SAM.gov entity type, e.g. Business or Individual"
    )
    address_city: Optional[str] = Field(
        default=None, description="City of the contractor's primary registered address"
    )
    address_state: Optional[str] = Field(
        default=None,
        description="Two-letter state code of the contractor's primary registered address",
    )
    sam_status: Optional[str] = Field(
        default=None,
        description="SAM.gov registration status, e.g. Active, Expired, or Excluded",
    )
    total_obligation: float = Field(
        description="Total dollars obligated to this contractor across all contracts"
    )
    contract_count: int = Field(
        description="Total number of contracts awarded to this contractor"
    )
    agency_count: int = Field(
        description="Number of distinct agencies that have awarded contracts to this contractor"
    )
    office_count: int = Field(
        description="Number of distinct contracting offices that have awarded to this contractor"
    )
    fiscal_years: list[int] = Field(
        description="Federal fiscal years in which this contractor received at least one award"
    )
    top_agencies: list[TopAgency] = Field(
        description="Agencies that have obligated the most dollars to this contractor"
    )
    top_psc_codes: list[TopPscCode] = Field(
        description="Product Service Codes under which this contractor has received the most obligations"
    )
    review_priority_score: int = Field(
        default=0,
        description="Beholder-computed review priority score (higher = more scrutiny warranted)",
    )
    risk_indicators: list[RiskIndicator] = Field(
        default=[],
        description="Active risk signals detected for this contractor",
    )
    vehicle_summary: list[VehicleSummary] = Field(
        default=[],
        description="Contract vehicles (IDVs) on which this contractor holds a position",
    )
    recent_contracts: list[ContractorContract] = Field(
        description="Most recently awarded contracts for this contractor"
    )
    subaward_received_count: int = Field(
        default=0,
        description="Number of subawards this contractor has received as a subcontractor",
    )
    subaward_awarded_count: int = Field(
        default=0,
        description="Number of subawards this contractor has issued to subcontractors",
    )


class ResolvedContractor(BaseModel):
    id: str = Field(
        description="Beholder UUID — use this in other tools that accept a contractor ID"
    )
    uei: Optional[str] = Field(
        default=None, description="SAM.gov Unique Entity Identifier (UEI)"
    )
    legal_name: str = Field(description="Legal registered name of the contractor")
    address_city: Optional[str] = Field(
        default=None, description="City of the contractor's primary registered address"
    )
    address_state: Optional[str] = Field(
        default=None,
        description="Two-letter state code of the contractor's primary registered address",
    )
    total_obligation: Optional[float] = Field(
        default=None,
        description="Total dollars obligated to this contractor across all contracts",
    )
    other_matches: int = Field(
        description="Number of additional contractors that also matched the query"
    )


class CompetitorItem(BaseModel):
    id: str = Field(description="Beholder UUID for this competing contractor")
    name: Optional[str] = Field(
        default=None, description="Legal name of the competing contractor"
    )
    awarding_agency: Optional[str] = Field(
        default=None,
        description="Agency that awarded the sampled contract identifying this competitor",
    )
    total_obligation: Optional[float] = Field(
        default=None,
        description="Total obligation on the sampled contract that identified this competitor",
    )
    fiscal_year: Optional[int] = Field(
        default=None,
        description="Fiscal year of the sampled contract that identified this competitor",
    )


class CompetitorsResult(BaseModel):
    contractor_id: str = Field(description="Beholder UUID of the source contractor")
    psc_codes_used: list[str] = Field(
        description="PSC codes from the source contractor's top codes used to find competitors"
    )
    competitors: list[CompetitorItem] = Field(
        description="Contractors found competing in the same PSC code categories"
    )


# ---------------------------------------------------------------------------
# Opportunity responses
# ---------------------------------------------------------------------------


class OpportunityListItem(BaseModel):
    notice_id: str = Field(description="Unique notice identifier from SAM.gov")
    title: Optional[str] = Field(
        default=None, description="Title of the solicitation or notice"
    )
    sol_number: Optional[str] = Field(
        default=None,
        description="Solicitation number assigned by the contracting office",
    )
    notice_type: Optional[str] = Field(
        default=None,
        description="Notice type, e.g. Solicitation, Presolicitation, Award Notice, Sources Sought",
    )
    set_aside: Optional[str] = Field(
        default=None,
        description="Set-aside designation, e.g. Small Business, 8(a), HUBZone",
    )
    department_agency: Optional[str] = Field(
        default=None, description="Department or agency posting the notice"
    )
    cgac: Optional[str] = Field(
        default=None,
        description="Common Government-wide Accounting Classification (CGAC) agency code",
    )
    office_name: Optional[str] = Field(
        default=None, description="Name of the contracting office posting the notice"
    )
    aac_code: Optional[str] = Field(
        default=None, description="Activity Address Code of the posting office"
    )
    posted_date: Optional[str] = Field(
        default=None, description="ISO datetime when the notice was published"
    )
    response_deadline: Optional[str] = Field(
        default=None, description="ISO datetime by which responses or offers are due"
    )
    active: Optional[bool] = Field(
        default=None, description="True if the notice is currently open for responses"
    )
    award_number: Optional[str] = Field(
        default=None,
        description="Contract award number, populated for Award Notice types",
    )
    award_date: Optional[str] = Field(
        default=None,
        description="ISO date the contract was awarded, populated for Award Notice types",
    )
    award_amount: Optional[float] = Field(
        default=None,
        description="Dollar amount of the award, populated for Award Notice types",
    )
    awardee: Optional[str] = Field(
        default=None,
        description="Name of the winning offeror, populated for Award Notice types",
    )
    link: Optional[str] = Field(
        default=None, description="URL to the full notice on SAM.gov"
    )


class OpportunityListResponse(BaseModel):
    items: list[OpportunityListItem] = Field(
        description="Opportunity notices matching the query"
    )
    total: int = Field(description="Total number of matching notices across all pages")
    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")


# ---------------------------------------------------------------------------
# Contract responses
# ---------------------------------------------------------------------------


class ContractListItem(BaseModel):
    id: str = Field(description="Beholder UUID for this contract")
    piid: str = Field(
        description="Procurement Instrument Identifier — the official contract number"
    )
    status: str = Field(
        default="active", description="Contract status: active or closed"
    )
    contract_description: Optional[str] = Field(
        default=None, description="Free-text description of the contract's scope"
    )
    recipient_name: Optional[str] = Field(
        default=None, description="Legal name of the contractor who received the award"
    )
    recipient_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the recipient contractor"
    )
    awarding_agency: Optional[str] = Field(
        default=None, description="Name of the agency that awarded this contract"
    )
    awarding_agency_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the awarding agency"
    )
    fiscal_year: Optional[int] = Field(
        default=None, description="Federal fiscal year in which the contract was signed"
    )
    total_obligation: Optional[float] = Field(
        default=None, description="Total dollars obligated to date under this contract"
    )
    extent_competed: Optional[str] = Field(
        default=None, description="Competition extent, e.g. Full and Open, Not Competed"
    )
    review_priority_score: int = Field(
        default=0,
        description="Beholder-computed review priority score (higher = more scrutiny warranted)",
    )


class ContractListResponse(BaseModel):
    items: list[ContractListItem] = Field(
        description="Contract records matching the query"
    )
    total: int = Field(
        description="Total number of matching contracts across all pages"
    )
    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")


class RelatedContractsResponse(BaseModel):
    relation_label: str = Field(
        description="Label describing how these contracts relate to the source, e.g. 'Same Vehicle', 'Same Awardee'"
    )
    contracts: list[ContractorContract] = Field(
        description="Contracts related to the queried PIID"
    )


# ---------------------------------------------------------------------------
# Subaward responses
# ---------------------------------------------------------------------------


class SubawardListItem(BaseModel):
    id: str = Field(description="Beholder UUID for this subaward record")
    subaward_number: Optional[str] = Field(
        default=None, description="Subaward number assigned by the prime contractor"
    )
    subaward_amount: Optional[float] = Field(
        default=None, description="Dollar amount of the subaward"
    )
    subaward_action_date: Optional[str] = Field(
        default=None, description="ISO date the subaward action was executed"
    )
    subaward_description: Optional[str] = Field(
        default=None, description="Description of the work performed under the subaward"
    )
    sub_recipient_name: Optional[str] = Field(
        default=None, description="Legal name of the subcontractor receiving the award"
    )
    sub_recipient_uei: Optional[str] = Field(
        default=None, description="SAM.gov UEI of the subcontractor"
    )
    place_of_performance_city: Optional[str] = Field(
        default=None, description="City where the subaward work is performed"
    )
    place_of_performance_state: Optional[str] = Field(
        default=None,
        description="Two-letter state code where the subaward work is performed",
    )
    prime_award_id_piid: Optional[str] = Field(
        default=None,
        description="PIID of the prime contract under which this subaward was issued",
    )
    prime_contract_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the prime contract"
    )
    prime_recipient_name: Optional[str] = Field(
        default=None, description="Legal name of the prime contractor"
    )
    prime_recipient_uei: Optional[str] = Field(
        default=None, description="SAM.gov UEI of the prime contractor"
    )
    awarding_agency_name: Optional[str] = Field(
        default=None, description="Name of the agency that awarded the prime contract"
    )


class SubawardListResponse(BaseModel):
    items: list[SubawardListItem] = Field(
        description="Subaward records under the queried prime contract"
    )
    total: int = Field(description="Total number of subawards across all pages")
    page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")
