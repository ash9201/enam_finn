"""Bounded investor-intent coverage; no extra planning model or new search service."""

import re

import httpx

from finn.retrieval import SETTINGS, retrieve_with_diagnostics
from finn.services import DependencyError

FACETS = {
    "offering": (
        "Products and services",
        r"\b(products?|services?|sells?|manufactur\w*|software|consulting|coffee|tractors?)\b",
        "products services manufacture offerings solutions",
    ),
    "customers": (
        "Customers and markets",
        r"\b(customers?|clients?|industries|sectors?|markets?|retail|enterprises|distribution)\b",
        "customers clients industries markets distribution relationships",
    ),
    "commercial": (
        "Commercial business model",
        r"\b(contracts?|licens\w*|subscriptions?|fees?|fixed.price|time.and.material|unit.of.work|business model|operating model)\b",
        'contracts licensing subscription fees "fixed price" "time and material" delivery',
    ),
    "segments": (
        "Business segments",
        r"\b(segments?|automotive|farm|divisions?|businesses)\b",
        "business segments automotive farm equipment services",
    ),
    "contribution": (
        "Relative segment contribution",
        r"\b(revenue|turnover|sales|contribut\w*|share|percentage)\b",
        '"segment revenue" "external revenue" "segment contribution" "turnover"',
    ),
    "profitability": (
        "Profitability drivers",
        r"\b(profit\w*|margins?|ebitda|costs?|product mix|pricing|logistics)\b",
        "profitability margins EBITDA product mix costs pricing logistics",
    ),
    "demand": (
        "Demand and orders",
        r"\b(demand|orders?|offtake|consumption|orderbook|(?:more|new|return|returning|resum\w*).{0,80}contracts?|contracts?.{0,35}(?:back|return|resum\w*))\b",
        'demand orders "order book" offtake consumption',
    ),
    "capacity": (
        "Production capacity",
        r"\b(capacity|production|plants?|factories|manufactur\w*|utilisation|utilization)\b",
        "capacity production plants utilisation expansion commissioning",
    ),
    "growth": (
        "Growth outlook",
        r"\b(growth|outlook|guidance|expect\w*|expan\w*|future|target\w*)\b",
        "growth outlook guidance expectations expansion targets",
    ),
}
VERSION = "investor-question-coverage-v1"


def plan_question(question):
    q = question.casefold()
    keys = []
    business = bool(re.search(r"business model|core business|commercial model", q))
    if business or re.search(
        r"(?:main|its|their|what|which) (?:products?|services?)|products? (?:and|or) services?|services does|does .* provide",
        q,
    ):
        keys.append("offering")
    # Customer demand is one demand question, not an additional request for a
    # customer profile. Preserve separately requested customers in the same text.
    customer_question = re.sub(r"\b(?:customers?'?|clients?'?)\s+demand\b", "demand", q)
    if business or re.search(r"customers?|clients?|who.*buy", customer_question):
        keys.append("customers")
    if business or re.search(r"generat\w* revenue|revenue streams?|how.*(?:earn|sell)", q):
        keys.append("commercial")
    if re.search(r"segments?|divisions?|major business", q):
        keys.insert(0, "segments")
    if re.search(r"contribut\w*|relative.*(?:size|share)|revenue (?:mix|share)", q):
        keys.append("contribution")
    for key, pattern in [
        ("profitability", r"profitability|margins?|profit drivers"),
        ("demand", r"\bdemand\b|order book"),
        ("capacity", r"\bcapacity\b|production"),
        ("growth", r"\bgrowth\b|future|outlook"),
    ]:
        if re.search(pattern, q):
            keys.append(key)
    return [{"id": k, "label": FACETS[k][0], "query": FACETS[k][2]} for k in dict.fromkeys(keys)][
        :8
    ]


