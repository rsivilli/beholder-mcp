from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from beholder_mcp.models import RiskIndicator

# ---------------------------------------------------------------------------
# Type literals
# ---------------------------------------------------------------------------

ConfidenceType = Literal["raw", "derived", "inferred", "manual"]

AwardTypeNormalized = Literal[
    "definitive_contract",
    "indefinite_delivery_contract",
    "delivery_order",
    "other_transaction",
    "sbir",
    "unknown",
]

MoneyValueType = Literal[
    "obligated",
    "total_value",
    "ceiling",
    "pool_ceiling",
    "seed",
    "prime_contract_value",
    "unknown",
    "not_applicable",
]


# ---------------------------------------------------------------------------
# Source / provenance models
# ---------------------------------------------------------------------------


class SourceAttribution(BaseModel):
    source_name: str = Field(
        description="Name of the data source (e.g. 'Beholder / USAspending')"
    )
    source_record_id: Optional[str] = Field(
        default=None, description="Unique identifier of the source record"
    )
    source_url: Optional[str] = Field(
        default=None, description="URL of the source record"
    )
    accessed_at: Optional[str] = Field(
        default=None, description="ISO date when the data was accessed"
    )
    confidence: ConfidenceType = Field(
        description=(
            "How the data was produced: raw (direct from source), derived (calculated), "
            "inferred (interpreted), or manual (human-entered)"
        )
    )


class SourceContext(BaseModel):
    source_name: str = Field(description="Name of the data source")
    accessed_at: Optional[str] = Field(
        default=None, description="ISO date when the data was fetched"
    )
    search_url: Optional[str] = Field(
        default=None, description="URL used to query the data"
    )
    query_filters: dict[str, str] = Field(
        default_factory=dict,
        description="Filters applied to the data query (e.g. entity_uei)",
    )
    result_count: Optional[int] = Field(
        default=None, description="Number of records returned"
    )
    notes: list[str] = Field(
        default_factory=list, description="Additional context notes"
    )


# ---------------------------------------------------------------------------
# Financial models
# ---------------------------------------------------------------------------


class MoneyValue(BaseModel):
    amount: Optional[float] = Field(default=None, description="Numeric dollar amount")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    display_value: Optional[str] = Field(
        default=None,
        description="Human-readable formatted value (e.g. '$454.7M', '$2.1B')",
    )
    value_type: MoneyValueType = Field(
        description=(
            "Category of the value: obligated, total_value, ceiling, pool_ceiling, "
            "seed, prime_contract_value, unknown, or not_applicable"
        )
    )
    is_estimate: bool = Field(
        default=False, description="True if the value is an estimate or approximation"
    )


class AwardFinancials(BaseModel):
    obligated: Optional[MoneyValue] = Field(
        default=None, description="Actual dollars obligated to date"
    )
    total_value: Optional[MoneyValue] = Field(
        default=None,
        description="Total potential contract value if all options are exercised",
    )
    ceiling: Optional[MoneyValue] = Field(
        default=None,
        description="IDIQ or vehicle ceiling (maximum order capacity, not actual spend)",
    )
    pool_ceiling: Optional[MoneyValue] = Field(
        default=None,
        description="Pool-wide ceiling shared across multiple awardees on a vehicle",
    )
    base_and_options_value: Optional[MoneyValue] = Field(
        default=None, description="Base contract value plus all priced options"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Caveats or notes about the financial values",
    )


# ---------------------------------------------------------------------------
# Date / performance models
# ---------------------------------------------------------------------------


class PeriodOfPerformance(BaseModel):
    start_date: Optional[str] = Field(
        default=None, description="ISO date the period of performance begins"
    )
    end_date: Optional[str] = Field(
        default=None, description="ISO date the period of performance ends"
    )
    display_range: str = Field(
        description="Human-readable date range (e.g. 'Aug 2019 – Jul 2026')"
    )
    expiry_label: Optional[str] = Field(
        default=None,
        description=(
            "Concise expiry label (e.g. 'Expires Jul 2026', 'Orders thru Dec 2035')"
        ),
    )
    is_complete: bool = Field(
        default=False, description="True if the period of performance has ended"
    )


