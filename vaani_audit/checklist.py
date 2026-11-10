"""The RBI-style collection-call checklist Vaani Audit checks every call against.

Basis (paraphrased; this tool is an aid for compliance teams, not legal advice):
* RBI circular of 12 Aug 2022 on recovery agents (calls only 08:00-19:00; no intimidation or
  harassment, verbal or physical; no humiliating the borrower publicly or intruding on the privacy
  of family members, referees and friends; no threatening or misleading calls),
* the Fair Practices Code for lenders (identify yourself and the lender; respectful conduct;
  a grievance-redressal mechanism the borrower is told about),
* RBI's guidance that borrower information is confidential (no disclosure to third parties).
"""
from __future__ import annotations

from dataclasses import dataclass

CALL_WINDOW = (8, 19)  # 08:00 <= local time < 19:00 IST


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    rule: str
    severity: str  # "critical" | "major"
    kind: str  # "span" (happens at a moment: has a timestamp + quote) | "call" (absence / metadata)


CHECKS: dict[str, Check] = {c.id: c for c in [
    Check("NO_DISCLOSURE", "Identity, lender and purpose stated",
          "Agent states own name, the lender and the purpose (loan/EMI) at the start of the call.",
          "major", "call"),
    Check("CALL_HOURS", "Call within 8 AM - 7 PM",
          "Recovery calls only between 08:00 and 19:00 (borrower's local time).", "major", "call"),
    Check("THREAT", "No threats or intimidation",
          "No threats of police, jail, arrest, seizure, home/office visits or harm.", "critical", "span"),
    Check("ABUSE", "Respectful language",
          "No abusive, insulting or demeaning words.", "critical", "span"),
    Check("SHAMING", "No public shaming",
          "No threat to tell neighbours, relatives, employer, social groups, or to post notices.",
          "critical", "span"),
    Check("THIRD_PARTY", "No disclosure to third parties",
          "Loan details are never shared with anyone other than the borrower.", "critical", "span"),
    Check("NO_GRIEVANCE", "Grievance channel offered",
          "Agent tells the borrower how to raise a complaint (grievance officer/helpline/branch).",
          "major", "call"),
]}

SPAN_CATEGORIES = [c for c, k in CHECKS.items() if k.kind == "span"]
CALL_CATEGORIES = [c for c, k in CHECKS.items() if k.kind == "call"]
AUDIO_CATEGORIES = [c for c in CHECKS if c != "CALL_HOURS"]  # CALL_HOURS comes from metadata only
SEVERITY_PENALTY = {"critical": 25, "major": 10}
