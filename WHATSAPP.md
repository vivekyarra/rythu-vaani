# WhatsApp setup: farmers send a voice note, Rythu Vaani replies with a voice note

How it works: the farmer records a Telugu voice note in WhatsApp → Meta sends it to
`/whatsapp/webhook` → Prisma v3.0 transcribes the OGG Opus file as it is → the helpline finds the
answer → Timbre speaks it as OGG Opus → the farmer gets a text (what was heard + the answer) and a
voice reply. Typed questions work too.

The code is done and tested (`tests/test_whatsapp.py`, plus a run against the real Gnani API with
Meta faked). The steps below need your own Facebook account, so only you can do them.
They take about 30 minutes.

## 1. Create the Meta app (about 10 minutes)

1. Go to https://developers.facebook.com → **My Apps** → **Create App**.
2. Pick the use case **Connect with customers through WhatsApp** (or app type **Business**), and finish.
3. In the app, open **WhatsApp → API Setup**. Meta gives you a free **test phone number**.
4. Copy two values from that page:
   - **Temporary access token** → `WHATSAPP_TOKEN` (expires after 24 hours; see step 5)
   - **Phone number ID** (not the phone number itself) → `WHATSAPP_PHONE_NUMBER_ID`
5. Under **To**, add your own WhatsApp number (and up to 4 more people, for example a farmer for the
   demo). Each number gets a code on WhatsApp to confirm. The test number can only message these
   numbers.
6. Open **App settings → Basic**, click **Show** next to **App secret** → `WHATSAPP_APP_SECRET`.
7. Make up any long random string → `WHATSAPP_VERIFY_TOKEN`.

Put all four in `.env` (it is gitignored). Never paste them anywhere else.

## 2. Start the server and a public tunnel (about 5 minutes)

Meta must reach your laptop over HTTPS. Cloudflare's quick tunnel needs no account:

```bash
winget install Cloudflare.cloudflared
```

Terminal 1:

```bash
uvicorn rythu_vaani.api:app --port 8000
```

Terminal 2:

```bash
cloudflared tunnel --url http://localhost:8000
```

It prints a URL like `https://something-random.trycloudflare.com`. That URL changes every time you
restart cloudflared, so repeat step 3 after each restart.

## 3. Connect the webhook (about 5 minutes)

1. In the Meta app: **WhatsApp → Configuration → Webhook → Edit**.
2. Callback URL: `https://<your-tunnel>/whatsapp/webhook`
3. Verify token: the same `WHATSAPP_VERIFY_TOKEN` as in `.env`. Click **Verify and save**.
   (The server answers Meta's check. If it fails, look at the uvicorn terminal.)
4. Under **Webhook fields**, click **Subscribe** next to **messages**.

## 4. Test it

From your WhatsApp, send the test number a voice note: *"గుంటూరులో మిర్చి ధర ఎంత?"*.
Within a few seconds you get:
- a blue double tick (the bot marked it as read),
- a text: `🎤 మీరు అడిగింది: ...`, the Telugu answer, and an English line in italics,
- a voice note in Timbre's Telugu voice.

If nothing comes back, check the uvicorn terminal. `401` means the app secret doesn't match.
`HTTP 401` from graph.facebook.com means the 24-hour token expired: copy a new one from API Setup.

## Notes

- The 24-hour token is enough to record the demo. For a token that lasts, create a System User in
  Meta Business Settings and generate a permanent token with the `whatsapp_business_messaging` permission.
- Every webhook is checked with Meta's `X-Hub-Signature-256` signature. Unsigned or wrongly signed
  requests are rejected with 401.
- Meta sometimes delivers the same message twice. The bot answers each message ID only once.
- Voice notes longer than 30 seconds exceed Prisma's REST limit. The bot then asks the farmer, in
  Telugu, to ask again in under 30 seconds.
- Without a Gnani key the bot replies with text marked MOCK MODE and never sends beeps as a voice note.