class CompetitionInfo(BaseModel):
    competition_type: Optional[str] = Field(
        default=None,
        description="Competition type, e.g. 'Full and Open', 'Not Competed'",
    )
    offeror_count: Optional[int] = Field(
        default=None,
        description="Number of offerors who responded to the solicitation",
    )
    ordering_scope: Optional[str] = Field(
        default=None,
        description="Ordering scope for IDVs (e.g. 'Government-wide', 'Single agency')",
    )


# ---------------------------------------------------------------------------
# Entity / organisation models
# ---------------------------------------------------------------------------


class EntityRef(BaseModel):
    name: str = Field(description="Legal name of the entity")
    uei: Optional[str] = Field(
        default=None, description="SAM.gov Unique Entity Identifier"
    )
    cage_code: Optional[str] = Field(
        default=None, description="Commercial and Government Entity (CAGE) code"
    )


class AgencyOffice(BaseModel):
    agency_name: str = Field(description="Full name of the agency")
    agency_abbrev: Optional[str] = Field(
        default=None, description="Common abbreviation (e.g. 'DoD', 'GSA', 'AF')"
    )
    subagency_name: Optional[str] = Field(
        default=None, description="Sub-agency or department name"
    )
    office_name: Optional[str] = Field(
        default=None, description="Contracting office name"
    )
    office_code: Optional[str] = Field(
        default=None, description="Office code (AAC or similar)"
    )
    display_name: str = Field(
        description="Short display name (e.g. 'GSA / FEDSIM', 'AF / FA8806')"
    )


class EntityProfile(BaseModel):
    legal_name: str = Field(description="Legal registered name of the entity")
    uei: str = Field(description="SAM.gov Unique Entity Identifier")
    cage_code: Optional[str] = Field(
        default=None,
        description="CAGE code (extracted from contract records; not always available)",
    )
    registration_status: Optional[str] = Field(
        default=None, description="SAM.gov registration status (e.g. 'Active')"
    )
    registration_expiration: Optional[str] = Field(
        default=None,
        description="ISO date the SAM.gov registration expires (not available from Beholder API)",
    )
    address_city: Optional[str] = Field(
        default=None, description="City of primary registered address"
    )
    address_state: Optional[str] = Field(
        default=None,
        description="Two-letter state code of primary registered address",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Domain tags (e.g. 'Space', 'Cyber') — not populated by Beholder API",
    )
    source: SourceAttribution = Field(
        description="Source attribution for this profile data"
    )


# ---------------------------------------------------------------------------
# Award models
# ---------------------------------------------------------------------------


class RelatedAward(BaseModel):
    relationship_type: Literal[
        "parent_idiq",
        "delivery_order",
        "seed_order",
        "subcontract_under",
        "follow_on",
        "same_program",
    ] = Field(description="How this award relates to the primary award")
    piid: str = Field(description="PIID of the related contract")
    description: Optional[str] = Field(
        default=None, description="Brief description of the relationship"
    )


