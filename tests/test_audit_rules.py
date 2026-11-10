"""Vaani Audit: rules, roles, coaching, LLM guard rails, benchmark matching. All offline (MOCK)."""
import json

import pytest

from vaani_audit import config
from vaani_audit.bench import match_call, prf
from vaani_audit.checklist import CHECKS
from vaani_audit.coaching import REPHRASE, coaching_card, rephrase
from vaani_audit.llm import review, verify
from vaani_audit.roles import assign_roles
from vaani_audit.rules import check_call_hours, norm, run_rules

LENDER = config.lender()["aliases"]
SPAN = {"THREAT", "ABUSE", "SHAMING", "THIRD_PARTY"}


def segs_from(call):
    return [{"start": i * 5.0, "end": i * 5.0 + 4.0, "text": t["text"], "role": t["speaker"],
             "speaker_id": 1 if t["speaker"] == "agent" else 2} for i, t in enumerate(call["turns"])]


def dev_calls():
    return json.loads((config.DATA / "dev_calls.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("call", dev_calls(), ids=lambda c: c["id"])
def test_rules_reproduce_dev_labels_on_script_text(call):
    ag = config.agent(call["agent_id"])
    found = run_rules(segs_from(call), ag["aliases"], LENDER, call["call_time"])
    pred = {(f.category, int(f.start // 5) if f.category in SPAN else None) for f in found}
    gt = {(l["category"], l.get("turn")) for l in call["labels"]}
    assert pred == gt


def test_every_finding_has_timestamp_and_verbatim_quote():
    call = next(c for c in dev_calls() if c["id"] == "hi_d02")
    segs = segs_from(call)
    for f in run_rules(segs, ["अमित"], LENDER, call["call_time"]):
        if f.category == "CALL_HOURS":
            assert "20:15" in f.quote
            continue
        assert any(s["text"] == f.quote and s["start"] == f.start for s in segs)


def test_norm_handles_nukta_zwnj_and_punctuation():
    assert norm("धोखेबाज़!") == norm("धोखेबाज")
    assert norm("ఆఫీసర్‌ని,") == "ఆఫీసర్ని"
    assert norm("Hello,  EMI?") == "hello emi"


@pytest.mark.parametrize("t,bad", [("2026-10-13T07:59:00+05:30", True), ("2026-10-13T08:00:00+05:30", False),
                                   ("2026-10-13T18:59:00+05:30", False), ("2026-10-13T19:00:00+05:30", True)])
def test_call_hours_window(t, bad):
    assert (check_call_hours(t) is not None) == bad


def test_relative_answering_without_disclosure_is_not_third_party():
    segs = [
        {"start": 0, "end": 3, "text": "नमस्ते, मैं नवधन फाइनेंस से अमित बोल रहा हूँ। क्या मनोज जी हैं?", "role": "agent"},
        {"start": 3, "end": 5, "text": "मैं उनकी पत्नी बोल रही हूँ, वो घर पर नहीं हैं।", "role": "borrower"},
        {"start": 5, "end": 8, "text": "कोई बात नहीं, कृपया उनसे कहिए मुझे वापस कॉल कर लें। कोई शिकायत हो तो हेल्पलाइन पर बताइए।", "role": "agent"},
    ]
    cats = {f.category for f in run_rules(segs, ["अमित"], LENDER, None)}
    assert "THIRD_PARTY" not in cats and "NO_DISCLOSURE" not in cats  # purpose waived for a third party


def test_borrower_words_never_trigger_agent_rules():
    segs = [{"start": 0, "end": 3, "text": "मैं नवधन फाइनेंस से अमित बोल रहा हूँ, आपकी EMI के बारे में। शिकायत हो तो हेल्पलाइन।", "role": "agent"},
            {"start": 3, "end": 6, "text": "मैं पुलिस में शिकायत करूँगा, आप धोखेबाज़ हो!", "role": "borrower"}]
    assert run_rules(segs, ["अमित"], LENDER, None) == []


def test_roles_pick_agent_even_if_borrower_speaks_first():
    segs = [{"start": 0, "end": 1, "text": "हैलो?", "speaker_id": 7},
            {"start": 1, "end": 4, "text": "नमस्ते, मैं नवधन फाइनेंस से अमित बोल रहा हूँ, आपकी EMI के बारे में।", "speaker_id": 3},
            {"start": 4, "end": 5, "text": "हाँ बोलिए", "speaker_id": 7}]
    r = assign_roles(segs, ["अमित"], LENDER)
    assert r["agent_speaker"] == 3 and [s["role"] for s in segs] == ["borrower", "agent", "borrower"]


def test_llm_verify_drops_invented_or_misattributed_findings():
    segs = [{"start": 0, "end": 2, "text": "आपके घर पर हमारी टीम भेजेंगे", "role": "agent"},
            {"start": 2, "end": 4, "text": "मैं पुलिस बुला लूँगा", "role": "borrower"}]
    raw = [{"category": "THREAT", "segment": 0, "quote": "हमारी टीम भेजेंगे"},         # kept
           {"category": "THREAT", "segment": 0, "quote": "हम आपको जेल भेजेंगे"},       # not in text -> dropped
           {"category": "THREAT", "segment": 1, "quote": "पुलिस बुला"},                # borrower turn -> dropped
           {"category": "MADE_UP", "segment": 0, "quote": "टीम"},                    # unknown category
           {"category": "ABUSE", "segment": 9, "quote": "x"}, "garbage"]
    kept = verify(raw, segs)
    assert len(kept) == 1 and kept[0].source == "llm" and kept[0].start == 0


def test_llm_review_with_fake_model_and_bad_json():
    segs = [{"start": 1, "end": 2, "text": "तुम बेकार इंसान हो", "role": "agent"}]
    assert review(segs, complete=lambda p: 'Sure: [{"category":"ABUSE","segment":0,"quote":"बेकार इंसान"}]')[0].category == "ABUSE"
    assert review(segs, complete=lambda p: "no json here") == []


def test_rephrasings_exist_for_every_category_and_language():
    for cat in CHECKS:
        for lang in ("hi-IN", "te-IN", "hi-en", "te-en"):
            s = rephrase(cat, lang, "नेहा", "Navdhan Finance", "f")
            assert s and "{" not in s
    assert "बोल रही" in rephrase("NO_DISCLOSURE", "hi-IN", "नेहा", "नवधन फाइनेंस", "f")
    assert set(REPHRASE) == set(CHECKS)


def test_coaching_card_counts_and_examples():
    audits = [{"call_id": "a", "language": "hi-IN", "findings": [{"category": "THREAT", "start": 3.0, "quote": "q"}]},
              {"call_id": "b", "language": "hi-IN", "findings": []}]
    card = coaching_card({"id": "AG-101", "name": "Amit", "gender": "m"}, audits)
    assert card["compliance_rate"] == 0.5 and card["focus"][0]["example"]["start"] == 3.0


def test_match_call_counts_tp_fp_fn_and_ignores_split_duplicates():
    truth = {"turns": [{"start": 0, "end": 3}, {"start": 3.5, "end": 6}, {"start": 6.5, "end": 9}],
             "labels": [{"category": "THREAT", "turn": 1}, {"category": "NO_GRIEVANCE"}]}
    preds = [{"category": "THREAT", "start": 3.6, "end": 4.5}, {"category": "THREAT", "start": 4.6, "end": 5.9},
             {"category": "ABUSE", "start": 20, "end": 21}]
    m = match_call(truth, preds)
    assert m["THREAT"] == {"tp": 1, "fp": 0, "fn": 0}
    assert m["ABUSE"]["fp"] == 1 and m["NO_GRIEVANCE"]["fn"] == 1
    assert prf({"tp": 0, "fp": 0, "fn": 0})["precision"] is None
