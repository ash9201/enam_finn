import csv
import io
import zipfile

import httpx
import pytest

from finn import price_primary
from finn.briefing import sync_prices


def archive(*, session="2026-10-30", close="1185", series="EQ"):
    row = {
        "TradDt": session,
        "Src": "NSE",
        "Sgmt": "CM",
        "TckrSymb": "INFY",
        "SctySrs": series,
        "ISIN": "INE009A01021",
        "ClsPric": close,
        "PrvsClsgPric": "1146.50",
        "TtlTradgVol": "13030713",
    }
    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as zipped:
        zipped.writestr("bhavcopy.csv", csv_text.getvalue())
    return data.getvalue()


def test_official_bar_validates_date_identifier_and_caches_one_archive(monkeypatch):
    monkeypatch.setattr(price_primary, "_cache", ("", 0, {}))
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, content=archive())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for _ in range(2):
            bar = price_primary.exchange_session_bar(
                client, "2026-10-30", {"symbol": "INFY", "isin": "INE009A01021"}
            )
        with pytest.raises(ValueError, match="symbol/ISIN"):
            price_primary.exchange_session_bar(
                client, "2026-10-30", {"symbol": "INFY", "isin": "wrong"}
            )
    assert len(calls) == 1
    assert bar["session"] == "2026-10-30"
    assert bar["close"] == 1185
    assert bar["volume"] == 13030713
    assert len(bar["archive_sha256"]) == 64


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"session": "2026-10-29"}, "trading date"),
        ({"close": "NaN"}, "no usable"),
        ({"series": "BE"}, "no usable"),
    ],
)
def test_incompatible_official_rows_are_rejected(kwargs, reason):
    with pytest.raises(ValueError, match=reason):
        price_primary.parse_bhavcopy(
            archive(**kwargs), "2026-10-30", "https://nsearchives.nseindia.com/test.zip"
        )


def test_newer_saved_session_is_not_replaced_by_a_freshly_fetched_older_one(monkeypatch):
    old = {
        "symbol": "INFY",
        "data": {"last_session": "2026-10-30", "close": 1185},
        "last_success_at": "2026-10-30T16:00:00+00:00",
    }

    class Store:
        def __init__(self):
            self.saved = []

        def rows(self, table, **kwargs):
            return [old] if table == "finn_price_snapshots" else []

        def upsert(self, table, rows, **kwargs):
            if table == "finn_price_snapshots":
                self.saved.extend(rows)

        def patch(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        "finn.briefing.price_probe", lambda company: {"last_session": "2026-10-29", "close": 1146.5}
    )
    store = Store()
    result = sync_prices(store, [{"symbol": "INFY"}])
    assert result["state"] == "failed"
    assert store.saved[0]["data"] == old["data"]
    assert store.saved[0]["last_success_at"] == old["last_success_at"]
    assert "older trading session" in store.saved[0]["error"]