def relevance(item, aspect, question):
    body = item["body"]
    score = len(re.findall(FACETS[aspect][1], body, re.I))
    # Accounting pages can contain useful commercial facts, but their audit detail
    # should not displace actual customer/service/operating evidence.
    if not re.search(r"accounting|recognition|principal|agent", question, re.I):
        score -= 3 * len(
            re.findall(
                r"revenue recognition|principal.or.agent|performance obligations|key audit matter",
                body,
                re.I,
            )
        )
    if aspect == "commercial":
        score += 20 * len(re.findall(r"fixed.price|time.and.material|unit.of.work", body, re.I))
        score += 4 * len(re.findall(r"licens\w*|subscription", body, re.I))
        score += 100 * bool(re.search(r"contracts with customers are either", body, re.I))
        score -= 30 * bool(re.search(r"unbilled|billings", body, re.I))
    if aspect == "contribution":
        score += 5 * bool(re.search(r"segment.{0,30}revenue|external revenue", body, re.I))
        score -= 15 * bool(re.search(r"related.party|proposed transactions", body, re.I))
    if aspect in ["segments", "contribution"] and "standalone" not in question.casefold():
        score += 8 * bool(re.search(r"the group|consolidated", body, re.I))
        score -= 12 * bool(
            re.search(r"standalone financial|standalone.*reported.*segments", body, re.I)
        )
    return score


def select_evidence(base, supplements, plan, question):
    pool = {
        e["chunk_id"]: e for e in [*base, *[e for values in supplements.values() for e in values]]
    }
    selected, pages, documents = [], {}, {}
    cap = max(
        SETTINGS.document_cap,
        (SETTINGS.limit + max(1, len({e["document_id"] for e in pool.values()})) - 1)
        // max(1, len({e["document_id"] for e in pool.values()})),
    )

    def add(item):
        page = (item["document_id"], item["pdf_page"])
        if (
            item in selected
            or pages.get(page, 0) >= SETTINGS.page_cap
            or documents.get(item["document_id"], 0) >= cap
            or len(selected) >= SETTINGS.limit
        ):
            return
        selected.append(item)
        pages[page] = pages.get(page, 0) + 1
        documents[item["document_id"]] = documents.get(item["document_id"], 0) + 1

    # Round-robin keeps one large topic from consuming the entire context window.
    rankings = {
        p["id"]: sorted(pool.values(), key=lambda e: relevance(e, p["id"], question), reverse=True)
        for p in plan
    }
    for rank in range(2):
        for p in plan:
            candidates = [
                e
                for e in rankings[p["id"]]
                if relevance(e, p["id"], question) > 0 and e not in selected
            ]
            for candidate in candidates:
                before = len(selected)
                add(candidate)
                if len(selected) > before:
                    break
    for item in base:
        add(item)
    return selected


def retrieve_planned(store, symbol, question, base, plan, **filters):
    supplements = {}
    # Four keyword queries maximum; the original evaluated hybrid query/RRF and
    # embedding count remain unchanged. All existing metadata filters are forwarded.
    for p in plan[:4]:
        scope = dict(filters)
        if (
            not scope.get("kinds")
            and (
                "management" in question.casefold()
                or p["id"] == "demand"
                and re.search(r"\b(current|latest|recent)\b", question, re.I)
            )
            and p["id"] in ["demand", "growth", "capacity", "profitability"]
        ):
            scope["kinds"] = ["transcript"]
        try:
            if p["id"] == "commercial":
                scope["keyword_override"] = '"contracts with customers" "either"'
            result = retrieve_with_diagnostics(
                store, symbol, p["query"], strategy="keyword", **scope
            )
            supplements[p["id"]] = result["evidence"]
        except (DependencyError, httpx.HTTPError, ValueError, KeyError):
            base.setdefault("question_plan_failures", []).append(p["label"])
    base["evidence"] = select_evidence(base["evidence"], supplements, plan, question)
    base["question_plan"] = plan
    return base


