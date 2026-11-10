"""Agent coaching: for every violation, a compliant way to say it, in the call's language.

The rephrasings are fixed, reviewed templates (not generated), so a coach never hears an
unvetted sentence. Gnani Timbre speaks them in the same language as the call.
"""
from __future__ import annotations

from collections import Counter

# {g} -> Hindi verb ending for the agent's gender (रहा / रही); {name}, {lender} substituted.
REPHRASE = {
    "THREAT": {
        "hi": "मैं समझ{sakta} हूँ कि अभी मुश्किल है। आपकी EMI बाकी है। आप आज भुगतान कर सकते हैं, या हम आपके लिए एक आसान भुगतान योजना बना सकते हैं।",
        "te": "మీ ఇబ్బంది నాకు అర్థమైంది. మీ EMI బకాయి ఉంది. ఈ రోజు కట్టవచ్చు, లేదా మీ కోసం ఒక సులభమైన పేమెంట్ ప్లాన్ చేయగలం.",
        "hi-en": "मैं समझ{sakta} हूँ कि अभी मुश्किल है। आपका EMI overdue है। आप आज payment कर सकते हैं, या हम आपके लिए एक easy payment plan बना सकते हैं।",
        "te-en": "మీ problem నాకు అర్థమైంది. మీ EMI overdue ఉంది. ఈ రోజు pay చేయవచ్చు, లేదా మీ కోసం ఒక easy payment plan చేయగలం.",
    },
    "ABUSE": {
        "hi": "मैं आपकी स्थिति समझ{sakta} हूँ। चलिए मिलकर कोई रास्ता निकालते हैं। आप किस तारीख तक भुगतान कर पाएंगे?",
        "te": "మీ పరిస్థితి నాకు అర్థమైంది. కలిసి ఒక దారి చూద్దాం. మీరు ఏ తేదీకి కట్టగలరు?",
        "hi-en": "मैं आपकी situation समझ{sakta} हूँ। चलिए मिलकर कोई solution निकालते हैं। आप किस date तक payment कर पाएंगे?",
        "te-en": "మీ situation నాకు అర్థమైంది. కలిసి ఒక solution చూద్దాం. మీరు ఏ date కి pay చేయగలరు?",
    },
    "SHAMING": {
        "hi": "आपके लोन की जानकारी पूरी तरह गोपनीय है, यह सिर्फ़ आपके और हमारे बीच रहेगी। क्या हम भुगतान की एक तारीख तय कर सकते हैं?",
        "te": "మీ లోన్ వివరాలు పూర్తిగా గోప్యంగా ఉంటాయి, మీకు మాకు మధ్యలోనే ఉంటాయి. కట్టే తేదీ ఒకటి నిర్ణయిద్దామా?",
        "hi-en": "आपके loan की details पूरी तरह confidential हैं, ये सिर्फ़ आपके और हमारे बीच रहेंगी। क्या हम payment की एक date fix कर सकते हैं?",
        "te-en": "మీ loan details పూర్తిగా confidential గా ఉంటాయి, మీకు మాకు మధ్యలోనే. Payment కి ఒక date fix చేద్దామా?",
    },
    "THIRD_PARTY": {
        "hi": "कोई बात नहीं। कृपया उन्हें बताइए कि {lender} से {name} का फोन आया था, और वे इस नंबर पर वापस कॉल कर लें। धन्यवाद।",
        "te": "పర్వాలేదు అండి. {lender} నుండి {name} ఫోన్ చేశారని, ఈ నంబర్‌కి తిరిగి కాల్ చేయమని దయచేసి చెప్పండి. ధన్యవాదాలు.",
        "hi-en": "कोई बात नहीं। Please उन्हें बता दीजिए कि {lender} से {name} का call आया था, और वे इस number पर call back कर लें। Thank you.",
        "te-en": "పర్వాలేదు అండి. {lender} నుండి {name} call చేశారని, ఈ number కి call back చేయమని please చెప్పండి. Thank you.",
    },
    "NO_DISCLOSURE": {
        "hi": "नमस्ते, मैं {lender} से {name} बोल {raha} हूँ। मैं आपके लोन की EMI के बारे में कॉल कर {raha} हूँ।",
        "te": "నమస్కారం, నేను {lender} నుండి {name} మాట్లాడుతున్నాను. మీ లోన్ EMI గురించి కాల్ చేస్తున్నాను.",
        "hi-en": "Hello, मैं {lender} से {name} बोल {raha} हूँ। मैं आपके loan के EMI के बारे में call कर {raha} हूँ।",
        "te-en": "Hello, నేను {lender} నుండి {name} మాట్లాడుతున్నాను. మీ loan EMI గురించి call చేస్తున్నాను.",
    },
    "NO_GRIEVANCE": {
        "hi": "अगर आपको कोई शिकायत हो, तो आप हमारे शिकायत अधिकारी से संपर्क कर सकते हैं। हेल्पलाइन नंबर आपके लोन एग्रीमेंट में दिया है।",
        "te": "మీకు ఏదైనా ఫిర్యాదు ఉంటే, మా గ్రీవెన్స్ ఆఫీసర్‌ని సంప్రదించవచ్చు. హెల్ప్‌లైన్ నంబర్ మీ లోన్ అగ్రిమెంట్‌లో ఉంది.",
        "hi-en": "अगर आपकी कोई complaint हो, तो आप हमारे grievance officer से contact कर सकते हैं। Helpline number आपके loan agreement में है।",
        "te-en": "మీకు ఏదైనా complaint ఉంటే, మా grievance officer ని contact చేయవచ్చు. Helpline number మీ loan agreement లో ఉంది.",
    },
    "CALL_HOURS": {
        "hi": "ग्राहकों को सिर्फ़ सुबह आठ बजे से शाम सात बजे के बीच ही कॉल करें।",
        "te": "కస్టమర్లకు ఉదయం ఎనిమిది నుండి సాయంత్రం ఏడు గంటల మధ్యలోనే కాల్ చేయండి.",
        "hi-en": "Customers को सिर्फ़ morning आठ बजे से evening सात बजे के बीच ही call करें।",
        "te-en": "Customers కి morning ఎనిమిది నుండి evening ఏడు గంటల మధ్యలోనే call చేయండి.",
    },
}

