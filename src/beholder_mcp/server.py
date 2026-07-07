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
# Entry points
# ---------------------------------------------------------------------------


def main_stdio():
    mcp.run(transport="stdio")


def main_http():
    mcp.run(transport="http")


if __name__ == "__main__":
    main_stdio()
