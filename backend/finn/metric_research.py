"""Verified numerical answers using existing documents, retrieval, citations and cache."""

import hashlib
import json
import re
import uuid
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import httpx

from finn.company_directory import resolve_identity
from finn.corpus import ensure_corpus, now
from finn.documents import native_page_texts, resolve_source_quote
from finn.financial_tables import VERSION as TABLE_VERSION
from finn.financial_tables import parse_number
from finn.financials import QUESTION as QUARTERLY_QUESTION
from finn.financials import RESULTS_VERSION
from finn.metric_calculations import VERSION as CALC_VERSION
from finn.metric_calculations import calculate
from finn.metric_evidence import (
    VERSION as EXTRACTION_VERSION,
)
from finn.metric_evidence import (
    Fact,
    entity_period_allowed,
    extract_metric_cells,
    extract_metric_prose,
    issuer_verified,
)
from finn.metric_registry import REGISTRY, financial_intent, normalise
from finn.metric_registry import VERSION as REGISTRY_VERSION
from finn.retrieval import chunk_pages, retrieve_with_diagnostics
from finn.services import DependencyError, MissingConfiguration

VERSION = "verified-financial-metrics-v1.1"


def supplement_quarter_pages(store, document, pages, company, wanted):
    """Read omitted ratio/balance/cash-flow pages from the already stored PDF once.

    The original quarterly extractor deliberately saves P&L pages only. Add bounded
    evidence pages/chunks, never replace validated pages or re-ingest the whole PDF.
    """
    raw = store.get_pdf(document["storage_path"], document["sha256"])
    native = native_page_texts(raw, lambda stage: None)
    if not issuer_verified(
        company, [{"pdf_page": i + 1, "text": text} for i, text in enumerate(native[:5])]
    ):
        return pages, raw
    if len(native) > 200:
        return pages, raw
    present = {p["pdf_page"] for p in pages}
    aliases = [normalise(a) for k in wanted for a in REGISTRY[k].aliases]
    missing = [
        {
            "pdf_page": i + 1,
            "text": text,
            "reading_text": text,
            "metadata_candidates": {"financial_figures_validated": False},
        }
        for i, text in enumerate(native)
        if i + 1 not in present
        and any(" " + a + " " in " " + normalise(text) + " " for a in aliases)
    ][:12]
    if missing:
        store.upsert(
            "finn_document_pages",
            [
                {
                    "document_id": document["id"],
                    "pdf_page": p["pdf_page"],
                    "layout_text": p["text"],
                    "metadata": {"reading_text": p["text"], "financial_figures_validated": False},
                }
                for p in missing
            ],
            conflict="document_id,pdf_page",
        )
        chunks = chunk_pages(document["id"], missing, [])
        if chunks:
            store.upsert("finn_research_chunks", chunks)
            from finn import embeddings

            embeddings.schedule_backfill(company["symbol"])
        pages = pages + missing
    return pages, raw


def verified_quarterly_facts(records, document, pages, company, chunks=()):
    """Reuse server-validated native/two-image cells, never client or LLM draft numbers."""
    metrics = {"Revenue": "revenue", "EBITDA": "ebitda", "PBT": "pbt", "PAT": "pat"}
    by_page = {p["pdf_page"]: p["text"] for p in pages}
    facts = []
    if not issuer_verified(company, pages):
        return facts
    for record in records:
        answer = record["result"]
        data = answer.get("financial_results", {})
        if data.get("version") != TABLE_VERSION or data.get("result_version") != RESULTS_VERSION:
            continue
        for claim in answer.get("claims", []):
            cit = claim.get("citation", {})
            cell = cit.get("financial_evidence", {})
            key = metrics.get(cell.get("metric"))
            if (
                not key
                or cit.get("document_id") != document["id"]
                or cit.get("source_url") != document["source_url"]
            ):
                continue
            raw = parse_number(cell.get("raw_value", ""))
            if (
                raw is None
                or raw != parse_number(str(cell.get("value", "")))
                or not entity_period_allowed(company, cell.get("period_end", ""))
                or cell.get("accounting_basis") not in {"consolidated", "standalone"}
            ):
                continue
            image = cell.get("image_verification")
            if image and (
                image.get("method") != "two_image_reads"
                or image.get("pdf_sha256") != document["sha256"]
            ):
                continue
            chunk = next(
                (
                    c
                    for c in chunks
                    if c["id"] == cit["id"]
                    and c["document_id"] == document["id"]
                    and c["pdf_page"] == cit["pdf_page"]
                ),
                None,
            )
            if not resolve_source_quote(
                cit["quote"], chunk["body"] if chunk else by_page.get(cit["pdf_page"], "")
            ):
                continue
            cite = {
                **cit,
                "metric_evidence": {
                    **cell,
                    "verification": "validated_quarterly_cell",
                    "document_sha256": document["sha256"],
                },
            }
            facts.append(
                Fact(
                    key,
                    raw,
                    cell["unit"],
                    cell["currency"],
                    cell["period_end"],
                    cell["period_kind"],
                    cell["accounting_basis"],
                    company["isin"],
                    cite,
                    key,
                    cell["raw_value"],
                )
            )
    return facts


