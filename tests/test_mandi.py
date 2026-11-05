from datetime import date

import httpx

from rythu_vaani.kb import KnowledgeBase
from rythu_vaani.mandi import RESOURCE_URL, LivePrices, quote_from_records
from rythu_vaani.nlu import Intent


def rec(commodity, modal, lo, hi, day="02/11/2026", variety="Other", market="Guntur"):
    return {"state": "Andhra Pradesh", "district": "Guntur", "market": market, "commodity": commodity,
            "variety": variety, "grade": "FAQ", "arrival_date": day,
            "min_price": str(lo), "max_price": str(hi), "modal_price": str(modal)}


GUNTUR = [
    rec("Dry Chillies", 15500, 13000, 17000, variety="Teja"),
    rec("Dry Chillies", 14000, 12000, 15000, variety="334"),
    rec("Dry Chillies", 16500, 15000, 18500, variety="Byadgi"),
    rec("Dry Chillies", 9000, 8000, 9500, day="01/11/2026"),  # older day: ignored
    rec("Cotton", 7200, 7000, 7400),
    rec("Maize", 0, 0, 0),  # no real price
]


def test_quote_uses_latest_day_median_and_range():
    q = quote_from_records(GUNTUR, ["chilli", "chillies"])
    assert (q.modal, q.low, q.high, q.day, q.n_varieties) == (15500, 12000, 18500, date(2026, 11, 2), 3)


def test_quote_missing_or_zero_prices():
    assert quote_from_records(GUNTUR, ["paddy"]) is None
    assert quote_from_records(GUNTUR, ["maize"]) is None


class Api:
    def __init__(self, records=GUNTUR, status=200):
        self.records, self.status, self.calls = records, status, []

    def __call__(self, request: httpx.Request):
        self.calls.append(request)
        assert str(request.url).startswith(RESOURCE_URL)
        return httpx.Response(self.status, json={"records": self.records})


def live(api, clock=lambda: 0.0):
    return LivePrices("KEY", http=httpx.Client(transport=httpx.MockTransport(api)), clock=clock)


def test_live_prices_query_and_cache():
    api, t = Api(), [0.0]
    lp = live(api, clock=lambda: t[0])
    assert lp.quote("Guntur", ["cotton"]).modal == 7200
    q = api.calls[0].url.params
    assert q["api-key"] == "KEY" and q["filters[market]"] == "Guntur" and q["format"] == "json"
    lp.quote("Guntur", ["chilli"])
    assert len(api.calls) == 1  # cached
    t[0] = 31 * 60
    lp.quote("Guntur", ["chilli"])
    assert len(api.calls) == 2  # cache expired


def test_api_failure_returns_none():
    assert live(Api(status=429)).quote("Guntur", ["cotton"]) is None


def test_kb_reply_uses_live_price_then_falls_back():
    kb = KnowledgeBase.load(live_prices=live(Api()))
    r = kb.answer(Intent("mandi_price", {"crop": "chilli", "market": "guntur"}))
    assert "15,500" in r.te and "అగ్‌మార్క్‌నెట్" in r.te and "02-11-2026" in r.te
    assert "Agmarknet" in r.en and "12,000" in r.en and "18,500" in r.en
    fallback = kb.answer(Intent("mandi_price", {"crop": "paddy", "market": "guntur"}))
    assert "అగ్‌మార్క్‌నెట్" not in fallback.te and "రూపాయలు" in fallback.te  # synthetic demo price
