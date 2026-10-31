import pytest

from rythu_vaani.kb import default_kb
from rythu_vaani.nlu import normalize_text, parse

KB = default_kb()


@pytest.mark.parametrize("text, intent, slots", [
    ("గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత?", "mandi_price", {"crop": "chilli", "market": "guntur"}),
    ("తెనాలి మార్కెట్‌లో కాటన్ రేటు ఎంత", "mandi_price", {"crop": "cotton", "market": "tenali"}),
    ("Tenali lo cotton rate entha", "mandi_price", {"crop": "cotton", "market": "tenali"}),
    ("వరి ధర", "mandi_price", {"crop": "paddy"}),
    ("నరసరావుపేటలో కందులు", "mandi_price", {"crop": "redgram", "market": "narasaraopet"}),
    ("పత్తికి పురుగు పట్టింది ఏం చేయాలి", "crop_advice", {"crop": "cotton", "topic": "pest"}),
    ("mirchi ki tegulu vachindi", "crop_advice", {"crop": "chilli", "topic": "disease"}),
    ("వరి పంటకు యూరియా ఎప్పుడు వేయాలి", "crop_advice", {"crop": "paddy", "topic": "fertilizer"}),
    ("మొక్కజొన్న ఎప్పుడు విత్తుకోవాలి", "crop_advice", {"crop": "maize", "topic": "sowing"}),
    ("నాకు 3 ఎకరాలు ఉన్నాయి, విత్తన సబ్సిడీకి అర్హుడినా?", "scheme_info", {"scheme": "seed_subsidy", "acres": 3.0}),
    ("నాకు మూడు ఎకరాలు ఉన్నాయి విత్తన సబ్సిడీ", "scheme_info", {"scheme": "seed_subsidy", "acres": 3.0}),
    ("నేను కౌలు రైతుని రెండు ఎకరాలు పంట లోన్ వస్తుందా", "scheme_info",
     {"scheme": "crop_loan", "acres": 2.0, "tenant": True}),
    ("కౌలు రైతుని కాదు 2.5 ఎకరాలు loan", "scheme_info", {"scheme": "crop_loan", "acres": 2.5, "tenant": False}),
    ("౪ ఎకరాలు బీమా", "scheme_info", {"scheme": "crop_insurance", "acres": 4.0}),
    ("ప్రభుత్వ పథకాలు ఏమున్నాయి", "scheme_info", {}),
    ("మిర్చి", "clarify_crop", {"crop": "chilli"}),
    ("నమస్కారం", "greeting", {}),
    ("ఈ రోజు సినిమా ఏది", "fallback", {}),
    ("", "fallback", {}),
])
def test_parse(text, intent, slots):
    got = parse(text, KB)
    assert (got.name, got.slots) == (intent, slots)


def test_benchmark_sentences_all_understood():
    import json

    from rythu_vaani.config import DATA_DIR

    sentences = json.loads((DATA_DIR / "benchmark_sentences.json").read_text(encoding="utf-8"))["sentences"]
    assert all(parse(s, KB).name not in ("fallback", "clarify_crop") for s in sentences)


def test_number_without_acre_word_is_not_acreage():
    assert "acres" not in parse("బీమా పథకం 2024", KB).slots


def test_normalize_keeps_telugu_vowel_signs_and_strips_punctuation():
    assert normalize_text("మిర్చి ధర, ఎంత?!") == "మిర్చి ధర ఎంత"
    assert normalize_text("Rate 2.5 acres.") == "rate 2.5 acres"