def dependencies(keys):
    result = set(keys)
    for _ in range(5):
        result.update(k for key in list(result) for k in REGISTRY[key].inputs)
    return result


def sector_for(company):
    text = (company.get("sector", "") or "") + " " + company["name"]
    return (
        "financial"
        if re.search(r"\bbank\b|insurance|financial|finance|investment", text, re.I)
        else "industrial"
    )


def format_value(value):
    return (
        format(value.quantize(Decimal(".01"), rounding=ROUND_HALF_UP), ",.2f")
        .rstrip("0")
        .rstrip(".")
    )


def fact_view(f):
    return {
        "metric": f.metric,
        "name": REGISTRY[f.metric].name,
        "value": str(f.value),
        "display_value": format_value(f.value),
        "unit": f.unit,
        "currency": f.currency,
        "period_end": f.period_end,
        "period_kind": f.period_kind,
        "basis": f.basis,
        "definition": f.definition,
        "method": f.method,
        "formula": f.formula,
        "inputs": [fact_view(i) for i in f.inputs],
    }


def leaves(fact):
    return [c for f in fact.inputs for c in leaves(f)] if fact.inputs else [fact.citation]


def attach_evidence(fact, view, claims):
    """Separate input claims disambiguate two source cells on the same PDF page."""
    if fact.inputs:
        indices = []
        for child, child_view in zip(fact.inputs, view["inputs"]):
            indices.extend(attach_evidence(child, child_view, claims))
    else:
        indices = [len(claims)]
        claims.append(
            {
                "statement": f"{REGISTRY[fact.metric].name}: {format_value(fact.value)} {fact.currency or ''} {fact.unit}; {fact.period_end}, {fact.basis}.",
                "citation": fact.citation,
                "citations": [fact.citation],
                "heading": REGISTRY[fact.metric].name,
            }
        )
    view["claim_index"] = indices[0]
    view["claim_indices"] = indices
    return indices


def interpretation(f):
    value = format_value(f.value)
    if f.metric == "debt_equity" and f.unit == "times":
        return (
            f"The reported definition corresponds to {value} of debt per 1 of equity."
            if f.method == "reported"
            else f"Borrowings are {value} times the verified closing equity balance; lease liabilities are not added separately."
        )
    if f.metric == "current_ratio" and f.unit == "times":
        return f"Current assets are {value} times current liabilities under this definition."
    if f.metric == "net_margin" and f.unit == "%":
        return f"Profit represents {value}% of revenue under the stated definition."
    return (
        "Calculated only from the compatible verified inputs below."
        if f.method == "calculated"
        else "Directly reported; the source's definition and stated unit apply."
    )


