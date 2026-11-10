"""Deterministic compliance rules over a diarized, role-labelled transcript.

Every finding carries the timestamp of the segment it came from and the exact transcript text of
that segment as evidence (``quote``) plus the phrase that triggered the rule (``matched``).
Call-level findings (something *missing*) point at the opening / closing agent turn instead.

Lexicons cover Hindi (Devanagari), Telugu script and romanised/English words, because Prisma
writes code-mixed speech with English words in Latin script (e.g. "सुरक्षा finance").
They were written from domain knowledge and tuned ONLY on the dev set (data/audit/dev_calls.json).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime

from .checklist import CALL_WINDOW, CHECKS

# ---------------------------------------------------------------- normalisation

_ZW = dict.fromkeys(map(ord, "‌‍​﻿"), None)
_PUNCT = re.compile(r"[।॥.,!?;:\"'“”‘’()\[\]{}<>…\-–—/]+")


def norm(text: str) -> str:
    """Lower-case, drop zero-width joiners, nukta and chandrabindu differences, punctuation."""
    t = unicodedata.normalize("NFC", text).translate(_ZW).lower()
    t = unicodedata.normalize("NFD", t).replace("़", "")  # Devanagari nukta: ज़ -> ज
    t = unicodedata.normalize("NFC", t).replace("ँ", "ं")  # chandrabindu -> anusvara
    t = _PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def _rx(*patterns: str) -> re.Pattern:
    def light(p: str) -> str:  # same normalisation as norm() minus punctuation (regex syntax)
        p = unicodedata.normalize("NFC", p).translate(_ZW).lower()
        p = unicodedata.normalize("NFD", p).replace("़", "")
        return unicodedata.normalize("NFC", p).replace("ँ", "ं")
    return re.compile("|".join(f"(?:{light(p)})" for p in patterns))


# ---------------------------------------------------------------- lexicons

DEBT = _rx(
    r"emi", r"ई ?एम ?आई", r"किस्त", r"बकाया", r"लोन", r"\bloan", r"कर्ज", r"उधार", r"रुपये", r"रुपए",
    r"rupees?", r"overdue", r"ओवरड्यू", r"pending", r"पेंडिंग", r"बाकी", r"\bdue\b", r"ड्यू",
    r"payment", r"पेमेंट", r"भुगतान", r"डिफॉल्ट", r"default", r"हजार",
    r"ఈ ?ఎం ?ఐ", r"లోన్", r"బకాయి", r"బాకీ", r"అప్పు", r"రూపాయ", r"వేల", r"కట్టలేదు", r"కట్టాలి",
    r"కట్టండి", r"పెండింగ్", r"ఓవర్ ?డ్యూ", r"పేమెంట్", r"వాయిదా", r"డ్యూ", r"ఇన్‌?స్టాల్‌?మెంట్",
)

THREAT = _rx(
    # police / jail / arrest / legal-criminal intimidation
    r"पुलिस", r"जेल", r"गिरफ्तार", r"अरेस्ट", r"वारंट", r"एफ ?आई ?आर", r"हवालात", r"हथकड़ी",
    r"\b(?:police|jail|arrest\w*|warrant|fir|seize|seizure)\b",
    r"(?:केस|मुकदमा|case)\s*(?:कर|दर्ज|ठोक|डाल|फाइल|file)", r"कोर्ट\s*(?:में|तक)\s*घसीट",
    r"పోలీ?సు?", r"జైలు", r"అరెస్ట", r"వారెంట", r"కేసు\s*(?:పెడ|వేస|ఫైల్|బుక్)", r"కోర్టు\S*\s*ఈడ్చ",
    # coming to home / office / sending people
    r"(?:आपके|आपकी|तुम्हारे|तेरे|उनके)\s*(?:घर|ऑफिस|दफ्तर|office|दुकान|गांव)\s*(?:पर|पे|में|तक)?\s*(?:आ|पहुंच)",
    r"(?:आदमी|लोग|बंदे|टीम|team|रिकवरी\s*वाले|एजेंट)\s*(?:भेज|आ\s*जाएंगे|आएंगे|घर)",
    r"(?:మీ|నీ)\s*(?:ఇంటి|ఇంటికి|ఇంట్లో|ఆఫీసు|ఆఫీస్|office|షాప్|దుకాణ|ఊరికి)\S*\s*(?:కి|కు|దగ్గరకు|దగ్గరికి)?\s*(?:వచ్చి|వస్తా|వస్తాం|వస్తారు|వస్తాము)",
    r"(?:మనుషుల|మనుషులు|మనుషుల్ని|టీమ్|team|ఏజెంట్)\S*\s*(?:వచ్చి|వస్తా|పంప)",
    r"\b(?:ghar|office)\s*(?:pe|par)?\s*(?:aa|aayenge|aakar)\b",
    # seizing property
    r"(?:उठा|उठवा)\s*(?:लेंगे|ले\s*जाएंगे|लें|लेगी|ले\s*जाएगी)", r"जब्त", r"सीज", r"कुर्क",
    r"లాక్కె", r"లాక్కు", r"జప్తు", r"సీజ్", r"ఎత్తుకెళ్", r"తీసుకెళ్ళిపోతా",
    # harm / menace
    r"देख\s*लेंगे", r"अंजाम", r"छोड़ेंगे\s*नहीं", r"नहीं\s*छोड़ेंगे", r"हाथ\s*पैर", r"बुरा\s*(?:होगा|हाल)",
    r"सबक\s*सिखा", r"చూసుకుంటా", r"వదిలిపెట్ట", r"వదలం", r"అంతు\s*చూస్", r"బుద్ధి\s*చెప్తా",
)

ABUSE = _rx(
    r"बेशर्म", r"बेईमान", r"धोखेबाज", r"फ्रॉड", r"चोर", r"झूठे", r"झूठा", r"निकम्म", r"नालायक", r"कमीन",
    r"बेवकूफ", r"गधे", r"गधा", r"भिखारी", r"भिखमंग", r"शर्म\s*(?:नहीं|आनी|करो|आती)", r"दो\s*कौड़ी",
    r"घटिया", r"हरामी", r"पागल", r"जाहिल", r"गंवार", r"औकात", r"बेकार\s*आदमी", r"चीटर",
    r"అబద్ధాలకోరు", r"అబద్ధాల\s*కోరు", r"మోసగా", r"మోసగత్తె", r"దొంగ", r"సిగ్గు\s*(?:లేదా|లేని|లేకుండా|ఉండాలి|లేదు)",
    r"పనికిమాలిన", r"వెధవ", r"బుద్ధి\s*(?:లేదా|లేని|లేదు)", r"మూర్ఖ", r"దరిద్ర", r"బిచ్చగా", r"చీటర్",
    r"ఫ్రాడ్", r"యూజ్‌?లెస్", r"పిచ్చి", r"అడుక్కు", r"నీ\s*స్థాయి", r"నీచ",
    r"\b(?:cheat|cheater|cheaters|fraud|useless|idiot|stupid|liar|shameless|nonsense|bloody|duffer|rascal|loser|beggar)\b",
)

SHAME_AUDIENCE = _rx(
    r"मोहल्ल", r"पड़ोस", r"पडोस", r"रिश्तेदार", r"सबको", r"सब\s*को", r"सबके", r"समाज", r"गांव", r"बिरादरी",
    r"ऑफिस\s*वाल", r"बॉस", r"एचआर", r"कलीग", r"मालिक", r"कंपनी\s*में", r"स्कूल", r"प्रिंसिपल",
    r"व्हाट्स\s*एप", r"वॉट्स\s*ऐप", r"वाट्स\s*एप", r"ग्रुप", r"फेसबुक", r"सोशल\s*मीडिया",
    r"ఊరి", r"ఊర్లో", r"ఊరంతా", r"గ్రామ", r"ఇరుగు\s*పొరుగు", r"పక్కింటి", r"పక్కవాళ్ళ", r"బంధువు", r"చుట్టా",
    r"అందరికీ", r"అందరికి", r"అందరూ", r"బాస్", r"మేనేజర్", r"హెచ్\s*ఆర్", r"స్కూల్", r"ప్రిన్సిపాల్",
    r"వాట్సాప్", r"వాట్స్\s*యాప్", r"గ్రూప్", r"ఫేస్‌?బుక్", r"కాలనీ", r"ఆఫీసులో",
    r"\b(?:whatsapp|group|facebook|social media|neighbou?rs?|relatives?|boss|hr|employer|colleagues?|society|colony|principal|school|manager)\b",
)
SHAME_EXPOSE = _rx(
    r"बता", r"बोल\s*दे", r"पता\s*चल", r"फैला", r"डाल\s*दे", r"डालेंगे", r"पोस्ट", r"लगा\s*दे", r"लगाएंगे",
    r"चिपका", r"फोटो", r"भेज\s*दे", r"भेजेंगे", r"खबर", r"लेटर", r"चिट्ठी", r"सामने",
    r"చెప్తా", r"చెబుతా", r"చెప్పేస్తా", r"చెప్పిస్తా", r"తెలిసేలా", r"తెలియజేస్త", r"తెలుస్తుంది", r"పెడతా",
    r"పెట్టేస్తా", r"పోస్ట్", r"ఫోటో", r"పంపిస్తా", r"పంపుతా", r"లెటర్", r"ఉత్తరం", r"నోటీసు", r"అతికి", r"రాస్తా",
    r"\b(?:tell|inform|post|letter|photo|notice|bata\w*|bol denge)\b",
)
SHAME_STRONG = _rx(
    r"बदनाम", r"इज्जत\s*(?:उतार|मिट्टी|नीलाम)", r"पोस्टर", r"नोटिस\s*(?:चिपका|लगा)", r"सबके\s*सामने",
    r"मुंह\s*दिखाने", r"పరువు\s*(?:తీ|పో|తీస్తా)", r"పోస్టర్", r"అందరి\s*ముందు", r"\bposters?\b",
)
CONFIDENTIAL = _rx(
    r"किसी\s*को\s*(?:नहीं|भी\s*नहीं)", r"किसी\s*से\s*नहीं", r"confidential", r"गोपनीय",
    r"ఎవరికీ\s*(?:చెప్ప|తెలియ)", r"గోప్యం", r"గోప్యంగా",
)

THIRD_PARTY_MARKER = _rx(
    r"मैं\s*(?:उनकी|उनका|उनके|इनकी|इनका)", r"(?:उनकी|उनका|उनके)\s*(?:पत्नी|वाइफ|भाई|बहन|बेटा|बेटी|मां|पिता|पापा|दोस्त|पति|सहकर्मी|कलीग)",
    r"(?:वो|वह|वे)\s*(?:अभी\s*)?(?:घर\s*पर\s*)?(?:नहीं\s*है|बाहर|ऑफिस|मीटिंग|सो\s*रहे)", r"घर\s*पर\s*नहीं",
    r"నేను\s*(?:ఆయన|ఆమె|వాళ్ళ|వాడి|అతని|ఆవిడ)", r"(?:ఆయన|ఆమె|వాళ్ళ|అతని|వాడి)\s*(?:భార్య|భర్త|అన్న|తమ్ము|అక్క|చెల్లె|చెల్లి|అమ్మ|నాన్న|కొడుకు|కూతురు|కొలీగ్|ఫ్రెండ్|స్నేహితు)",
    r"(?:ఇంట్లో|ఇక్కడ)\s*(?:లేరు|లేడు|లేదు|లేరండి)", r"(?:ఆఫీసుకు|బయటకు|బయటికి|ఊరికి|పనికి)\s*వెళ్ళ", r"మీటింగ్",
    r"\b(?:his|her)\s+(?:wife|husband|brother|sister|colleague|friend|son|daughter|mother|father)\b",
    r"\bcolleague\b", r"\bnot at home\b", r"\bmeeting\b",
)
HANDOVER = _rx(
    r"फोन\s*(?:देता|देती|दे\s*रहा|दे\s*रही)", r"बात\s*(?:कराता|कराती|करवाता|करवाती)", r"बुलाता", r"बुलाती",
    r"(?:मैं|हां\s*मैं)\s*\S+\s*(?:ही\s*)?बोल\s*(?:रहा|रही)", r"ఫోన్\s*ఇస్త", r"ఫోన్\s*ఇస్తున్నా", r"పిలుస్తా",
    r"నేనే\s*\S+", r"\bgiving (?:him|her) the phone\b", r"\bphone\s*de\s*(?:raha|rahi|deta|deti)\b",
)

SELF_INTRO = _rx(
    r"मेरा\s*नाम\s*\S+", r"मैं\s+(?:\S+\s+){0,5}?(?!से\b)\S+\s+बोल\s*(?:रहा|रही)",
    r"నా\s*పేరు\s*\S+", r"\bmy name is\b", r"\bthis is \w+", r"\bmain \w+ bol",
)
GRIEVANCE_STRONG = _rx(
    r"शिकायत", r"ग्रीवेंस", r"grievance", r"complaint", r"कंप्लेंट", r"कम्प्लेंट", r"लोकपाल", r"ombudsman",
    r"नोडल", r"nodal", r"ఫిర్యాదు", r"గ్రీవెన్", r"కంప్లైంట్", r"కంప్లెయింట్", r"అంబుడ్స్",
)
GRIEVANCE_WEAK = _rx(r"हेल्पलाइन", r"helpline", r"कस्टमर\s*केयर", r"customer\s*(?:care|support)", r"ब्रांच",
                     r"branch", r"హెల్ప్\s*లైన్", r"కస్టమర్\s*కేర్", r"బ్రాంచ్")
GRIEVANCE_COND = _rx(r"अगर", r"कोई", r"problem", r"समस्या", r"परेशानी", r"issue", r"ఏదైనా", r"ఉంటే", r"సమస్య",
                     r"\bif\b", r"\bany\b")
GRIEVANCE_DISCOURAGE = _rx(r"शिकायत\s*(?:करने|करके)\s*से\s*कुछ\s*नहीं", r"complaint\s*(?:karne|kar ke)\s*se\s*kuch",
                           r"ఫిర్యాదు\s*చేసినా\s*(?:ఏమీ|ఏం)")

# the stock grievance sentence ("... in your loan agreement") is not a disclosure of the debt
LOAN_AGREEMENT = _rx(r"(?:loan|लोन)\s*(?:agreement|एग्रीमेंट)", r"(?:loan|లోన్)\s*(?:agreement|అగ్రిమెంట్)")

OPENING_AGENT_TURNS = 3


# ---------------------------------------------------------------- findings

@dataclass
class Finding:
    category: str
    start: float
    end: float
    quote: str
    matched: str = ""
    note: str = ""
    source: str = "rule"  # "rule" | "llm"

    @property
    def title(self) -> str:
        return CHECKS[self.category].title

    @property
    def severity(self) -> str:
        return CHECKS[self.category].severity

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(title=self.title, severity=self.severity)
        return d


def _find(rx: re.Pattern, text: str) -> str:
    m = rx.search(text)
    return m.group(0).strip() if m else ""


def _has_alias(text_n: str, aliases: list[str]) -> str:
    squashed = text_n.replace(" ", "")
    for a in aliases:
        a_n = norm(a)
        if a_n and (a_n in text_n or a_n.replace(" ", "") in squashed):
            return a
    return ""


def check_call_hours(call_time: str | None) -> Finding | None:
    if not call_time:
        return None
    t = datetime.fromisoformat(call_time)
    lo, hi = CALL_WINDOW
    if lo <= t.hour < hi:
        return None
    return Finding("CALL_HOURS", 0.0, 0.0, quote=f"call metadata: started {t.strftime('%H:%M')} IST",
                   matched=t.strftime("%H:%M"), note=f"allowed window {lo:02d}:00-{hi:02d}:00")


def run_rules(segments: list[dict], agent_aliases: list[str], lender_aliases: list[str],
              call_time: str | None = None) -> list[Finding]:
    """``segments``: time-ordered dicts with start, end, text, role ('agent' | 'borrower')."""
    findings: list[Finding] = []
    third_party, handed_over = False, False
    window: list[dict] = []          # agent turns that count as "the opening"
    agent_turns_since_reset = 0

    for seg in segments:
        text_n = norm(seg["text"])
        if seg.get("role") != "agent":
            if THIRD_PARTY_MARKER.search(text_n) and not handed_over:
                third_party = True
            elif third_party and HANDOVER.search(text_n):
                third_party, handed_over, agent_turns_since_reset = False, True, 0
            continue

        agent_turns_since_reset += 1
        if agent_turns_since_reset <= OPENING_AGENT_TURNS:
            window.append(seg)

        def add(cat, rx_or_match, note=""):
            m = rx_or_match if isinstance(rx_or_match, str) else _find(rx_or_match, text_n)
            if m:
                findings.append(Finding(cat, seg["start"], seg["end"], seg["text"], m, note))
                return True
            return False

        add("THREAT", THREAT)
        add("ABUSE", ABUSE)
        if not CONFIDENTIAL.search(text_n):
            strong = _find(SHAME_STRONG, text_n)
            aud, exp = _find(SHAME_AUDIENCE, text_n), _find(SHAME_EXPOSE, text_n)
            if strong:
                add("SHAMING", strong)
            elif aud and exp:
                add("SHAMING", f"{aud} … {exp}")
        if third_party:
            add("THIRD_PARTY", _find(DEBT, LOAN_AGREEMENT.sub(" ", text_n)),
                "someone other than the borrower is on the line")

    # ---- opening disclosure (call level)
    agent_segs = [s for s in segments if s.get("role") == "agent"]
    if agent_segs:
        win_n = " ".join(norm(s["text"]) for s in window)
        name = _has_alias(win_n, agent_aliases) or (_find(SELF_INTRO, win_n) if not agent_aliases else "")
        lender = _has_alias(win_n, lender_aliases)
        purpose = _find(DEBT, win_n)
        purpose_waived = third_party and not handed_over
        missing = [k for k, ok in (("agent name", name), ("lender", lender),
                                   ("purpose", purpose or purpose_waived)) if not ok]
        if missing:
            first = window[0] if window else agent_segs[0]
            findings.append(Finding("NO_DISCLOSURE", first["start"], first["end"], first["text"],
                                    note="missing in opening: " + ", ".join(missing)))

        # ---- grievance channel (call level)
        offered = ""
        for s in agent_segs:
            t = norm(s["text"])
            if GRIEVANCE_DISCOURAGE.search(t):
                continue
            offered = _find(GRIEVANCE_STRONG, t) or (
                _find(GRIEVANCE_WEAK, t) if GRIEVANCE_COND.search(t) else "")
            if offered:
                break
        if not offered:
            last = agent_segs[-1]
            findings.append(Finding("NO_GRIEVANCE", last["start"], last["end"], last["text"],
                                    note="no grievance/complaint channel offered by the agent"))

    ch = check_call_hours(call_time)
    if ch:
        findings.append(ch)
    return findings
