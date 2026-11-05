"""Live mandi prices from Agmarknet, via the Government of India open data API (data.gov.in).

Dataset: "Current Daily Price of Various Commodities from Various Markets (Mandi)"
  GET https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070
      ?api-key=<key>&format=json&limit=<n>&filters[market]=<market>
Each record has state, district, market, commodity, variety, grade, arrival_date (dd/mm/yyyy),
min_price, max_price and modal_price (rupees per quintal).

The dataset only holds the latest reported day, so there is no weekly trend here. A market can
report several varieties of one crop (for chilli: Teja, 334, Byadgi, ...); the quote uses the
median modal price and the overall min-max range across them.

The key is read only from DATA_GOV_IN_API_KEY (.env). Without it, or if the API fails, the
knowledge base falls back to its synthetic demo prices.
"""
from __future__ import annotations

import os
import statistics
import time
from dataclasses import dataclass
from datetime import date, datetime

import httpx

RESOURCE_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
CACHE_TTL_S = 30 * 60


@dataclass
class MandiQuote:
    modal: float
    low: float
    high: float
    day: date
    n_varieties: int
    commodity: str  # the Agmarknet name that matched


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_date(v: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def quote_from_records(records: list[dict], match: list[str]) -> MandiQuote | None:
    """Best quote for one crop from a market's records (latest day only)."""
    rows = []
    for r in records:
        name = str(r.get("commodity", "")).lower()
        modal, d = _to_float(r.get("modal_price")), _to_date(r.get("arrival_date", ""))
        if modal and modal > 0 and d and any(m in name for m in match):
            rows.append((d, modal, _to_float(r.get("min_price")) or modal, _to_float(r.get("max_price")) or modal,
                         r.get("commodity", "")))
    if not rows:
        return None
    latest = max(r[0] for r in rows)
    rows = [r for r in rows if r[0] == latest]
    return MandiQuote(modal=statistics.median(r[1] for r in rows), low=min(r[2] for r in rows),
                      high=max(r[3] for r in rows), day=latest, n_varieties=len(rows), commodity=rows[0][4])


class LivePrices:
    def __init__(self, api_key: str, http: httpx.Client | None = None, clock=time.monotonic):
        self._key = api_key
        self._http = http or httpx.Client(timeout=10)
        self._clock = clock
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    @classmethod
    def from_env(cls) -> "LivePrices | None":
        key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
        return cls(key) if key else None

    def _records(self, market: str) -> list[dict]:
        hit = self._cache.get(market)
        if hit and self._clock() - hit[0] < CACHE_TTL_S:
            return hit[1]
        resp = self._http.get(RESOURCE_URL, params={"api-key": self._key, "format": "json", "limit": 500,
                                                    "filters[market]": market})
        resp.raise_for_status()
        records = resp.json().get("records", []) or []
        self._cache[market] = (self._clock(), records)
        return records

    def quote(self, market: str, match: list[str]) -> MandiQuote | None:
        """None when the market has no report for this crop, or the API is unreachable."""
        try:
            return quote_from_records(self._records(market), match)
        except (httpx.HTTPError, ValueError):
            return None