class ContractDetail(BaseModel):
    """Full detail record from GET /contracts/{id} — richer than ContractListItem."""

    id: str = Field(description="Beholder UUID for this contract")
    piid: str = Field(description="Procurement Instrument Identifier")
    contract_type: Optional[str] = Field(
        default=None, description="FPDS contract/award type code or label"
    )
    contract_description: Optional[str] = Field(
        default=None, description="Free-text description of the contract scope"
    )
    parent_piid: Optional[str] = Field(
        default=None,
        description="PIID of the parent contract (for delivery orders under an IDV)",
    )
    parent_contract_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the parent contract"
    )
    recipient_name: Optional[str] = Field(
        default=None, description="Legal name of the recipient contractor"
    )
    recipient_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the recipient"
    )
    awarding_agency: Optional[str] = Field(
        default=None, description="Awarding agency name"
    )
    awarding_agency_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the awarding agency"
    )
    awarding_office: Optional[str] = Field(
        default=None, description="Awarding contracting office name"
    )
    awarding_office_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the awarding office"
    )
    funding_agency: Optional[str] = Field(
        default=None,
        description="Funding agency name (may differ from awarding agency)",
    )
    total_obligation: Optional[float] = Field(
        default=None, description="Total dollars obligated to date"
    )
    total_outlayed_amount: Optional[float] = Field(
        default=None, description="Total dollars disbursed to date"
    )
    potential_total_value: Optional[float] = Field(
        default=None,
        description="Maximum potential value if all options are exercised",
    )
    initial_obligation: Optional[float] = Field(
        default=None, description="Original obligation amount at award"
    )
    base_and_all_options_value: Optional[float] = Field(
        default=None, description="Base contract value plus all priced options"
    )
    signed_date: Optional[str] = Field(
        default=None, description="ISO date the contract was signed"
    )
    start_date: Optional[str] = Field(
        default=None, description="ISO date the period of performance begins"
    )
    end_date: Optional[str] = Field(
        default=None, description="ISO date the period of performance ends"
    )
    fiscal_year: Optional[int] = Field(
        default=None, description="Federal fiscal year of the award"
    )
    psc_code: Optional[str] = Field(default=None, description="Product Service Code")
    psc_name: Optional[str] = Field(
        default=None, description="Human-readable PSC description"
    )
    naics_code: Optional[str] = Field(default=None, description="NAICS industry code")
    extent_competed: Optional[str] = Field(
        default=None,
        description="Competition extent (e.g. 'Full and Open', 'Not Competed')",
    )
    number_of_offers_received: Optional[int] = Field(
        default=None, description="Number of proposals received"
    )
    set_aside: Optional[str] = Field(default=None, description="Set-aside designation")
    number_of_actions: Optional[int] = Field(
        default=None,
        description="Total number of contract actions (modifications) on record",
    )
    ordering_period_end_date: Optional[str] = Field(
        default=None,
        description="ISO date after which no new orders may be placed (IDVs only)",
    )
    period_of_performance_potential_end_date: Optional[str] = Field(
        default=None,
        description="Potential end date of the period of performance including all options",
    )
    cage_code: Optional[str] = Field(
        default=None, description="CAGE code of the recipient contractor"
    )
    recipient_address_line_1: Optional[str] = Field(
        default=None, description="Recipient street address line 1"
    )
    recipient_address_line_2: Optional[str] = Field(
        default=None, description="Recipient street address line 2"
    )
    recipient_city_name: Optional[str] = Field(
        default=None, description="Recipient city"
    )
    recipient_zip_4_code: Optional[str] = Field(
        default=None, description="Recipient ZIP+4 code"
    )
    recipient_country_code: Optional[str] = Field(
        default=None, description="Recipient country code"
    )
    status: str = Field(
        default="active", description="Contract status: active or closed"
    )
    child_count: int = Field(
        default=0,
        description="Number of child contracts (delivery orders) under this IDV",
    )
    subaward_count: int = Field(
        default=0,
        description="Number of subawards reported under this contract",
    )
    vehicle_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the parent contract vehicle"
    )
    vehicle_solicitation_identifier: Optional[str] = Field(
        default=None,
        description="Solicitation identifier of the parent vehicle (e.g. 'OASIS', 'SEWP-V')",
    )
    vehicle_title: Optional[str] = Field(
        default=None, description="Human-readable title of the parent vehicle"
    )
    review_priority_score: int = Field(
        default=0, description="Beholder-computed review priority score"
    )
    risk_indicators: list[RiskIndicator] = Field(
        default_factory=list,
        description="Active risk signals for this contract",
    )
    source_system: str = Field(
        default="usaspending", description="Source system for this record"
    )


