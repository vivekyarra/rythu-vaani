"""Deterministic intent + slot parser for Telugu, romanised Telugu and Telugu-English code-mix.

Prisma transcribes `te-IN` speech in Telugu script, so English loan words usually arrive
transliterated ("రేటు", "లోన్", "మార్కెట్"). Cue lists therefore cover Telugu script, the
transliterated English forms and plain Latin text (for typed or romanised input).

Matching is by token *prefix* so that inflected forms match their stem
("గుంటూరులో" -> "గుంటూరు", "పత్తికి" -> "పత్తి").
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

PRICE_CUES = ["ధర", "రేటు", "రేట్", "ప్రైస్", "మార్కెట్", "మండి", "price", "rate", "market", "mandi", "dhara"]
SCHEME_CUES = ["పథకం", "పథకా", "స్కీమ్", "స్కీం", "అర్హత", "అర్హు", "scheme", "yojana", "eligib", "arhata"]
ADVICE_TOPICS = {
    "pest": ["పురుగు", "పెస్ట్", "దోమ", "pest", "insect", "purugu"],
    # "తెగిలి": Prisma's rendering of తెగులు on a 5 dB phone line in the benchmark
    "disease": ["తెగులు", "తెగుళ్ళు", "తెగిలి", "వ్యాధి", "రోగం", "disease", "tegulu"],
    "fertilizer": ["ఎరువు", "ఫెర్టిలైజర్", "యూరియా", "fertili", "urea", "eruvu"],
    "sowing": ["విత్త", "నాటు", "sow", "seed", "vittan"],
}
GREETING_CUES = ["నమస్కారం", "నమస్తే", "హలో", "సహాయం", "hello", "hi", "namaskaram", "namaste", "help"]
TENANT_CUES = ["కౌలు", "tenant", "koulu", "kaulu"]
NEGATION_CUES = ["కాదు", "కాను", "not", "kaadu", "kaanu"]
ACRE_CUES =["ఎకర", "ఎకరా", "acre", "ekar"]

NUMBER_WORDS = {
    "అర": 0.5, "ఒక": 1, "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "అయిదు": 5,
    "ఆరు": 6, "ఏడు": 7, "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10, "పన్నెండు": 12, "పదిహేను": 15,
    "ఇరవై": 20, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "half": 0.5,
}
TELUGU_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789")

# Spoken Telugu fuses a number with ఎకరం/ఎకరాలు (sandhi): రెండు + ఎకరాలు -> రెండెకరాలు.
# The fused token is "<number stem> + ె + కర...", so match the stem before "ెకర".
FUSED_ACRE = "ెకర"
FUSED_ACRE_STEMS = {
    "అర": 0.5, "ఒక": 1, "రెండ": 2, "మూడ": 3, "నాలుగ": 4, "ఐద": 5, "అయిద": 5, "ఆర": 6,
    "ఏడ": 7, "ఎనిమిద": 8, "తొమ్మిద": 9, "పద": 10, "పన్నెండ": 12, "పదిహేన": 15, "ఇరవ": 20,
}


def normalize_text(s: str) -> str:
    """NFC, lowercase, drop ZWJ/ZWNJ, replace punctuation/symbols with spaces.

    Uses Unicode categories rather than a ``\\w`` regex, which would strip Telugu
    vowel signs (category Mn/Mc).
    """
    s = unicodedata.normalize("NFC", s).lower().replace("‌", "").replace("‍", "")
    s = "".join(" " if unicodedata.category(c)[0] in "PS" and c != "." else c for c in s)
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)  # keep decimal points only
    return " ".join(s.split())


def tokenize(s: str) -> list[str]:
    return normalize_text(s).translate(TELUGU_DIGITS).split()


def _hits(tokens: list[str], cues: list[str]) -> list[str]:
    return [c for c in cues if any(t.startswith(c) for t in tokens)]


def _find_entity(tokens: list[str], table: dict) -> str | None:
    """Key of the first entity (by position in the utterance) whose alias prefixes a token."""
    for tok in tokens:
        for key, entry in table.items():
            if any(tok.startswith(a.lower()) for a in entry["aliases"]):
                return key
    return None


def _fused_acres(tokens: list[str]) -> float | None:
    for tok in tokens:
        stem, sep, _ = tok.partition(FUSED_ACRE)
        if sep and stem in FUSED_ACRE_STEMS:
            return float(FUSED_ACRE_STEMS[stem])
    return None


def _find_number(tokens: list[str]) -> float | None:
    fused = _fused_acres(tokens)
    if fused is not None:
        return fused
    for tok in tokens:
        m = re.match(r"\d+(\.\d+)?", tok)
        if m:
            return float(m.group())
        if tok in NUMBER_WORDS:
            return float(NUMBER_WORDS[tok])
    return None


@dataclass
class Intent:
    name: str  # mandi_price | crop_advice | scheme_info | clarify_crop | greeting | fallback
    slots: dict = field(default_factory=dict)
    cues: list[str] = field(default_factory=list)


def parse(text: str, kb) -> Intent:
    tokens = tokenize(text)
    crop = _find_entity(tokens, kb.crops)
    market = _find_entity(tokens, kb.markets)
    scheme = _find_entity(tokens, kb.schemes)
    slots = {k: v for k, v in {"crop": crop, "market": market}.items() if v}

    scheme_hits = _hits(tokens, SCHEME_CUES)
    # Acreage or tenant status only matters for eligibility, so treat it as a scheme question
    # even when noise has swallowed the scheme name (the reply then asks which scheme).
    eligibility_hint = bool(_hits(tokens, TENANT_CUES)) or (
        not crop and (_hits(tokens, ACRE_CUES) or _fused_acres(tokens) is not None))
    if scheme or scheme_hits or eligibility_hint:
        if scheme:
            slots["scheme"] = scheme
        if _hits(tokens, ACRE_CUES) or _fused_acres(tokens) is not None:
            acres = _find_number(tokens)
            if acres is not None:
                slots["acres"] = acres
        if _hits(tokens, TENANT_CUES):
            slots["tenant"] = not _hits(tokens, NEGATION_CUES)
        return Intent("scheme_info", slots, scheme_hits)

    for topic, cues in ADVICE_TOPICS.items():
        hits = _hits(tokens, cues)
        if hits:
            return Intent("crop_advice", {**slots, "topic": topic}, hits)

    price_hits = _hits(tokens, PRICE_CUES)
    if price_hits or (market and crop):
        return Intent("mandi_price", slots, price_hits)
    if crop:
        return Intent("clarify_crop", slots)
    if _hits(tokens, GREETING_CUES):
        return Intent("greeting")
    return Intent("fallback")
