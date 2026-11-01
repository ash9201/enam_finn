"""Make an already-verified statement pair concrete without reselecting its evidence."""

import re
from copy import deepcopy

VERSION = "management-reported-readings-v1"


def concrete_comparison(result):
    comparison = result.get("comparison")
    if not comparison:
        return result
    left, right = comparison["earlier"], comparison["later"]
    earlier = left["citation"]["quote"]
    later = right["citation"]["quote"]
    target = re.search(r"\bEBITDA\s+(\d+(?:\.\d+)?)\s*(?:to|[-–])\s*(\d+(?:\.\d+)?)", earlier, re.I)
    # An explicit percentage/unit already has the ordinary comparison treatment.
    if not target or re.search(r"%|percent|\bmargin", earlier, re.I):
        return result
    reported = []
    for m in re.finditer(
        r"\b(EBITDA|EBIT|PAT)\s+(?:(?:was|were)\s+)?(?:at\s+)?(INR\s+)?(\d+(?:\.\d+)?)\s*(%|percent|billion|million|crore|lakh)(?!\w)",
        later,
        re.I,
    ):
        reported.append(
            (
                m.group(1).upper(),
                ("INR " if m.group(2) else "")
                + m.group(3)
                + (" " if m.group(4) != "%" else "")
                + m.group(4),
            )
        )
    if not reported:
        return result
    fiscal = re.search(r"\bFY\s*['’]?(\d{2,4})\b", earlier, re.I)
    period = "FY" + fiscal.group(1) if fiscal else "the stated outlook period"
    identifiers = right["citation"].get("source_identifiers", [])
    later_period = " ".join(
        sorted(
            (x for x in identifiers if re.fullmatch(r"Q[1-4]|FY\d{2,4}", x)),
            key=lambda x: x.startswith("FY"),
        )
    )
    result = deepcopy(result)
    comparison = result["comparison"]
    a = {
        **comparison["earlier"],
        "statement": f"For {period}, management described an EBITDA range of {target.group(1)} to {target.group(2)}. The selected passage does not state a unit for that range.",
    }
    b = {
        **comparison["later"],
        "statement": f"In the later {later_period + ' ' if later_period else ''}call, management reported "
        + ", ".join(label + " of " + value for label, value in reported)
        + ".",
    }
    explanation = "The later figures describe reported quarterly performance. The earlier range has no explicit unit and refers to an outlook period; these sources do not supply a comparable completed full-period outcome. Target delivery or a numerical shortfall cannot be established from this pair."
    synthesis = {
        "statement": explanation,
        "citation": a["citation"],
        "citations": [a["citation"], b["citation"]],
    }
    # Keep the canonical source IDs and parent ID. Old private results remain
    # untouched until the caller explicitly publishes the reviewed presentation.
    old_left, old_right = comparison["earlier"], comparison["later"]
    claims = []
    for claim in result["claims"]:
        if (
            claim["statement"] == old_left["statement"]
            and claim["citation"]["id"] == old_left["citation"]["id"]
        ):
            claims.append(a)
        elif (
            claim["statement"] == old_right["statement"]
            and claim["citation"]["id"] == old_right["citation"]["id"]
        ):
            claims.append(b)
        elif claim not in comparison.get("analysis_claims", []):
            claims.append(claim)
    result["claims"] = [*claims, synthesis]
    comparison.update(
        earlier=a,
        later=b,
        analysis_claims=[synthesis],
        assessment=explanation,
        uncertainty="The target range's unit and a compatible full-period outcome are missing. No percentage unit or target-versus-outcome calculation has been inferred.",
    )
    result["reading_version"] = VERSION
    return result
