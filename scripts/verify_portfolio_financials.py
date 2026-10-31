"""Live, generic portfolio coverage audit. --publish is explicit; no seeded financial data."""

import argparse
import json
import time
from pathlib import Path

from finn.config import load_local_env
from finn.financials import analyse_results
from finn.store import open_store
from finn.timing import tracing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Recheck original sources; saved image reads are reused by PDF hash.",
    )
    args = parser.parse_args()
    load_local_env()
    output = Path("artifacts/experience-audit")
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "portfolio-improved-coverage.json"
    summary = (
        json.loads(summary_path.read_text(encoding="utf-8"))
        if args.symbols and summary_path.exists()
        else []
    )
    with open_store() as store:
        symbols = args.symbols or [
            c["symbol"]
            for c in store.rows(
                "finn_companies", portfolio="eq.true", select="symbol", order="symbol"
            )
        ]
        for symbol in symbols:
            started = time.perf_counter()
            try:
                with tracing() as trace:
                    result = analyse_results(
                        store,
                        symbol,
                        publish=args.publish,
                        refresh=args.refresh,
                        progress=lambda stage: (
                            print(symbol, stage, flush=True)
                            if stage.startswith("visual:")
                            else None
                        ),
                    )
                financial = result["financial_results"]
                row = {
                    "symbol": symbol,
                    "status": result["status"],
                    "seconds": round(time.perf_counter() - started, 2),
                    "cached": result["cached"],
                    "facts": len(result["claims"]),
                    "quarters": financial["periods"],
                    "bases": {
                        basis: {
                            r["metric"]: {
                                "figures": {k: f["value"] for k, f in r["figures"].items()},
                                "qoq": r["qoq"],
                                "yoy": r["yoy"],
                            }
                            for r in view["rows"]
                        }
                        for basis, view in financial["bases"].items()
                    },
                    "withheld": financial["rejected_cells"],
                    "timings": trace.summary(),
                }
                (output / (symbol + "-improved-results.json")).write_text(
                    json.dumps(result, indent=2), encoding="utf-8"
                )
            except Exception as exc:
                row = {
                    "symbol": symbol,
                    "status": "failed",
                    "error": str(exc),
                    "seconds": round(time.perf_counter() - started, 2),
                }
            summary = [r for r in summary if r["symbol"] != symbol] + [row]
            (output / "portfolio-improved-coverage.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            print(json.dumps({k: v for k, v in row.items() if k != "bases"}), flush=True)


if __name__ == "__main__":
    main()
