"""Synthetic caller questions (Timbre voice Lavanya), so the demo uses no real person's voice."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from rythu_vaani.config import get_client, is_mock_mode
assert not is_mock_mode(), "need a real key"
out = pathlib.Path(__file__).resolve().parent
Q = {
  "q1_price": "గుంటూరు మార్కెట్‌లో మిర్చి ధర ఎంత?",
  "q2_loan": "కౌలు రైతుని, రెండు ఎకరాలు, crop loan వస్తుందా?",
  "q3_pest": "పత్తికి పురుగు పట్టింది, ఏం చేయాలి?",
}
c = get_client()
for k, t in Q.items():
    wav = c.synthesize(t, sample_rate=16000, voice="Lavanya")
    (out / f"{k}.wav").write_bytes(wav)
    print(k, len(wav))
json.dump(Q, open(out / "questions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
