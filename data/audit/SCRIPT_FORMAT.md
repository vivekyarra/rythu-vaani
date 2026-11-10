# Synthetic call script format (Vaani Audit)

Every call in `dev_calls.json` / `heldout_calls.json` is **synthetic**: fictional lender, fictional
people, no real phone numbers, account numbers or IDs. Lender name is always the fictional
**"Navdhan Finance"**.

```json
{
  "id": "hi_h01",
  "split": "heldout",                 // "dev" (used to write/tune rules) or "heldout" (never used for tuning)
  "language": "hi-IN",                // hi-IN | te-IN | hi-en (Hinglish) | te-en (Telugu-English mix)
  "agent_id": "AG-103",               // one of AG-101 .. AG-105 (see below)
  "call_time": "2026-10-14T18:40:00+05:30",  // IST, ISO 8601
  "summary": "one line, English: what happens in the call",
  "turns": [
    {"speaker": "agent",    "text": "...", "style": "calm"},
    {"speaker": "borrower", "text": "...", "style": "calm"}
  ],
  "labels": [
    {"category": "THREAT", "turn": 4},        // span categories point at the 0-based turn index
    {"category": "NO_GRIEVANCE"}              // call-level categories have no turn
  ]
}
```

`style` is `calm` or `angry` (angry agent turns are voiced with Timbre's `<shouting>` tag).
`speaker` is `agent` or `borrower` (a relative/third party who picks up is also `borrower` side,
the second voice).

Write turn text in the natural script: Devanagari for Hindi, Telugu script for Telugu. For
code-mixed calls write English words in Latin script inside the Hindi/Telugu sentence, the way
people actually speak ("aapka EMI overdue hai" may also be fully romanized for hi-en).

## Categories (the checklist)

Span categories (label the turn where it happens; an agent turn):

| category | meaning |
|---|---|
| `THREAT` | threat or intimidation: police, jail, arrest, seizing property, "we will come to your house/office", physical harm, fake legal threats |
| `ABUSE` | abusive, insulting or demeaning language at the borrower ("shameless", "fraud", "liar", curses) |
| `SHAMING` | threat to publicly shame: telling neighbours, relatives, employer, society, WhatsApp groups, putting up notices |
| `THIRD_PARTY` | the agent discloses the loan/debt/amount/overdue status to someone who is NOT the borrower (spouse, sibling, colleague who answered the phone) |

Call-level categories (no turn):

| category | meaning |
|---|---|
| `NO_DISCLOSURE` | the agent does NOT identify themself by name AND the lender AND the purpose (loan/EMI payment) near the start of the call. Missing any one of the three = violation |
| `NO_GRIEVANCE` | the agent never offers a grievance / complaint channel (grievance officer, helpline, complaint email, branch) before the call ends |
| `CALL_HOURS` | call_time outside 08:00-19:00 IST (label it whenever call_time is outside the window) |

A compliant call has an empty `labels` list. A call may carry several labels.

Agents (synthetic): AG-101 Amit (hi), AG-102 Rohit (hi/hi-en), AG-103 Kiran (te/te-en),
AG-104 Suresh (te), AG-105 Neha (hi-en, female).