TIP_EN = {
    "THREAT": "Replace threats with options: today's payment, or a payment plan.",
    "ABUSE": "Stay respectful; acknowledge the situation and ask for a date.",
    "SHAMING": "Never mention neighbours, family, employer or groups; promise confidentiality.",
    "THIRD_PARTY": "If someone else answers, leave only your name and lender and ask for a call-back.",
    "NO_DISCLOSURE": "Open every call with your name, the lender and the purpose.",
    "NO_GRIEVANCE": "Before ending, tell the borrower how to raise a complaint.",
    "CALL_HOURS": "Dial only between 8 AM and 7 PM.",
}

TTS_LANG = {"hi": "hi-IN", "hi-en": "hi-IN", "te": "te-IN", "te-en": "te-IN"}


def lang_key(language: str) -> str:
    return {"hi-IN": "hi", "te-IN": "te", "hi-en": "hi-en", "te-en": "te-en"}.get(language, "hi")


def rephrase(category: str, language: str, agent_name: str, lender: str, gender: str = "m") -> str:
    tpl = REPHRASE[category][lang_key(language)]
    return tpl.format(name=agent_name, lender=lender, raha="रहा" if gender == "m" else "रही",
                      sakta="ता" if gender == "m" else "ती")


def coaching_card(agent: dict, audits: list[dict]) -> dict:
    """Summarise one agent's audited calls into a coaching card."""
    counts = Counter(f["category"] for a in audits for f in a["findings"])
    calls = len(audits)
    compliant = sum(1 for a in audits if not a["findings"])
    focus = []
    for cat, n in counts.most_common(3):
        example = next(((a, f) for a in audits for f in a["findings"] if f["category"] == cat), None)
        a, f = example
        focus.append({
            "category": cat, "count": n, "tip": TIP_EN[cat],
            "example": {"call_id": a["call_id"], "start": f["start"], "quote": f["quote"]},
            "rephrase": rephrase(cat, a["language"], agent["name"], a.get("lender", "Navdhan Finance"),
                                 agent.get("gender", "m")),
            "language": a["language"],
        })
    return {"agent_id": agent["id"], "name": agent["name"], "calls": calls, "compliant_calls": compliant,
            "compliance_rate": round(compliant / calls, 3) if calls else None, "focus": focus}