def select_results(intent, facts, company):
    results = []
    for key in intent.metrics:
        if key in intent.unsupported_variants:
            results.append(
                {
                    "id": key,
                    "name": REGISTRY[key].name,
                    "status": "unavailable",
                    "support": "unsupported_definition",
                    "reason": "This adjusted/underlying definition is not supported. A standard reported value was not substituted.",
                }
            )
            continue
        if key.startswith("unspecified_"):
            results.append(
                {
                    "id": key,
                    "name": REGISTRY[key].name,
                    "status": "unavailable",
                    "support": REGISTRY[key].support,
                    "reason": "Specify the base metric, such as revenue or profit. A different growth metric was not substituted.",
                }
            )
            continue
        if intent.basis == "both":
            results.append(
                {
                    "id": key,
                    "name": REGISTRY[key].name,
                    "status": "unavailable",
                    "support": REGISTRY[key].support,
                    "reason": "Select standalone or consolidated for this numerical question. Both bases were requested; they were not combined.",
                }
            )
            continue
        candidates = [
            f
            for f in facts
            if (not intent.basis or f.basis == intent.basis)
            and (
                f.period_end in intent.period_ends
                if intent.period_ends
                else not intent.years or int(f.period_end[:4]) in intent.years
            )
            and (not intent.frequency or f.period_kind in {intent.frequency, "point"})
            and not (
                intent.frequency == "year"
                and f.period_kind == "point"
                and f.citation.get("kind") == "quarterly_results"
                and not any(
                    a.period_end == f.period_end and a.citation.get("kind") == "annual_report"
                    for a in facts
                )
            )
        ]
        periods = sorted({f.period_end for f in candidates}, reverse=True)
        requested_periods = []
        multi_dates = len(intent.period_ends) > 1
        if multi_dates:
            requested_periods = sorted(intent.period_ends, reverse=True)
        elif len(intent.years) > 1:
            requested_periods = [
                next((p for p in periods if int(p[:4]) == y), f"{y}-12-31")
                for y in sorted(intent.years, reverse=True)
            ]
        else:
            requested_periods = periods
        found_for_year = set()
        found_dates = set()
        calculation_facts = [
            f for f in facts if not intent.frequency or f.period_kind in {intent.frequency, "point"}
        ]
        saved = []
        last_reason = "The metric could not be verified from the available primary statements. Missing values are not zero."
        for period in requested_periods:
            if not multi_dates and len(intent.years) > 1 and period[:4] in found_for_year:
                continue
            for basis in [intent.basis] if intent.basis else ["consolidated", "standalone"]:
                f, reason = calculate(
                    key,
                    calculation_facts,
                    period,
                    basis,
                    company["isin"],
                    growth_basis=intent.growth_basis,
                    sector=sector_for(company),
                )
                if f:
                    saved.append(f)
                    found_for_year.add(period[:4])
                    found_dates.add(period)
                    break
                last_reason = reason or last_reason
            if saved and len(intent.years) <= 1 and not multi_dates:
                break
        for f in saved:
            results.append(
                {
                    "id": key,
                    "name": REGISTRY[key].name,
                    "status": "verified",
                    **fact_view(f),
                    "interpretation": interpretation(f),
                    "fact": f,
                    "support": REGISTRY[key].support,
                }
            )
        missing_years = (
            [y for y in intent.years if str(y) not in found_for_year]
            if len(intent.years) > 1
            else []
        )
        missing_dates = (
            [p for p in intent.period_ends if p not in found_dates] if multi_dates else []
        )
        if not saved or missing_years or missing_dates:
            results.append(
                {
                    "id": key,
                    "name": REGISTRY[key].name,
                    "status": "unavailable",
                    "support": REGISTRY[key].support,
                    "reason": last_reason,
                    "requested_years": missing_years or list(intent.years),
                    "requested_period_ends": missing_dates,
                    "basis": intent.basis,
                }
            )
    return results


def complete_numerical_answer(intent, results):
    """Intent satisfaction requires a verified value OR an explicit missing reason per metric."""

    def numerical(result):
        try:
            return Decimal(str(result.get("value"))).is_finite() and all(
                result.get(k) for k in ["unit", "basis", "period_end"]
            )
        except (InvalidOperation, ValueError, TypeError):
            return False

    return all(
        any(
            r["id"] == key
            and (
                r["status"] == "verified"
                and numerical(r)
                or r["status"] == "unavailable"
                and r.get("reason")
            )
            for r in results
        )
        for key in intent.metrics
    )


