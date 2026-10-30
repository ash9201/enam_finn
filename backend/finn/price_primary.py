"""Recover an incomplete daily bar from NSE's dated official UDiFF bhavcopy."""

from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import math
from threading import Lock
import time
import zipfile

_cache: tuple[str, float, dict] = ("", 0, {})
_lock = Lock()


def parse_bhavcopy(data: bytes, session: str, source_url: str) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = archive.infolist()
        if len(files) != 1 or not files[0].filename.lower().endswith(".csv"):
            raise ValueError("Unexpected NSE daily archive structure.")
        if files[0].file_size > 30 * 1024 * 1024:
            raise ValueError("NSE daily CSV exceeds the processing bound.")
        with archive.open(files[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
            required = {
                "TradDt",
                "Src",
                "Sgmt",
                "TckrSymb",
                "SctySrs",
                "ISIN",
                "ClsPric",
                "PrvsClsgPric",
                "TtlTradgVol",
            }
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("NSE daily CSV fields changed; no price was inferred.")
            rows = {}
            for row in reader:
                if row["SctySrs"] != "EQ" or row["Sgmt"] != "CM" or row["Src"] != "NSE":
                    continue
                if row["TradDt"] != session:
                    raise ValueError(
                        "NSE archive trading date does not match the requested session."
                    )
                try:
                    close, previous = float(row["ClsPric"]), float(row["PrvsClsgPric"])
                    volume = int(row["TtlTradgVol"])
                except ValueError:
                    continue
                if not all(math.isfinite(v) and v > 0 for v in [close, previous]) or volume < 0:
                    continue
                symbol = row["TckrSymb"]
                if symbol in rows:
                    raise ValueError(
                        "Duplicate NSE EQ series record; price provenance is ambiguous."
                    )
                rows[symbol] = {
                    "session": session,
                    "close": close,
                    "previous_close": previous,
                    "volume": volume,
                    "isin": row["ISIN"],
                    "source_url": source_url,
                    "archive_sha256": digest,
                }
    if not rows:
        raise ValueError("NSE daily archive contained no usable EQ records.")
    return rows


def exchange_session_bar(client, session: str, company: dict) -> dict:
    global _cache
    day = date.fromisoformat(session)
    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
    with _lock:
        if _cache[0] != session or time.monotonic() - _cache[1] > 1800:
            buffer = bytearray()
            with client.stream("GET", url) as response:
                if response.is_error:
                    raise ValueError(
                        f"NSE daily archive returned HTTP {response.status_code}; incomplete Yahoo bar was not replaced."
                    )
                for piece in response.iter_bytes():
                    buffer.extend(piece)
                    if len(buffer) > 5 * 1024 * 1024:
                        raise ValueError("NSE daily archive exceeds the download bound.")
            rows = parse_bhavcopy(bytes(buffer), session, url)
            # Only one date is kept: bounded memory and one archive fetch per batch.
            _cache = (session, time.monotonic(), rows)
        bar = _cache[2].get(company["symbol"])
        if not bar or (company.get("isin") and bar["isin"] != company["isin"]):
            raise ValueError("NSE EQ symbol/ISIN did not match; no price was inferred.")
        return dict(bar)