class Award(BaseModel):
    """Normalized award — assembled from ContractDetail with structured sub-objects."""

    award_id: str = Field(description="Beholder UUID for this award")
    piid: str = Field(description="Procurement Instrument Identifier")
    parent_award_id: Optional[str] = Field(
        default=None, description="Beholder UUID of the parent contract"
    )
    parent_piid: Optional[str] = Field(
        default=None,
        description="PIID of the parent contract (for delivery orders under an IDV)",
    )
    common_name: Optional[str] = Field(
        default=None,
        description="Common program name or vehicle title (e.g. 'ACCESS', 'OASIS+')",
    )
    program_name: Optional[str] = Field(
        default=None, description="Program or program office name"
    )
    award_type: AwardTypeNormalized = Field(
        description=(
            "Normalized award type: definitive_contract, indefinite_delivery_contract, "
            "delivery_order, other_transaction, sbir, or unknown"
        )
    )
    description: Optional[str] = Field(
        default=None, description="Contract scope description"
    )
    psc_code: Optional[str] = Field(default=None, description="Product Service Code")
    psc_name: Optional[str] = Field(default=None, description="PSC description")
    fiscal_year: Optional[int] = Field(
        default=None, description="Federal fiscal year of award"
    )
    recipient: EntityRef = Field(
        description="The contracting entity that received this award"
    )
    awarding_agency: AgencyOffice = Field(
        description="Agency that awarded the contract"
    )
    funding_agency: Optional[AgencyOffice] = Field(
        default=None,
        description="Agency funding the contract (may differ from awarding agency)",
    )
    period_of_performance: PeriodOfPerformance = Field(
        description="Period of performance with display-ready date strings"
    )
    financials: AwardFinancials = Field(
        description="Financial values: obligated, total value, ceiling, and options"
    )
    competition: Optional[CompetitionInfo] = Field(
        default=None, description="Competition details"
    )
    modification_count: Optional[int] = Field(
        default=None,
        description="Number of contract actions (modifications) on record",
    )
    status: str = Field(
        default="unknown",
        description="Contract status: active, complete, expired, or unknown",
    )
    related_awards: list[RelatedAward] = Field(
        default_factory=list,
        description="Related contracts (parent IDV, siblings, delivery orders)",
    )
    source: SourceAttribution = Field(description="Data source attribution")


# ---------------------------------------------------------------------------
# Subcontract models
# ---------------------------------------------------------------------------


class SubcontractRelationship(BaseModel):
    subcontractor: EntityRef = Field(
        description="The entity performing work as subcontractor"
    )
    prime_contractor: EntityRef = Field(
        description="The prime contractor managing the government relationship"
    )
    prime_award_piid: str = Field(description="PIID of the prime contract")
    parent_vehicle_piid: Optional[str] = Field(
        default=None,
        description=(
            "Solicitation identifier of the parent vehicle "
            "(if the prime award is a delivery order under an IDV)"
        ),
    )
    related_order_piids: list[str] = Field(
        default_factory=list,
        description="PIIDs of delivery orders related to this subcontract relationship",
    )
    program_name: Optional[str] = Field(
        default=None, description="Program name associated with this subcontract"
    )
    customer_agency: Optional[AgencyOffice] = Field(
        default=None, description="Government customer agency"
    )
    prime_contract_value: Optional[MoneyValue] = Field(
        default=None,
        description=(
            "Total value of the prime contract (NOT subcontractor revenue — "
            "use subcontract_value for that when available)"
        ),
    )
    subcontract_value: Optional[MoneyValue] = Field(
        default=None, description="Value of the subcontract, if disclosed"
    )
    period: Optional[PeriodOfPerformance] = Field(
        default=None,
        description="Period of performance derived from the prime contract record",
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the work performed under the subcontract",
    )
    strategic_relevance: Optional[str] = Field(
        default=None,
        description="Analyst note on the strategic relevance of this relationship",
    )
    source: SourceAttribution = Field(description="Data source attribution")


# ---------------------------------------------------------------------------
# Portfolio metric models
# ---------------------------------------------------------------------------


class AwardRef(BaseModel):
    piid: str = Field(description="PIID of the referenced award")
    common_name: Optional[str] = Field(
        default=None, description="Common program name, if known"
    )
    display_name: str = Field(
        description="Display label for the award (common_name if available, otherwise PIID)"
    )


