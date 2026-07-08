import asyncio
from typing import Annotated, Optional

import httpx
from fastmcp import FastMCP
from pydantic import Field

from beholder_mcp.config import settings
from beholder_mcp.models import (
    CompetitorItem,
    CompetitorsResult,
    ContractListResponse,
    ContractorListResponse,
    ContractorProfile,
    OpportunityListResponse,
    RelatedContractsResponse,
    ResolvedContractor,
    SubawardListResponse,
)
from beholder_mcp.portfolio_helpers import (
    _build_agency_office,
    _build_award_from_detail,
    _build_pop,
    _compute_financial_rollups,
    _compute_portfolio_metrics,
    _format_money_display,
)
from beholder_mcp.portfolio_models import (
    AgencyOffice,
    Award,
    ContractDetail,
    ContractPortfolioDeckData,
    EntityProfile,
    EntityRef,
    FinancialRollups,
    MoneyValue,
    PeriodOfPerformance,
    SourceAttribution,
    SourceContext,
    SubcontractRelationship,
)

mcp = FastMCP("Beholder")

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.beholder_base_url,
            timeout=httpx.Timeout(connect=10, read=120, write=10, pool=10),
        )
    return _client


def _headers() -> dict:
    """Return auth headers for Beholder API."""
    return {"X-API-Key": settings.beholder_api_key}


def _drop_none(**kwargs) -> dict:
    """Build a query params dict, dropping None values."""
    return {k: v for k, v in kwargs.items() if v is not None}


# ---------------------------------------------------------------------------
# Internal resolvers — convert human-friendly IDs to Beholder UUIDs
# ---------------------------------------------------------------------------


