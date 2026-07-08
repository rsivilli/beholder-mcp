"""
Portfolio helpers — pure data-transform functions used by the portfolio MCP tools.

These functions are stateless and have no dependency on the MCP server instance,
making them straightforward to test independently.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as _date
from typing import Optional

from beholder_mcp.portfolio_models import (
    AgencyObligationRollup,
    AgencyOffice,
    Award,
    AwardFinancials,
    AwardRef,
    AwardTypeRollup,
    CompetitionInfo,
    EntityRef,
    FinancialRollups,
    MoneyValue,
    PeriodOfPerformance,
    PortfolioMetrics,
    SourceAttribution,
    YearlyObligationRollup,
)

# ---------------------------------------------------------------------------
# FPDS contract-type code → normalised award type
# ---------------------------------------------------------------------------

_FPDS_CODE_MAP: dict[str, str] = {
    "A": "indefinite_delivery_contract",
    "B": "definitive_contract",
    "C": "delivery_order",
    "D": "delivery_order",
    "IDC": "indefinite_delivery_contract",
    "IDO": "indefinite_delivery_contract",
    "IDP": "indefinite_delivery_contract",
    "IDQ": "indefinite_delivery_contract",
    "IDS": "indefinite_delivery_contract",
    "IDR": "indefinite_delivery_contract",
    "J": "other_transaction",
    "K": "other_transaction",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_money_display(amount: Optional[float]) -> Optional[str]:
    """Return a compact, human-readable dollar string (e.g. '$454.7M', '$2.1B')."""
    if amount is None:
        return None
    abs_v = abs(amount)
    if abs_v >= 1_000_000_000:
        return f"${abs_v / 1_000_000_000:.1f}B"
    if abs_v >= 1_000_000:
        return f"${abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"${abs_v / 1_000:.0f}K"
    return f"${abs_v:,.0f}"


# ---------------------------------------------------------------------------
# Model-building helpers
# ---------------------------------------------------------------------------


def _build_pop(
    start_date: Optional[str],
    end_date: Optional[str],
    ordering_end_date: Optional[str],
) -> PeriodOfPerformance:
    """Construct a PeriodOfPerformance with human-readable display strings."""

    def _parse(s: Optional[str]) -> Optional[_date]:
        if not s:
            return None
        try:
            return _date.fromisoformat(s[:10])
        except (ValueError, TypeError):
            return None

    def _fmt(d: Optional[_date]) -> str:
        return d.strftime("%b %Y") if d else "?"

    start = _parse(start_date)
    end = _parse(end_date)
    ordering_end = _parse(ordering_end_date)

    if start and end:
        display_range = f"{_fmt(start)} \u2013 {_fmt(end)}"
    elif start:
        display_range = f"{_fmt(start)} \u2013 present"
    elif end:
        display_range = f"? \u2013 {_fmt(end)}"
    else:
        display_range = "Unknown"

    expiry_label: Optional[str] = None
    if ordering_end:
        expiry_label = f"Orders thru {_fmt(ordering_end)}"
    elif end:
        expiry_label = f"Expires {_fmt(end)}"

    today = _date.today()
    effective_end = ordering_end or end
    is_complete = bool(effective_end and effective_end < today)

    return PeriodOfPerformance(
        start_date=start_date,
        end_date=end_date,
        display_range=display_range,
        expiry_label=expiry_label,
        is_complete=is_complete,
    )


def _build_agency_office(
    agency_str: Optional[str],
    office_str: Optional[str],
) -> AgencyOffice:
    """Build an AgencyOffice from flat agency/office name strings."""
    agency_name = agency_str or "Unknown Agency"
    display_parts = [p for p in [agency_name, office_str] if p]
    return AgencyOffice(
        agency_name=agency_name,
        office_name=office_str,
        display_name=" / ".join(display_parts),
    )


def _derive_award_type(
    contract_type: Optional[str],
    award_type_category: Optional[str],
) -> str:
    """Map FPDS contract_type or award_type_category to a normalised award type string."""
    if award_type_category:
        _atc_map = {
            "idv": "indefinite_delivery_contract",
            "delivery_order": "delivery_order",
            "purchase_order": "definitive_contract",
            "bpa_call": "delivery_order",
            "definitive_contract": "definitive_contract",
        }
        return _atc_map.get(award_type_category, "unknown")
    if contract_type:
        upper = contract_type.upper().strip()
        if upper in _FPDS_CODE_MAP:
            return _FPDS_CODE_MAP[upper]
        if any(x in upper for x in ("INDEFINITE DELIVERY", "IDIQ", "GWAC")):
            return "indefinite_delivery_contract"
        if "OTHER TRANSACTION" in upper:
            return "other_transaction"
        if upper.startswith("ID"):
            return "indefinite_delivery_contract"
        if any(x in upper for x in ("DELIVERY ORDER", "TASK ORDER")):
            return "delivery_order"
    return "unknown"


def _build_award_from_detail(data: dict) -> Award:
    """Transform a raw ContractDetail API dict into a normalised Award model."""
    award_type = _derive_award_type(
        data.get("contract_type"),
        data.get("award_type_category"),
    )
    is_idv = award_type == "indefinite_delivery_contract"

    obligated = data.get("total_obligation")
    total_val = data.get("potential_total_value")
    base_opts = data.get("base_and_all_options_value")

    financials = AwardFinancials(
        obligated=MoneyValue(
            amount=obligated,
            display_value=_format_money_display(obligated),
            value_type="obligated",
        )
        if obligated is not None
        else None,
        total_value=MoneyValue(
            amount=total_val,
            display_value=_format_money_display(total_val),
            value_type="total_value",
        )
        if not is_idv and total_val is not None
        else None,
        ceiling=MoneyValue(
            amount=total_val,
            display_value=_format_money_display(total_val),
            value_type="ceiling",
        )
        if is_idv and total_val is not None
        else None,
        base_and_options_value=MoneyValue(
            amount=base_opts,
            display_value=_format_money_display(base_opts),
            value_type="total_value",
        )
        if base_opts is not None
        else None,
    )

    pop = _build_pop(
        data.get("start_date"),
        data.get("end_date"),
        data.get("ordering_period_end_date"),
    )

    awarding_agency = _build_agency_office(
        data.get("awarding_agency"),
        data.get("awarding_office"),
    )

    funding_agency: Optional[AgencyOffice] = None
    if data.get("funding_agency"):
        funding_agency = _build_agency_office(data["funding_agency"], None)

    competition: Optional[CompetitionInfo] = None
    if data.get("extent_competed") or data.get("number_of_offers_received"):
        competition = CompetitionInfo(
            competition_type=data.get("extent_competed"),
            offeror_count=data.get("number_of_offers_received"),
        )

    return Award(
        award_id=data["id"],
        piid=data["piid"],
        parent_award_id=data.get("parent_contract_id"),
        parent_piid=data.get("parent_piid"),
        common_name=data.get("vehicle_title"),
        award_type=award_type,
        description=data.get("contract_description"),
        psc_code=data.get("psc_code"),
        psc_name=data.get("psc_name"),
        fiscal_year=data.get("fiscal_year"),
        recipient=EntityRef(
            name=data.get("recipient_name") or "Unknown",
            cage_code=data.get("cage_code"),
        ),
        awarding_agency=awarding_agency,
        funding_agency=funding_agency,
        period_of_performance=pop,
        financials=financials,
        competition=competition,
        modification_count=data.get("number_of_actions"),
        status=data.get("status", "unknown"),
        source=SourceAttribution(
            source_name="Beholder / USAspending",
            source_record_id=data["id"],
            confidence="raw",
        ),
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _compute_portfolio_metrics(awards: list[Award]) -> PortfolioMetrics:
    """Compute headline portfolio metrics from a list of normalised Award objects."""
    total_obligated = 0.0
    total_obligated_excl = 0.0
    largest_amount = -1.0
    largest_award: Optional[Award] = None
    activity_years: list[int] = []
    active_vehicle_count = 0
    completed_count = 0

    for award in awards:
        obl = award.financials.obligated
        obl_amount = obl.amount if obl and obl.amount is not None else 0.0
        total_obligated += obl_amount

        is_ceiling_only = (
            award.award_type == "indefinite_delivery_contract" and obl_amount == 0.0
        )
        if not is_ceiling_only:
            total_obligated_excl += obl_amount

        if obl_amount > largest_amount:
            largest_amount = obl_amount
            largest_award = award

        if award.fiscal_year:
            activity_years.append(award.fiscal_year)

        if (
            award.award_type == "indefinite_delivery_contract"
            and award.status == "active"
        ):
            active_vehicle_count += 1

        if award.status in ("complete", "expired", "closed"):
            completed_count += 1

    largest_ref: Optional[AwardRef] = None
    if largest_award:
        largest_ref = AwardRef(
            piid=largest_award.piid,
            common_name=largest_award.common_name,
            display_name=largest_award.common_name or largest_award.piid,
        )

    return PortfolioMetrics(
        prime_and_ot_award_count=len(awards),
        total_obligated=MoneyValue(
            amount=total_obligated,
            display_value=_format_money_display(total_obligated),
            value_type="obligated",
        ),
        total_obligated_excluding_ceiling_only=MoneyValue(
            amount=total_obligated_excl,
            display_value=_format_money_display(total_obligated_excl),
            value_type="obligated",
        ),
        largest_obligated_award=largest_ref,
        activity_start_year=min(activity_years) if activity_years else None,
        activity_end_year=max(activity_years) if activity_years else None,
        active_vehicle_count=active_vehicle_count,
        completed_award_count=completed_count,
        source=SourceAttribution(
            source_name="Beholder / USAspending",
            confidence="derived",
        ),
    )


def _compute_financial_rollups(
    awards: list[Award],
    exclude_ceiling_only: bool = True,
) -> FinancialRollups:
    """
    Aggregate obligated values by agency, fiscal year, and award type.

    IDV ceiling-only awards (zero obligated) are excluded from all totals when
    exclude_ceiling_only=True to avoid inflating headline obligation numbers.
    """
    agency_amounts: dict[str, float] = defaultdict(float)
    agency_offices: dict[str, AgencyOffice] = {}
    agency_award_refs: dict[str, list[AwardRef]] = defaultdict(list)
    year_amounts: dict[int, float] = defaultdict(float)
    year_award_refs: dict[int, list[AwardRef]] = defaultdict(list)
    type_amounts: dict[str, float] = defaultdict(float)
    type_award_refs: dict[str, list[AwardRef]] = defaultdict(list)
    excluded: list[AwardRef] = []

    for award in awards:
        obl = award.financials.obligated
        obl_amount = obl.amount if obl and obl.amount is not None else 0.0

        is_ceiling_only = (
            award.award_type == "indefinite_delivery_contract" and obl_amount == 0.0
        )
        award_ref = AwardRef(
            piid=award.piid,
            common_name=award.common_name,
            display_name=award.common_name or award.piid,
        )

        if exclude_ceiling_only and is_ceiling_only:
            excluded.append(award_ref)
            continue

        label = award.awarding_agency.display_name
        agency_amounts[label] += obl_amount
        agency_offices[label] = award.awarding_agency
        agency_award_refs[label].append(award_ref)

        if award.fiscal_year:
            year_amounts[award.fiscal_year] += obl_amount
            year_award_refs[award.fiscal_year].append(award_ref)

        type_amounts[award.award_type] += obl_amount
        type_award_refs[award.award_type].append(award_ref)

    def _mv(amount: float) -> MoneyValue:
        return MoneyValue(
            amount=amount,
            display_value=_format_money_display(amount),
            value_type="obligated",
        )

    by_agency = sorted(
        [
            AgencyObligationRollup(
                agency_label=lbl,
                agency=agency_offices.get(lbl),
                obligated=_mv(agency_amounts[lbl]),
                included_awards=agency_award_refs[lbl],
            )
            for lbl in agency_amounts
        ],
        key=lambda r: r.obligated.amount or 0.0,
        reverse=True,
    )

    by_year = sorted(
        [
            YearlyObligationRollup(
                fiscal_year=yr,
                obligated=_mv(year_amounts[yr]),
                included_awards=year_award_refs[yr],
            )
            for yr in year_amounts
        ],
        key=lambda r: r.fiscal_year,
    )

    by_type = [
        AwardTypeRollup(
            award_type=atype,
            obligated=_mv(type_amounts[atype]),
            included_awards=type_award_refs[atype],
        )
        for atype in type_amounts
    ]

    notes: list[str] = []
    if exclude_ceiling_only and excluded:
        notes.append(
            f"{len(excluded)} IDV ceiling-only award(s) excluded from obligation totals."
        )

    return FinancialRollups(
        obligated_by_agency=by_agency,
        obligated_by_year=by_year,
        obligated_by_award_type=by_type,
        excluded_from_obligation_rollup=excluded,
        notes=notes,
    )
