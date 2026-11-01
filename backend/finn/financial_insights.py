"""Concise observations derived only from approved cells and Decimal changes."""

from copy import deepcopy
from decimal import Decimal

VERSION = "validated-performance-v1"


def with_performance(result):
    if not result.get("financial_results"):
        return result
    result = deepcopy(result)
    data = result["financial_results"]
    for basis, view in data.get("bases", {}).items():
        rows = {r["metric"]: r for r in view["rows"]}
        observations, prior_signature = [], None
        for kind, base in [("yoy", "year_ago"), ("qoq", "previous")]:
            parts, indices, directions = [], [], {}
            for metric in ["Revenue", "PBT", "PAT"]:
                row = rows.get(metric)
                if not row or row.get(kind, {}).get("absolute") is None:
                    continue
                current, previous = row["figures"]["latest"], row["figures"][base]
                delta = Decimal(row[kind]["absolute"])
                directions[metric] = 1 if delta > 0 else -1 if delta < 0 else 0
                label = (
                    "Bank total income" if current["definition"] == "bank_total_income" else metric
                )
                verb = "rose" if delta > 0 else "fell" if delta < 0 else "was unchanged"
                value = (
                    f"{abs(Decimal(row[kind]['percent']))}%"
                    if row[kind]["percent"] is not None
                    else f"{view['currency']} {abs(delta)} {view['unit']}"
                )
                parts.append(label + " " + verb + (" by " + value if delta else ""))
                indices.extend([current["claim_index"], previous["claim_index"]])
            signature = tuple(directions.items())
            if not parts or signature == prior_signature:
                continue
            period = "Year on year" if kind == "yoy" else "Quarter on quarter"
            statement = period + ", " + "; ".join(parts) + "."
            if directions.get("Revenue") == 1 and all(
                directions.get(m) == -1 for m in ["PBT", "PAT"]
            ):
                statement += " Higher revenue did not translate into higher reported profits."
            observations.append(
                {
                    "statement": statement,
                    "comparison": kind,
                    "claim_indices": list(dict.fromkeys(indices)),
                }
            )
            prior_signature = signature
        view["performance"] = observations
    data["performance_version"] = VERSION
    data["performance_caveat"] = (
        "These are observed changes in reported figures. Their causes have not been established by the calculations."
    )
    return result
