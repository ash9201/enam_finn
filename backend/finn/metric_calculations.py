"""Approved Decimal formulas. Every operand retains its original evidence."""

from decimal import Decimal

from finn.financial_tables import shift_quarter
from finn.metric_evidence import SCALES, Fact
from finn.metric_registry import REGISTRY

VERSION = "metric-calculations-v1"


def supported_fact(fact):
    return bool(
        fact.citation.get("metric_evidence", {}).get("verification")
        in {"native_pdf_geometry", "explicit_dated_prose", "validated_quarterly_cell"}
        or fact.method == "calculated"
        and fact.inputs
        and all(supported_fact(x) for x in fact.inputs)
    )


def compatible(facts):
    return bool(
        facts
        and all(supported_fact(f) for f in facts)
        and len({(f.entity, f.basis, f.currency, f.period_end) for f in facts}) == 1
        and len({f.period_kind for f in facts if f.period_kind != "point"}) <= 1
        and all(f.unit in SCALES for f in facts)
        and all(f.period_kind in {"year", "quarter", "point"} for f in facts)
    )


def amount(fact):
    return fact.value * SCALES[fact.unit]


def unique_fact(facts, key, period, basis, entity):
    values = [
        f
        for f in facts
        if f.metric == key
        and f.period_end == period
        and f.basis == basis
        and f.entity == entity
        and supported_fact(f)
    ]
    signatures = {
        (
            f.value * SCALES.get(f.unit, Decimal(1)),
            f.currency,
            "money" if f.unit in SCALES else f.unit,
            f.definition,
            f.period_kind,
        )
        for f in values
    }
    if len(signatures) != 1:
        return None
    return values[0] if values else None


def calculate(
    key, facts, period, basis, entity, *, growth_basis="yoy", sector="industrial", depth=0
):
    direct = unique_fact(facts, key, period, basis, entity)
    if direct:
        return direct, None
    metric = REGISTRY[key]
    if any(
        f.metric == key and f.period_end == period and f.basis == basis and f.entity == entity
        for f in facts
    ):
        return None, "Conflicting reported values or definitions; no value was selected."
    if not metric.formula or depth > 4:
        return (
            None,
            "No unambiguous directly disclosed value was verified; this metric has no approved calculation.",
        )
    if sector != "industrial":
        return (
            None,
            "Industrial-company formulas are disabled for banks, insurers and financial-service entities; a disclosed value is required.",
        )
    inputs = []
    for required in metric.inputs:
        f, _ = calculate(
            required,
            facts,
            period,
            basis,
            entity,
            growth_basis=growth_basis,
            sector=sector,
            depth=depth + 1,
        )
        if not f:
            return None, "Compatible verified inputs are missing: " + ", ".join(
                REGISTRY[k].name for k in metric.inputs
            ) + "."
        inputs.append(f)
    if not compatible(inputs):
        return (
            None,
            "Inputs have incompatible periods, currencies, units, entities or accounting bases.",
        )
    if (metric.formula in {"percent", "cash_flow"} or key == "interest_coverage") and (
        any(f.period_kind not in {"year", "quarter"} for f in inputs)
        or len({f.period_kind for f in inputs}) != 1
    ):
        return (
            None,
            "Flow inputs need the same verified annual or quarterly duration; an as-at balance, YTD or unknown-duration amount was not substituted.",
        )
    values = [amount(f) for f in inputs]
    unit, currency = "rupee", inputs[0].currency
    formula = ""
    if metric.formula == "sum_debt":
        result = sum(values)
        formula = "Current borrowings + non-current borrowings (lease liabilities excluded unless reported in those inputs)"
    elif metric.formula == "subtract":
        result = values[0] - values[1]
        formula = REGISTRY[metric.inputs[0]].name + " − " + REGISTRY[metric.inputs[1]].name
    elif metric.formula in {"ratio", "percent"}:
        if values[1] <= 0:
            return None, "The denominator is zero or negative; this ratio was not calculated."
        if key == "debt_equity" and values[0] < 0:
            return None, "Negative gross debt is not a valid input for this calculation."
        result = values[0] / values[1] * (100 if metric.formula == "percent" else 1)
        unit, currency = ("%" if metric.formula == "percent" else "times"), None
        formula = (
            REGISTRY[metric.inputs[0]].name
            + " / "
            + REGISTRY[metric.inputs[1]].name
            + (" × 100" if unit == "%" else "")
        )
    elif metric.formula == "cash_flow":
        if values[1] > 0:
            return (
                None,
                "Cash capex must be an explicitly signed cash outflow; an accrual capex or unsigned spending figure was not substituted.",
            )
        result = values[0] + values[1]
        formula = "Operating cash flow + signed cash purchases of PPE and intangibles"
    elif metric.formula == "growth":
        current = inputs[0]
        if (
            current.period_kind not in {"year", "quarter"}
            or growth_basis == "qoq"
            and current.period_kind != "quarter"
        ):
            return (
                None,
                "Compatible complete annual/quarterly periods are required; YTD and stub periods are not subtracted.",
            )
        prior = shift_quarter(period, -3 if growth_basis == "qoq" else -12)
        previous = unique_fact(facts, metric.inputs[0], prior, basis, entity)
        if (
            not previous
            or previous.period_kind != current.period_kind
            or previous.currency != current.currency
            or previous.unit not in SCALES
        ):
            return None, "A compatible preceding period was not verified."
        if amount(previous) <= 0:
            return None, "Percentage growth is unavailable for a zero or negative comparison base."
        inputs.append(previous)
        result = (amount(current) - amount(previous)) / amount(previous) * 100
        unit, currency = "%", None
        formula = f"({REGISTRY[metric.inputs[0]].name} − {prior} value) / {prior} value × 100"
    elif metric.formula in {"average_return", "average_roce"}:
        if inputs[0].period_kind != "year":
            return (
                None,
                "Returns require a full annual profit period and compatible opening/closing balances; quarterly annualisation is not implemented.",
            )
        if key == "roe" and inputs[1].definition != "owners_equity":
            return (
                None,
                "ROE requires owners' equity excluding non-controlling interests, not an interchangeable total-equity figure.",
            )
        prior = shift_quarter(period, -12)
        opening = [unique_fact(facts, k, prior, basis, entity) for k in metric.inputs[1:]]
        if not all(opening) or any(f.currency != currency or f.unit not in SCALES for f in opening):
            return None, "Compatible opening balances for an average denominator were not verified."
        if key == "roe" and opening[0].definition != "owners_equity":
            return None, "Opening and closing owners' equity definitions differ."
        closing = values[1] if key == "roe" else values[1] - values[2]
        start = amount(opening[0]) if key == "roe" else amount(opening[0]) - amount(opening[1])
        if start <= 0 or closing <= 0:
            return (
                None,
                "Opening or closing capital is zero or negative; an average return was not calculated.",
            )
        result = values[0] / ((start + closing) / 2) * 100
        inputs.extend(opening)
        unit, currency = "%", None
        formula = (
            "Profit attributable to owners / average opening and closing owners' equity × 100"
            if key == "roe"
            else "Reported EBIT / average opening and closing (total assets − current liabilities) × 100"
        )
    else:
        return None, "Calculation not implemented."
    if unit == "rupee":
        result /= SCALES[inputs[0].unit]
        unit = inputs[0].unit
    return Fact(
        key,
        result,
        unit,
        currency,
        period,
        inputs[0].period_kind,
        basis,
        entity,
        inputs[0].citation,
        key,
        method="calculated",
        inputs=inputs,
        formula=formula,
    ), None