class PortfolioMetrics(BaseModel):
    prime_and_ot_award_count: Optional[int] = Field(
        default=None,
        description="Total number of prime awards and other transactions",
    )
    total_obligated: Optional[MoneyValue] = Field(
        default=None,
        description="Sum of all obligated amounts across all awards",
    )
    total_obligated_excluding_ceiling_only: Optional[MoneyValue] = Field(
        default=None,
        description=(
            "Obligated total excluding IDV ceiling-only awards "
            "(where obligated == 0). Use this for headline metrics."
        ),
    )
    largest_obligated_award: Optional[AwardRef] = Field(
        default=None,
        description="The single award with the largest obligated amount",
    )
    activity_start_year: Optional[int] = Field(
        default=None, description="Earliest fiscal year with contract activity"
    )
    activity_end_year: Optional[int] = Field(
        default=None, description="Most recent fiscal year with contract activity"
    )
    active_vehicle_count: Optional[int] = Field(
        default=None,
        description="Number of active IDV vehicles currently in ordering period",
    )
    completed_award_count: Optional[int] = Field(
        default=None, description="Number of completed or expired contracts"
    )
    major_domains: list[str] = Field(
        default_factory=list,
        description="High-level domain labels (e.g. 'Space', 'Cyber') — not populated by API",
    )
    source: SourceAttribution = Field(
        description="Source and methodology attribution for these metrics"
    )


# ---------------------------------------------------------------------------
# Financial rollup models
# ---------------------------------------------------------------------------


class AgencyObligationRollup(BaseModel):
    agency_label: str = Field(description="Display label for the agency")
    agency: Optional[AgencyOffice] = Field(
        default=None, description="Structured agency reference"
    )
    obligated: MoneyValue = Field(
        description="Total obligated amount attributed to this agency"
    )
    included_awards: list[AwardRef] = Field(
        description="Awards contributing to this rollup total"
    )
    highlight_label: Optional[str] = Field(
        default=None, description="Optional highlight annotation for chart display"
    )


class YearlyObligationRollup(BaseModel):
    fiscal_year: int = Field(description="Federal fiscal year")
    obligated: MoneyValue = Field(
        description="Total obligated amount in this fiscal year"
    )
    included_awards: list[AwardRef] = Field(
        description="Awards contributing to this year's total"
    )


class AwardTypeRollup(BaseModel):
    award_type: str = Field(description="Normalized award type")
    obligated: MoneyValue = Field(
        description="Total obligated amount for this award type"
    )
    included_awards: list[AwardRef] = Field(description="Awards of this type")


class FinancialRollups(BaseModel):
    obligated_by_agency: list[AgencyObligationRollup] = Field(
        description="Obligated value broken down by awarding agency, sorted descending"
    )
    obligated_by_year: list[YearlyObligationRollup] = Field(
        default_factory=list,
        description="Obligated value broken down by fiscal year, sorted ascending",
    )
    obligated_by_award_type: list[AwardTypeRollup] = Field(
        default_factory=list,
        description="Obligated value broken down by award type",
    )
    excluded_from_obligation_rollup: list[AwardRef] = Field(
        default_factory=list,
        description="Awards excluded from obligation totals (e.g. ceiling-only IDVs)",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Notes about exclusions and calculation methodology",
    )


# ---------------------------------------------------------------------------
# Top-level payload
# ---------------------------------------------------------------------------


class ContractPortfolioDeckData(BaseModel):
    """Complete structured data payload for generating a federal contract portfolio deck."""

    entity: EntityProfile = Field(
        description="Entity identity and registration details"
    )
    source_context: SourceContext = Field(
        description="Data source provenance for the entire payload"
    )
    portfolio_metrics: PortfolioMetrics = Field(
        description="Headline portfolio metrics (award count, obligated total, activity span)"
    )
    awards: list[Award] = Field(
        description="All normalized prime awards and other transactions for this entity"
    )
    subcontracts: list[SubcontractRelationship] = Field(
        default_factory=list,
        description="Subcontract relationships where this entity is the subcontractor",
    )
    financial_rollups: FinancialRollups = Field(
        description="Pre-computed financial aggregations by agency, year, and award type"
    )
