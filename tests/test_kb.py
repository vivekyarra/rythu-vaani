from rythu_vaani.kb import KnowledgeBase, _inr, default_kb
from rythu_vaani.nlu import Intent

KB = default_kb()


def ask(name, **slots):
    return KB.answer(Intent(name, slots))


def test_price_uses_kb_values_and_trend():
    now, last = KB.data["prices"]["guntur"]["chilli"]
    r = ask("mandi_price", crop="chilli", market="guntur")
    assert _inr(now) in r.te and "గుంటూరు" in r.te and "మిర్చి" in r.te
    assert ("పెరిగింది" if now > last else "తగ్గింది") in r.te
    assert f"₹{_inr(now)}" in r.en


def test_price_defaults_to_default_market_and_asks_for_crop():
    assert "గుంటూరు" in ask("mandi_price", crop="paddy").te
    assert "ఏ పంట" in ask("mandi_price").te


def test_unchanged_price():
    data = {**KB.data, "prices": {"guntur": {"paddy": [2000, 2000]}}}
    assert "గత వారం ధరలోనే" in KnowledgeBase(data).answer(Intent("mandi_price", {"crop": "paddy"})).te


def test_advice_with_and_without_crop():
    assert "పత్తి" in ask("crop_advice", crop="cotton", topic="pest").te
    assert "మీ పంట" in ask("crop_advice", topic="fertilizer").te
    assert "ఏ పంట" in ask("crop_advice", topic="sowing").te
    assert KB.crops["maize"]["sowing_te"] in ask("crop_advice", crop="maize", topic="sowing").te


def test_scheme_eligibility_rules():
    assert "likely eligible" in ask("scheme_info", scheme="seed_subsidy", acres=3.0).en
    assert "up to 5 acres" in ask("scheme_info", scheme="seed_subsidy", acres=7.0).en
    assert "tenant" in ask("scheme_info", scheme="crop_loan", acres=2.0, tenant=True).en
    assert "likely eligible" in ask("scheme_info", scheme="crop_insurance", acres=50.0, tenant=True).en
    assert "acreage" in ask("scheme_info", scheme="crop_loan").en
    assert "Which one" in ask("scheme_info").en


def test_greeting_and_fallback():
    assert "రైతు వాణి" in ask("greeting").te
    assert "క్షమించండి" in ask("fallback").te


def test_indian_grouping():
    assert [_inr(x) for x in (950, 14200, 125000)] == ["950", "14,200", "1,25,000"]
