"""Opt-in real-source follow-up smoke test; writes only private research and local artifacts."""

import json
from pathlib import Path

from finn.config import load_local_env
from finn.evidence import document_date
from finn.research import research_company
from finn.store import open_store

OUTPUT = Path("artifacts/release")
ROOT_QUESTION = (
    "How did management describe freeze-dried coffee utilisation and product mix in the July call?"
)
QUESTION = "What did later management commentary say about freeze-dried coffee demand and premiumisation? Describe the later observations without inferring financial target delivery."


def main():
    load_local_env()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with open_store() as store:
        company = store.rows("finn_companies", symbol="eq.CCL", select="manifest", limit=1)
        manifest = company[0]["manifest"] if company else []
        if not manifest:
            raise SystemExit("CCL has no active source manifest; ingest real documents first.")
        documents = store.rows(
            "finn_documents",
            symbol="eq.CCL",
            kind="eq.transcript",
            state="eq.ready",
            id="in.(" + ",".join(manifest) + ")",
        )
        dated = sorted(
            (document_date(store, d).get("document_date", ""), d["id"]) for d in documents
        )
        dated = [pair for pair in dated if pair[0][:10] in ["2026-07-28", "2026-10-16"]]
        if len(dated) < 2:
            raise SystemExit(
                "This smoke case requires two original CCL calls with observable dates."
            )
        # Prepared source-specific acceptance case; application discovery is generic.
        root = research_company(
            store, "CCL", ROOT_QUESTION, kinds=["transcript"], document_ids=[dated[0][1]]
        )
        claim = next((c for c in root["claims"] if "freeze" in c["statement"].lower()), None)
        if not claim:
            raise SystemExit(
                "The primary source did not support the smoke-case anchor; no substitute used."
            )
        reference = {
            "research_id": root["id"],
            "citation_id": claim["citation"]["id"],
            "claim_index": root["claims"].index(claim),
            "intent": "later",
        }
        result = research_company(store, "CCL", QUESTION, context_reference=reference)
        assert result["status"] == "answered" and result["claims"]
        assert all(c["citation"]["document_date"][:10] > dated[0][0][:10] for c in result["claims"])
        repeated = research_company(store, "CCL", QUESTION, context_reference=reference)
        assert repeated["cached"] and repeated["id"] == result["id"]
        latest = max(result["claims"], key=lambda c: c["citation"]["document_date"])
        absent = research_company(
            store,
            "CCL",
            "Is there independently dated later evidence to assess this statement?",
            context_reference={
                "research_id": result["id"],
                "citation_id": latest["citation"]["id"],
                "claim_index": result["claims"].index(latest),
                "intent": "later",
            },
        )
        assert absent["status"] == "insufficient_evidence" and not absent["usage"]
        (OUTPUT / "evidence-followup-mix-real.json").write_text(
            json.dumps({"root": root, "followup": result}, indent=2), encoding="utf-8"
        )
        (OUTPUT / "evidence-no-later-real.json").write_text(
            json.dumps(absent, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "company": "CCL",
                    "later_claims": len(result["claims"]),
                    "independent_documents": result["investigation"]["other_documents_retrieved"],
                    "cache_reused": True,
                    "no_later_model_calls": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