async def _resolve_contractor_id(query: str) -> Optional[str]:
    """Resolve a UEI or company name to a Beholder contractor UUID."""
    response = await _get_client().get(
        "/api/v1/contractors",
        params={"q": query, "page_size": 1},
        headers=_headers(),
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    return items[0]["id"] if items else None


async def _resolve_contract_id(piid: str) -> Optional[str]:
    """Resolve a contract PIID to a Beholder contract UUID."""
    response = await _get_client().get(
        "/api/v1/contracts",
        params={"q": piid, "page_size": 1},
        headers=_headers(),
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    return items[0]["id"] if items else None


# ---------------------------------------------------------------------------
# Contractor tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_contractors(
    q: Annotated[
        Optional[str],
        Field(description="Search by company name or UEI"),
    ] = None,
    state: Annotated[
        Optional[str],
        Field(description="Filter by two-letter state code, e.g. VA"),
    ] = None,
    agency_id: Annotated[
        Optional[str],
        Field(description="Filter to contractors with awards from this agency UUID"),
    ] = None,
    sort_by: Annotated[
        Optional[str],
        Field(description="Sort field: total_obligation | contract_count | legal_name"),
    ] = None,
    page: Annotated[int, Field(description="Page number (1-based)", ge=1)] = 1,
    page_size: Annotated[
        int, Field(description="Results per page (max 200)", ge=1, le=200)
    ] = 50,
) -> ContractorListResponse:
    """Search for contractors (vendors/organizations) in the Beholder database."""
    params = _drop_none(
        q=q,
        state=state,
        agency_id=agency_id,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    response = await _get_client().get(
        "/api/v1/contractors", params=params, headers=_headers()
    )
    response.raise_for_status()
    return ContractorListResponse.model_validate(response.json())


@mcp.tool()
async def get_contractor(
    uei: Annotated[
        str,
        Field(description="UEI or company name to look up"),
    ],
) -> ContractorProfile:
    """Get a contractor record by UEI or name.
    Returns a ContractorProfile with top agencies, PSC codes, and risk indicators."""
    contractor_id = await _resolve_contractor_id(uei)
    if not contractor_id:
        raise ValueError(f"No contractor found for '{uei}'")
    response = await _get_client().get(
        f"/api/v1/contractors/{contractor_id}", headers=_headers()
    )
    response.raise_for_status()
    return ContractorProfile.model_validate(response.json())


@mcp.tool()
async def resolve_contractor(
    name: Annotated[str, Field(description="Company name or UEI to resolve")],
    state: Annotated[
        Optional[str],
        Field(description="Narrow by two-letter state code, e.g. CO"),
    ] = None,
) -> ResolvedContractor:
    """Resolve a company name or UEI to its Beholder contractor record and UUID.
    Returns the single best match, or raises an error if none found."""
    params = _drop_none(q=name, state=state, page_size=5)
    response = await _get_client().get(
        "/api/v1/contractors", params=params, headers=_headers()
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        raise ValueError(f"No contractor found matching '{name}'")
    best = items[0]
    return ResolvedContractor(
        id=best["id"],
        uei=best.get("uei"),
        legal_name=best["legal_name"],
        address_city=best.get("address_city"),
        address_state=best.get("address_state"),
        total_obligation=best.get("total_obligation"),
        other_matches=len(items) - 1,
    )


@mcp.tool()
async def get_contractor_profile(
    uei: Annotated[str, Field(description="UEI or name of the company")],
) -> ContractorProfile:
    """Full profile of a contractor: registration details, recent contract history,
    top agencies, PSC codes, vehicle summaries, and risk indicators — in a single call."""
    contractor_id = await _resolve_contractor_id(uei)
    if not contractor_id:
        raise ValueError(f"No contractor found for '{uei}'")
    response = await _get_client().get(
        f"/api/v1/contractors/{contractor_id}", headers=_headers()
    )
    response.raise_for_status()
    return ContractorProfile.model_validate(response.json())


@mcp.tool()
async def find_competitors(
    uei: Annotated[
        str,
        Field(description="UEI or name of the company to find competitors for"),
    ],
    page_size: Annotated[
        int,
        Field(
            description="Number of contracts to sample per PSC code (max 50)",
            ge=1,
            le=50,
        ),
    ] = 20,
) -> CompetitorsResult:
    """Find companies competing in the same PSC code categories as the given contractor.
    Useful for mapping the competitive landscape around a specific contractor."""
    contractor_id = await _resolve_contractor_id(uei)
    if not contractor_id:
        raise ValueError(f"No contractor found for '{uei}'")

    profile_resp = await _get_client().get(
        f"/api/v1/contractors/{contractor_id}", headers=_headers()
    )
    profile_resp.raise_for_status()
    profile = ContractorProfile.model_validate(profile_resp.json())

    psc_codes = [p.psc_code for p in profile.top_psc_codes if p.psc_code]
    if not psc_codes:
        raise ValueError(f"No PSC codes found for contractor '{uei}'")

    # Search contracts by each PSC code in parallel (up to 3 codes)
    async def _search_psc(code: str) -> list:
        r = await _get_client().get(
            "/api/v1/contracts",
            params={"psc_code": code, "page_size": page_size},
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json().get("items", [])

    results = await asyncio.gather(*[_search_psc(c) for c in psc_codes[:3]])

    # Collect unique competitors by contractor UUID, excluding original
    seen: set[str] = {contractor_id}
    competitors: list[CompetitorItem] = []
    for batch in results:
        for contract in batch:
            rid = contract.get("recipient_id")
            if rid and rid not in seen:
                seen.add(rid)
                competitors.append(
                    CompetitorItem(
                        id=rid,
                        name=contract.get("recipient_name"),
                        awarding_agency=contract.get("awarding_agency"),
                        total_obligation=contract.get("total_obligation"),
                        fiscal_year=contract.get("fiscal_year"),
                    )
                )

    return CompetitorsResult(
        contractor_id=contractor_id,
        psc_codes_used=psc_codes[:3],
        competitors=competitors,
    )


# ---------------------------------------------------------------------------
# Opportunity tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_opportunities(
    q: Annotated[
        Optional[str],
        Field(description="Full-text search on opportunity title and description"),
    ] = None,
    notice_type: Annotated[
        Optional[str],
        Field(
            description="Filter by notice type, e.g. Solicitation, Presolicitation, Award Notice"
        ),
    ] = None,
    naics_code: Annotated[
        Optional[str], Field(description="Filter by NAICS code")
    ] = None,
    set_aside_code: Annotated[
        Optional[str],
        Field(description="Filter by set-aside code, e.g. SBA, 8A, HZC, SDVOSBC, WOSB"),
    ] = None,
    cgac: Annotated[
        Optional[str], Field(description="Filter by agency CGAC code")
    ] = None,
    active: Annotated[
        Optional[bool],
        Field(description="Filter by active status (true=open, false=closed)"),
    ] = None,
    posted_after: Annotated[
        Optional[str],
        Field(
            description="ISO date — only notices posted after this date (YYYY-MM-DD)"
        ),
    ] = None,
    posted_before: Annotated[
        Optional[str],
        Field(
            description="ISO date — only notices posted before this date (YYYY-MM-DD)"
        ),
    ] = None,
    deadline_after: Annotated[
        Optional[str],
        Field(
            description="ISO date — only notices with deadline after this date (YYYY-MM-DD)"
        ),
    ] = None,
    deadline_before: Annotated[
        Optional[str],
        Field(
            description="ISO date — only notices with deadline before this date (YYYY-MM-DD)"
        ),
    ] = None,
    sort_by: Annotated[
        Optional[str], Field(description="Sort field (default: posted_date)")
    ] = None,
    sort_dir: Annotated[
        Optional[str], Field(description="asc or desc (default: desc)")
    ] = None,
    page: Annotated[int, Field(description="Page number (1-based)", ge=1)] = 1,
    page_size: Annotated[
        int, Field(description="Results per page (max 200)", ge=1, le=200)
    ] = 50,
) -> OpportunityListResponse:
    """Search for contract opportunities (solicitations and award notices)."""
    params = _drop_none(
        q=q,
        notice_type=notice_type,
        naics_code=naics_code,
        set_aside_code=set_aside_code,
        cgac=cgac,
        active=active,
        posted_after=posted_after,
        posted_before=posted_before,
        deadline_after=deadline_after,
        deadline_before=deadline_before,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    response = await _get_client().get(
        "/api/v1/opportunities", params=params, headers=_headers()
    )
    response.raise_for_status()
    return OpportunityListResponse.model_validate(response.json())


# ---------------------------------------------------------------------------
# Contract & subaward tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def search_contracts(
    q: Annotated[
        Optional[str],
        Field(description="PIID prefix search (e.g. W912DY)"),
    ] = None,
    recipient_uei: Annotated[
        Optional[str],
        Field(
            description="UEI or name of the recipient contractor — auto-resolved to Beholder UUID"
        ),
    ] = None,
    agency_id: Annotated[
        Optional[str],
        Field(description="Awarding agency UUID"),
    ] = None,
    psc_code: Annotated[
        Optional[str], Field(description="Filter by PSC code (exact match)")
    ] = None,
    fiscal_year: Annotated[
        Optional[int], Field(description="Filter by fiscal year")
    ] = None,
    min_obligation: Annotated[
        Optional[float], Field(description="Minimum total obligation in dollars")
    ] = None,
    max_obligation: Annotated[
        Optional[float], Field(description="Maximum total obligation in dollars")
    ] = None,
    date_from: Annotated[
        Optional[str],
        Field(description="Signed date from (ISO date, e.g. 2023-01-01)"),
    ] = None,
    date_to: Annotated[
        Optional[str],
        Field(description="Signed date to (ISO date, e.g. 2024-12-31)"),
    ] = None,
    status: Annotated[
        Optional[str], Field(description="Filter by status: active | closed")
    ] = None,
    award_type_category: Annotated[
        Optional[str],
        Field(
            description="Award type: delivery_order | purchase_order | bpa_call | idv | definitive_contract"
        ),
    ] = None,
    sort_by: Annotated[
        Optional[str],
        Field(description="Sort field: total_obligation | signed_date | fiscal_year"),
    ] = None,
    sort_dir: Annotated[Optional[str], Field(description="asc or desc")] = None,
    page: Annotated[int, Field(description="Page number (1-based)", ge=1)] = 1,
    page_size: Annotated[
        int, Field(description="Results per page (max 200)", ge=1, le=200)
    ] = 50,
) -> ContractListResponse:
    """Search awarded contract records. Use recipient_uei to find all contracts
    awarded to a specific company. Filter by psc_code, fiscal_year, or date range."""
    contractor_id: Optional[str] = None
    if recipient_uei:
        contractor_id = await _resolve_contractor_id(recipient_uei)
        if not contractor_id:
            raise ValueError(f"No contractor found for '{recipient_uei}'")

    params = _drop_none(
        q=q,
        contractor_id=contractor_id,
        agency_id=agency_id,
        psc_code=psc_code,
        fiscal_year=fiscal_year,
        min_obligation=min_obligation,
        max_obligation=max_obligation,
        date_from=date_from,
        date_to=date_to,
        status=status,
        award_type_category=award_type_category,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    response = await _get_client().get(
        "/api/v1/contracts", params=params, headers=_headers()
    )
    response.raise_for_status()
    return ContractListResponse.model_validate(response.json())


@mcp.tool()
async def get_related_contracts(
    contract_id: Annotated[
        str,
        Field(description="Contract PIID to find related contracts for"),
    ],
) -> RelatedContractsResponse:
    """Given a contract PIID, find related contracts (parent, siblings, same vehicle,
    same awardee). Replaces the manual NAICS/agency/set-aside similarity search."""
    beholder_id = await _resolve_contract_id(contract_id)
    if not beholder_id:
        raise ValueError(f"No contract found for PIID '{contract_id}'")
    response = await _get_client().get(
        f"/api/v1/contracts/{beholder_id}/related", headers=_headers()
    )
    response.raise_for_status()
    return RelatedContractsResponse.model_validate(response.json())


@mcp.tool()
async def search_subawards(
    piid: Annotated[
        str,
        Field(
            description="Prime contract PIID — retrieves all subawards under that contract"
        ),
    ],
    page: Annotated[int, Field(description="Page number (1-based)", ge=1)] = 1,
    page_size: Annotated[
        int, Field(description="Results per page (max 200)", ge=1, le=200)
    ] = 50,
) -> SubawardListResponse:
    """Get subawards reported under a specific prime contract by PIID."""
    contract_id = await _resolve_contract_id(piid)
    if not contract_id:
        raise ValueError(f"No contract found for PIID '{piid}'")
    params = _drop_none(page=page, page_size=page_size)
    response = await _get_client().get(
        f"/api/v1/contracts/{contract_id}/subawards",
        params=params,
        headers=_headers(),
    )
    response.raise_for_status()
    return SubawardListResponse.model_validate(response.json())


# ---------------------------------------------------------------------------
# Portfolio / slide deck tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_contract_detail(
    piid: Annotated[str, Field(description="Contract PIID to look up")],
) -> ContractDetail:
    """Get the full detail record for a contract by PIID.
    Returns all available fields: parent contract, funding agency, period of performance,
    financial values (obligated, potential, base+options), competition details, and vehicle info."""
    contract_id = await _resolve_contract_id(piid)
    if not contract_id:
        raise ValueError(f"No contract found for PIID '{piid}'")
    response = await _get_client().get(
        f"/api/v1/contracts/{contract_id}", headers=_headers()
    )
    response.raise_for_status()
    return ContractDetail.model_validate(response.json())


@mcp.tool()
async def get_entity_awards(
    uei: Annotated[str, Field(description="UEI or company name")],
    include_inactive: Annotated[
        bool,
        Field(description="Include completed and expired contracts (default true)"),
    ] = True,
    page_size: Annotated[
        int,
        Field(
            description="Contracts per page when fetching the list (max 200)",
            ge=1,
            le=200,
        ),
    ] = 50,
) -> list[Award]:
    """Get all contracts for a company as normalized Award objects with structured financials,
    period of performance, competition details, and agency information.
    Makes one detail API call per contract — expect several seconds for large portfolios."""
    contractor_id = await _resolve_contractor_id(uei)
    if not contractor_id:
        raise ValueError(f"No contractor found for '{uei}'")

    all_items: list[dict] = []
    page = 1
    while True:
        resp = await _get_client().get(
            f"/api/v1/contractors/{contractor_id}/contracts",
            params={"page": page, "page_size": page_size},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        all_items.extend(items)
        if len(all_items) >= data.get("total", 0) or not items:
            break
        page += 1

    awards: list[Award] = []
    for item in all_items:
        contract_id_val = item.get("contract_id")
        if not contract_id_val:
            continue
        detail_resp = await _get_client().get(
            f"/api/v1/contracts/{contract_id_val}", headers=_headers()
        )
        if detail_resp.status_code != 200:
            continue
        detail = detail_resp.json()
        if not include_inactive and detail.get("status") not in ("active",):
            continue
        awards.append(_build_award_from_detail(detail))

    return awards


@mcp.tool()
async def get_subcontract_history(
    uei: Annotated[str, Field(description="UEI or company name")],
) -> list[SubcontractRelationship]:
    """Get subcontract relationships where the given company appears as the subcontractor.
    Enriches each subaward with prime contract details: period, agency, vehicle, and prime value."""
    contractor_id = await _resolve_contractor_id(uei)
    if not contractor_id:
        raise ValueError(f"No contractor found for '{uei}'")

    resp = await _get_client().get(
        f"/api/v1/contractors/{contractor_id}/subawards-received",
        params={"page_size": 200},
        headers=_headers(),
    )
    resp.raise_for_status()
    subawards = resp.json().get("items", [])

    relationships: list[SubcontractRelationship] = []
    for sub in subawards:
        prime_contract_id = sub.get("prime_contract_id")
        prime_detail: Optional[dict] = None
        if prime_contract_id:
            prime_resp = await _get_client().get(
                f"/api/v1/contracts/{prime_contract_id}", headers=_headers()
            )
            if prime_resp.status_code == 200:
                prime_detail = prime_resp.json()

        pop: Optional[PeriodOfPerformance] = None
        prime_value: Optional[MoneyValue] = None
        customer_agency: Optional[AgencyOffice] = None
        parent_vehicle_piid: Optional[str] = None

        if prime_detail:
            pop = _build_pop(
                prime_detail.get("start_date"),
                prime_detail.get("end_date"),
                prime_detail.get("ordering_period_end_date"),
            )
            ptv = prime_detail.get("potential_total_value")
            if ptv is not None:
                prime_value = MoneyValue(
                    amount=ptv,
                    display_value=_format_money_display(ptv),
                    value_type="prime_contract_value",
                )
            customer_agency = _build_agency_office(
                prime_detail.get("awarding_agency"),
                prime_detail.get("awarding_office"),
            )
            parent_vehicle_piid = prime_detail.get("vehicle_solicitation_identifier")

        sub_amount = sub.get("subaward_amount")
        relationships.append(
            SubcontractRelationship(
                subcontractor=EntityRef(
                    name=sub.get("sub_recipient_name") or "Unknown",
                    uei=sub.get("sub_recipient_uei"),
                ),
                prime_contractor=EntityRef(
                    name=sub.get("prime_recipient_name") or "Unknown",
                    uei=sub.get("prime_recipient_uei"),
                ),
                prime_award_piid=sub.get("prime_award_id_piid") or "",
                parent_vehicle_piid=parent_vehicle_piid,
                customer_agency=customer_agency,
                prime_contract_value=prime_value,
                subcontract_value=MoneyValue(
                    amount=sub_amount,
                    display_value=_format_money_display(sub_amount),
                    value_type="obligated",
                )
                if sub_amount is not None
                else None,
                period=pop,
                description=sub.get("subaward_description"),
                source=SourceAttribution(
                    source_name="Beholder / USAspending",
                    source_record_id=sub.get("id"),
                    confidence="raw",
                ),
            )
        )

    return relationships


@mcp.tool()
async def get_financial_rollups(
    uei: Annotated[str, Field(description="UEI or company name")],
    exclude_ceiling_only: Annotated[
        bool,
        Field(
            description=(
                "Exclude IDV ceiling-only awards (zero obligated) from obligation totals. "
                "Default true to avoid inflating headline numbers."
            )
        ),
    ] = True,
) -> FinancialRollups:
    """Get obligated value rollups by agency, fiscal year, and award type for a contractor.
    IDV ceiling-only awards are excluded by default to avoid inflating obligation totals."""
    awards = await get_entity_awards(uei)
    return _compute_financial_rollups(awards, exclude_ceiling_only=exclude_ceiling_only)


@mcp.tool()
async def get_contract_portfolio_deck_data(
    uei: Annotated[str, Field(description="UEI or company name")],
    include_subcontracts: Annotated[
        bool,
        Field(
            description="Include subcontract history (fetches additional API records)"
        ),
    ] = True,
) -> ContractPortfolioDeckData:
    """Fetch all structured data needed to generate a federal contract portfolio presentation.
    Returns entity profile, all normalized awards with financials and period of performance,
    subcontract history, financial rollups by agency/year/type, and headline portfolio metrics.
    This is the primary tool for slide deck data generation — gets everything in one call."""
    contractor_id = await _resolve_contractor_id(uei)
    if not contractor_id:
        raise ValueError(f"No contractor found for '{uei}'")

    # Fetch contractor profile in background while awards are retrieved
    profile_task = asyncio.create_task(
        _get_client().get(f"/api/v1/contractors/{contractor_id}", headers=_headers())
    )

    awards = await get_entity_awards(uei)

    profile_resp = await profile_task
    profile_resp.raise_for_status()
    profile_data = profile_resp.json()

    # Extract CAGE code from the first award that has one
    cage_code: Optional[str] = next(
        (a.recipient.cage_code for a in awards if a.recipient.cage_code), None
    )

    entity = EntityProfile(
        legal_name=profile_data["legal_name"],
        uei=profile_data.get("uei") or uei,
        cage_code=cage_code,
        registration_status=profile_data.get("sam_status"),
        address_city=profile_data.get("address_city"),
        address_state=profile_data.get("address_state"),
        source=SourceAttribution(
            source_name="Beholder / SAM.gov",
            source_record_id=contractor_id,
            confidence="raw",
        ),
    )

    subcontracts: list[SubcontractRelationship] = []
    if include_subcontracts:
        subcontracts = await get_subcontract_history(uei)

    metrics = _compute_portfolio_metrics(awards)
    rollups = _compute_financial_rollups(awards, exclude_ceiling_only=True)

    return ContractPortfolioDeckData(
        entity=entity,
        source_context=SourceContext(
            source_name="Beholder / USAspending",
            query_filters={"entity_uei": entity.uei},
            result_count=len(awards),
        ),
        portfolio_metrics=metrics,
        awards=awards,
        subcontracts=subcontracts,
        financial_rollups=rollups,
    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def main_stdio():
    mcp.run(transport="stdio")


def main_http():
    mcp.run(transport="http")


if __name__ == "__main__":
    main_stdio()