def assess_coverage(plan, claims, evidence):
    result = []
    for p in plan:
        key = p["id"]
        supported = [
            i
            for i, c in enumerate(claims)
            if re.search(FACETS[key][1], c["statement"], re.I)
            and any(
                re.search(FACETS[key][1], s["quote"], re.I)
                for s in c.get("citations", [c["citation"]])
            )
        ]
        if key == "offering":
            supported = [
                i
                for i in supported
                if re.search(
                    r"\b(provid\w*|offer\w*|deliver\w*|develop\w*|manufactur\w*|sell\w*|suppl\w*|production|sale)\b.{0,180}\b(services?|software|products?|solutions?|consulting|engineering|coffee|vehicles?|automobiles?|tractors?)\b|\bservices?\s+(?:include|comprise)",
                    claims[i]["statement"],
                    re.I,
                )
            ]
        if key == "profitability":
            supported = [
                i
                for i in supported
                if re.search(
                    r"cost|product mix|pricing|hedg|logistics|driver|margin.*(?:depend|due|because)",
                    claims[i]["statement"],
                    re.I,
                )
            ]
        if key == "commercial":
            supported = [
                i
                for i in supported
                if not re.search(
                    r"principal.or.agent|revenue recognition|performance obligations",
                    claims[i]["statement"],
                    re.I,
                )
            ]
        if key == "contribution":
            numeric = [
                i
                for i in supported
                if re.search(
                    r"\d.*(?:%|percent|crore|million|billion|lakh)", claims[i]["statement"], re.I
                )
            ]
            status = "covered" if numeric else "partial" if supported else "missing"
            note = (
                "Compatible numerical segment contributions were not verified; qualitative segment descriptions do not establish their relative size."
                if not numeric
                else None
            )
        else:
            status = "covered" if supported else "missing"
            available = any(relevance(e, key, "") > 0 for e in evidence)
            note = (
                None
                if supported
                else "Relevant passages were searched, but no supported answer for this aspect passed validation."
                if available
                else "The retrieved company documents did not supply evidence for this aspect."
            )
        result.append(
            {
                "aspect": key,
                "label": p["label"],
                "status": status,
                "claim_indices": supported,
                "note": note,
            }
        )
    return result


def order_claims(plan, claims, evidence):
    coverage = assess_coverage(plan, claims, evidence)
    priorities = {
        i: min((n for n, c in enumerate(coverage) if i in c["claim_indices"]), default=len(plan))
        for i in range(len(claims))
    }
    return [c for i, c in sorted(enumerate(claims), key=lambda pair: priorities[pair[0]])]


def business_question(question):
    return bool(
        re.search(
            r"business model|core business|commercial model|generat\w* revenue", question, re.I
        )
    ) and not re.search(r"accounting|recognition|principal|agent", question, re.I)


def accounting_detail(text):
    return bool(
        re.search(
            r"revenue recognition|revenue.{0,25}recogni[sz]ed|principal.or.agent|performance obligations|measure of progress|transfer of control|unbilled|billings|unconditional|consideration is",
            text,
            re.I,
        )
    )


def focused_text(question, body):
    if not business_question(question) or not accounting_detail(body):
        return body
    # Supply a contiguous, exact commercial passage, keeping original evidence
    # unchanged for validation and the drawer. Do not splice quoted sentences.
    candidates = list(
        re.finditer(
            r"[^.!?]*(?:contracts? with customers|fixed.price|time.and.material|licens\w*|derives revenues)[^.!?]*[.!?]",
            body,
            re.I,
        )
    )
    eligible = [m for m in candidates if not accounting_detail(m.group(0))]
    match = max(
        eligible,
        key=lambda m: len(
            re.findall(r"fixed.price|time.and.material|unit.of.work", m.group(0), re.I)
        ),
        default=None,
    )
    if match:
        previous = next(
            (
                m
                for m in reversed(eligible)
                if m.end() <= match.start()
                and match.start() - m.end() < 5
                and "derives revenues" in m.group(0).casefold()
            ),
            None,
        )
        return body[previous.start() if previous else match.start() : match.end()].strip()
    return "No commercial passage was isolated from this accounting-focused excerpt."
