"""Answers from the sample knowledge base (data/kb.json), in Telugu plus an English gloss."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import DATA_DIR
from .mandi import LivePrices
from .nlu import Intent

GREETING_TE = ("నమస్కారం! నేను రైతు వాణి. పంట ధరలు, పంట సలహాలు, ప్రభుత్వ పథకాల గురించి అడగండి. "
               "ఉదాహరణకు, గుంటూరులో మిర్చి ధర ఎంత అని అడగండి.")
GREETING_EN = ("Hello! I am Rythu Vaani. Ask me about mandi prices, crop advice or schemes, "
               "for example: what is the chilli price in Guntur?")
FALLBACK_TE = "క్షమించండి, సరిగ్గా అర్థం కాలేదు. పంట పేరు చెప్పి, ధర, సలహా లేదా పథకం గురించి మళ్ళీ అడగండి."
FALLBACK_EN = "Sorry, I did not understand. Please say the crop name and ask about price, advice or a scheme."

# Prisma v3.0 context for farmer calls (see KnowledgeBase.stt_context)
STT_SKIP_ALIASES = {"రుణ", "లోనొ"}  # NLU match stems, not words anyone says
STT_EXTRA_KEYTERMS = ["రుణం", "ధర", "రేటు", "మార్కెట్", "క్వింటాలు", "పురుగు", "తెగులు", "ఎరువు", "యూరియా",
                      "విత్తనాలు", "విత్తుకోవాలి", "ఎకరాలు", "కౌలు రైతు", "పథకం", "అర్హత", "క్రాప్ లోన్"]
STT_TOPIC = ("A farmer near Guntur, Andhra Pradesh, calls a Telugu agriculture helpline over a phone line. "
             "They ask about mandi prices for chilli, cotton, paddy, maize or red gram at Guntur, Tenali or "
             "Narasaraopet; about pests, disease, fertilizer or sowing time; or whether they qualify for "
             "crop insurance, seed subsidy or a crop loan, often saying their acreage and whether they are "
             "a tenant farmer.")


@dataclass
class Reply:
    te: str
    en: str


def _inr(n: float) -> str:
    """Indian digit grouping: 14200 -> '14,200', 125000 -> '1,25,000'."""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join([head] + groups + [tail]) if head else ",".join(groups + [tail])


def _dative(name_te: str) -> str:
    """Telugu 'to/for X': పథకం -> పథకానికి (not పథకంకు)."""
    return name_te[:-1] + "ానికి" if name_te.endswith("ం") else name_te + "కు"


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


class KnowledgeBase:
    def __init__(self, data: dict, live_prices: LivePrices | None = None):
        self.data = data
        self.crops = data["crops"]
        self.markets = data["markets"]
        self.schemes = data["schemes"]
        self.live_prices = live_prices

    @classmethod
    def load(cls, path: Path | None = None, live_prices: LivePrices | None = None) -> "KnowledgeBase":
        return cls(json.loads(Path(path or DATA_DIR / "kb.json").read_text(encoding="utf-8")), live_prices)

    def stt_context(self) -> tuple[list[str], str]:
        """Prisma v3.0 hints: Telugu-script crop/market/scheme names plus helpline words, and a topic.

        Only words the helpline actually listens for go in, so a hint can't push the
        transcript toward something the NLU would then misread.
        """
        terms: list[str] = []
        for table in (self.crops, self.markets, self.schemes):
            for entry in table.values():
                terms += [a for a in entry["aliases"] if not a.isascii() and a not in STT_SKIP_ALIASES]
        terms += STT_EXTRA_KEYTERMS
        return list(dict.fromkeys(terms)), STT_TOPIC

    def answer(self, intent: Intent) -> Reply:
        handler = getattr(self, f"_{intent.name}", None)
        return handler(intent.slots) if handler else Reply(FALLBACK_TE, FALLBACK_EN)

    # ---- intents ----

    def _greeting(self, slots) -> Reply:
        return Reply(GREETING_TE, GREETING_EN)

    def _clarify_crop(self, slots) -> Reply:
        c = self.crops[slots["crop"]]
        return Reply(f"{c['te']} గురించి మార్కెట్ ధర కావాలా, పంట సలహా కావాలా?",
                     f"Do you want the market price or crop advice for {c['en']}?")

    def _mandi_price(self, slots) -> Reply:
        if "crop" not in slots:
            return Reply("ఏ పంట ధర కావాలి? ఉదాహరణకు మిర్చి, పత్తి, వరి.",
                         "Which crop's price do you need? For example chilli, cotton, paddy.")
        crop = self.crops[slots["crop"]]
        mkey = slots.get("market", self.data["default_market"])
        market = self.markets[mkey]
        if self.live_prices:
            q = self.live_prices.quote(market["agmarknet"], crop["agmarknet"])
            if q:
                day_te = q.day.strftime("%d-%m-%Y")
                return Reply(
                    f"{market['te']} మార్కెట్‌లో {crop['te']} ధర క్వింటాలుకు {_inr(q.modal)} రూపాయలు. "
                    f"కనిష్ఠ ధర {_inr(q.low)}, గరిష్ఠ ధర {_inr(q.high)} రూపాయలు. ఇది {day_te} నాటి ప్రభుత్వ "
                    "అగ్‌మార్క్‌నెట్ ధర.",
                    f"{crop['en'].capitalize()} at {market['en']} market: ₹{_inr(q.modal)} per quintal "
                    f"(range ₹{_inr(q.low)}-₹{_inr(q.high)}), Agmarknet report of {q.day:%d %b %Y}.",
                )
        now, last_week = self.data["prices"][mkey][slots["crop"]]
        diff = now - last_week
        if diff > 0:
            trend_te, trend_en = f"గత వారం కంటే {_inr(diff)} రూపాయలు పెరిగింది.", f"up ₹{_inr(diff)} from last week"
        elif diff < 0:
            trend_te, trend_en = f"గత వారం కంటే {_inr(-diff)} రూపాయలు తగ్గింది.", f"down ₹{_inr(-diff)} from last week"
        else:
            trend_te, trend_en = "గత వారం ధరలోనే ఉంది.", "unchanged from last week"
        return Reply(
            f"{market['te']} మార్కెట్‌లో {crop['te']} ధర క్వింటాలుకు {_inr(now)} రూపాయలు. {trend_te}",
            f"{crop['en'].capitalize()} at {market['en']} market: ₹{_inr(now)} per quintal, {trend_en}.",
        )

    def _crop_advice(self, slots) -> Reply:
        topic = slots["topic"]
        tmpl = self.data["advice"][topic]
        crop = self.crops.get(slots.get("crop", ""))
        if topic == "sowing":
            if not crop:
                return Reply("ఏ పంట విత్తాలనుకుంటున్నారు? పంట పేరు చెప్పండి.",
                             "Which crop do you want to sow? Please say the crop name.")
            return Reply(tmpl["te"].format(crop=crop["te"], sowing=crop["sowing_te"]),
                         tmpl["en"].format(crop=crop["en"], sowing=crop["sowing_en"]))
        return Reply(tmpl["te"].format(crop=crop["te"] if crop else "మీ"),
                     tmpl["en"].format(crop=crop["en"] if crop else "crop"))

    def _scheme_info(self, slots) -> Reply:
        if "scheme" not in slots:
            names_te = ", ".join(s["te"] for s in self.schemes.values())
            names_en = ", ".join(s["en"] for s in self.schemes.values())
            return Reply(f"నా దగ్గర ఈ పథకాల సమాచారం ఉంది: {names_te}. ఏ పథకం గురించి తెలుసుకోవాలి?",
                         f"I have information on: {names_en}. Which one would you like to know about?")
        s = self.schemes[slots["scheme"]]
        if "acres" not in slots:
            return Reply(
                f"{s['te']}: {s['benefit_te']}. కావలసిన పత్రాలు: {s['docs_te']}. "
                "అర్హత తెలుసుకోవడానికి మీకు ఎన్ని ఎకరాలు ఉన్నాయో, మీరు కౌలు రైతా అని చెప్పండి.",
                f"{s['en']}: {s['benefit_en']}. Documents: {s['docs_en']}. "
                "To check eligibility, tell me your acreage and whether you are a tenant farmer.",
            )
        acres, tenant = slots["acres"], slots.get("tenant", False)
        if tenant and not s["tenant_ok"]:
            reason_te, reason_en = "ఈ పథకం కౌలు రైతులకు వర్తించదు", "this scheme does not cover tenant farmers"
        elif s["max_acres"] is not None and acres > s["max_acres"]:
            reason_te = f"ఈ పథకం {_num(s['max_acres'])} ఎకరాల లోపు ఉన్న రైతులకే"
            reason_en = f"this scheme is only for farmers with up to {_num(s['max_acres'])} acres"
        else:
            return Reply(
                f"{_num(acres)} ఎకరాలతో మీరు {_dative(s['te'])} అర్హులు అయ్యే అవకాశం ఉంది. {s['benefit_te']}. "
                f"కావలసిన పత్రాలు: {s['docs_te']}. దరఖాస్తు కోసం మీ రైతు భరోసా కేంద్రాన్ని సంప్రదించండి.",
                f"With {_num(acres)} acres you are likely eligible for the {s['en']}: {s['benefit_en']}. "
                f"Documents: {s['docs_en']}. Apply at your Rythu Bharosa Kendram.",
            )
        return Reply(
            f"{_num(acres)} ఎకరాలతో మీరు {_dative(s['te'])} అర్హులు కాకపోవచ్చు, ఎందుకంటే {reason_te}. "
            "ఇతర పథకాల గురించి అడగండి.",
            f"With {_num(acres)} acres you may not be eligible: {reason_en}. Ask me about other schemes.",
        )


@lru_cache(maxsize=1)
def default_kb() -> KnowledgeBase:
    """Live Agmarknet prices when DATA_GOV_IN_API_KEY is set, sample prices from the knowledge base otherwise."""
    return KnowledgeBase.load(live_prices=LivePrices.from_env())