def numerical_research(
    store,
    symbol,
    question,
    *,
    intent=None,
    refresh=False,
    publish=False,
    cached_only=False,
    context=None,
    progress=lambda stage: None,
):
    intent = intent or financial_intent(question)
    if not intent:
        return None
    company = resolve_identity(symbol, store=store)
    docs = store.rows(
        "finn_search_documents",
        symbol="eq." + symbol,
        kind="in.(annual_report,quarterly_results)",
        select="*",
        limit=12,
    )
    notes = []
    quarterly_metrics = {
        "revenue",
        "total_income",
        "ebitda",
        "pbt",
        "pat",
        "eps",
        "diluted_eps",
        "net_margin",
        "ebitda_margin",
        "revenue_growth",
        "profit_growth",
    }
    if not cached_only and (
        refresh
        or not docs
        or not any(d["kind"] == "annual_report" for d in docs)
        and not set(intent.metrics) <= quarterly_metrics
    ):
        try:
            ensure_corpus(store, symbol, refresh=refresh, progress=progress)
            docs = store.rows(
                "finn_search_documents",
                symbol="eq." + symbol,
                kind="in.(annual_report,quarterly_results)",
                select="*",
                limit=12,
            )
        except (ValueError, OSError, DependencyError, MissingConfiguration, httpx.HTTPError) as exc:
            notes.append(
                "Primary-document discovery could not complete; only existing verified sources were considered. "
                + str(exc)[:250]
            )
    quarterly_cache = store.rows(
        "finn_research_cache",
        symbol="eq." + symbol,
        question="eq." + QUARTERLY_QUESTION,
        select="id,result,created_at",
        order="created_at.desc",
        limit=1,
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            sorted((d["id"], d["sha256"], d.get("extraction_version")) for d in docs)
        ).encode()
    ).hexdigest()
    identity = [
        VERSION,
        REGISTRY_VERSION,
        CALC_VERSION,
        EXTRACTION_VERSION,
        TABLE_VERSION,
        RESULTS_VERSION,
        company["isin"],
        asdict(intent),
        fingerprint,
        [(r["id"], r["created_at"]) for r in quarterly_cache],
    ]
    if context:
        identity.append({k: context.get(k) for k in ["research_id", "citation_id", "claim_index"]})
    cache_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    cached = store.rows("finn_research_cache", cache_key="eq." + cache_key, limit=1)
    if (
        cached
        and not refresh
        and complete_numerical_answer(
            intent, cached[0]["result"].get("financial_metrics", {}).get("results", [])
        )
    ):
        return {**cached[0]["result"], "question": question, "cached": True}
    if cached_only:
        return None
    wanted = dependencies(intent.metrics)
    retrieval = None
    try:
        # Hybrid supplies candidate pages. It cannot approve any financial value.
        retrieval = retrieve_with_diagnostics(
            store,
            symbol,
            " ".join(REGISTRY[k].name for k in sorted(wanted)),
            kinds=["annual_report", "quarterly_results"],
        )
    except (DependencyError, MissingConfiguration, httpx.HTTPError, ValueError):
        notes.append(
            "Candidate search was unavailable; deterministic stored-page discovery was used."
        )
    facts = []
    progress("financial_metrics:verification")
    for document in docs:
        stored = store.rows(
            "finn_document_pages",
            document_id="eq." + document["id"],
            select="pdf_page,layout_text,metadata",
            order="pdf_page",
            limit=1000,
        )
        pages = [
            {
                "pdf_page": p["pdf_page"],
                "text": p.get("metadata", {}).get("reading_text") or p["layout_text"],
            }
            for p in stored
        ]
        raw = None
        if document["kind"] == "quarterly_results" and len(pages) < document.get(
            "page_count", len(pages)
        ):
            try:
                pages, raw = supplement_quarter_pages(store, document, pages, company, wanted)
            except (ValueError, OSError, DependencyError, httpx.HTTPError):
                notes.append(
                    "Additional quarterly balance-sheet/ratio pages could not be checked; saved validated pages were retained."
                )
        citation_ids = list(
            {
                c["citation"]["id"]
                for r in quarterly_cache
                for c in r["result"].get("claims", [])
                if c.get("citation", {}).get("document_id") == document["id"]
            }
        )
        chunks = (
            store.rows(
                "finn_research_chunks",
                document_id="eq." + document["id"],
                id="in.(" + ",".join(citation_ids) + ")",
                select="id,document_id,pdf_page,body",
            )
            if citation_ids
            else []
        )
        reused = verified_quarterly_facts(quarterly_cache, document, pages, company, chunks)
        facts.extend(reused)
        # Exact labels rescue numerical disclosures ranked below qualitative passages.
        aliases = [normalise(a) for k in wanted for a in REGISTRY[k].aliases]
        ranked = [
            r["pdf_page"]
            for r in (retrieval or {}).get("evidence", [])
            if r["document_id"] == document["id"]
        ]
        primary_aliases = [normalise(a) for k in intent.metrics for a in REGISTRY[k].aliases]
        primary_pages = [
            p["pdf_page"]
            for p in pages
            if any(" " + a + " " in " " + normalise(p["text"]) + " " for a in primary_aliases)
        ]
        labelled = [
            p["pdf_page"]
            for p in pages
            if any(" " + a + " " in " " + normalise(p["text"]) + " " for a in aliases)
        ]
        selected = list(dict.fromkeys(primary_pages + ranked + labelled))[:18]
        if not selected:
            continue
        try:
            raw = raw or store.get_pdf(document["storage_path"], document["sha256"])
            extracted, warnings = extract_metric_cells(
                raw, document, pages, company, wanted, selected
            )
            verified_keys = {(f.metric, f.period_end, f.basis) for f in reused}
            facts.extend(
                f for f in extracted if (f.metric, f.period_end, f.basis) not in verified_keys
            )
            notes.extend(warnings)
            facts.extend(extract_metric_prose(document, pages, company, wanted, selected))
        except (ValueError, OSError, DependencyError, httpx.HTTPError) as exc:
            notes.append(
                f"{document['discovery_label']}: native metric extraction was unavailable ({type(exc).__name__})."
            )
    results = select_results(intent, facts, company)
    claims = []
    for result in results:
        f = result.pop("fact", None)
        if not f:
            continue
        attach_evidence(f, result, claims)
    assert complete_numerical_answer(intent, results), (
        "Numerical intent was not satisfied or explicitly declined."
    )
    if any(REGISTRY[k].category == "valuation" for k in intent.metrics):
        notes.append(
            "Valuation metrics require a dated explicit primary disclosure. No live price, forward earnings or market valuation was fabricated or calculated."
        )
    notes.append(
        "Native PDF cells and explicitly dated prose only. Ambiguous/scanned tables remain unavailable; no LLM-generated figure is accepted. Definitions may differ between companies."
    )
    if company["symbol"] in {"TMCV", "TMPV"}:
        notes.append(
            "Pre-demerger Tata figures were not recast or substituted for the current issuer. Historical current-entity coverage before October 2025 is not supported."
        )
    checked = max((d["fetched_at"] for d in docs), default=now())
    answer = {
        "id": cached[0]["id"] if cached else str(uuid.uuid4()),
        "symbol": symbol,
        "company_name": company["name"],
        "question": question,
        "status": "answered" if claims else "insufficient_evidence",
        "claims": claims,
        "limitations": list(dict.fromkeys(notes)),
        "coverage": {
            "annual_reports": sum(d["kind"] == "annual_report" for d in docs),
            "transcripts": 0,
            "results_filings": sum(d["kind"] == "quarterly_results" for d in docs),
        },
        "source_checked_at": checked,
        "generated_at": now(),
        "cached": False,
        "retrieval_mode": "verified_financial_metrics",
        "model": "deterministic-financial-metrics",
        "financial_comparisons_enabled": False,
        "financial_metrics": {
            "version": VERSION,
            "calculation_version": CALC_VERSION,
            "results": results,
            "numerical_intent_satisfied": True,
            "document_ids": [d["id"] for d in docs],
        },
        **({"evidence_context": context} if context else {}),
    }
    if docs:
        store.upsert(
            "finn_research_cache",
            [
                {
                    "id": answer["id"],
                    "symbol": symbol,
                    "question": question,
                    "cache_key": cache_key,
                    "corpus_fingerprint": fingerprint,
                    "prompt_version": VERSION,
                    "model": answer["model"],
                    "result": answer,
                    "is_public": publish and not context,
                    "created_at": answer["generated_at"],
                }
            ],
            conflict="cache_key",
        )
    return answer
