# Orange Invest — final minimal OBS read-along (G6)

**Purpose:** A genuine 3–5 minute, continuous current-release recording showing one complete booking and one handled mock-provider failure with **chat and Live activity visible side by side**. No invented results, edited success frames, production provider, payment or measured 100× claim. The extended historical [OBS script](OBS_RECORDING_SCRIPT.md) is preserved but is not the recommended quick take.

## Rehearsal and controls

1. Confirm the app at `http://127.0.0.1:8080/` reports the newly accepted source revision in the release receipt. Sign in **before** recording as an unused synthetic timeout-after-success account (`obs-take1-190158`, `obs-take2-190158`, or `obs-take3-190158`; synthetic password `synthetic-test`). The mock fault and +₹37 hold-quote delta are deliberately configured for this user. If a take has already booked, use another fixture; do not reset databases.
2. Select **Groq · Live**. Wait until the chat workspace is empty. Ensure you capture only the Chrome application window, not Gmail, secrets, passwords or the Word script. Camera OFF, mic ON. Open the one-page Word narration on the same laptop in a separate window. Make a short test recording first.
3. Rehearse the exact prompt below without recording. If Groq is rate-limited, a required field is missing, provider results are absent, or outcome remains unverified, record a truthful failure receipt and stop. Retry only after recovery and with an unused fixture; do not present an offline fallback as live Groq.

### Exact prompt (copy)

```text
Find a plumber in Indiranagar this week, mornings only, under 1800.
```

## Timed continuous narration

**0:00–0:25 — Introduce.** With both panels visible, say:

> I built Orange as a locally running service-booking agent. The real Groq model interprets natural language, while application code—not the model—controls human approval and the booking transaction. This uses mocked providers and a deliberately configured timeout-after-success failure.

**0:25–1:05 — One request.** Paste the prompt and click Send once. Show service=plumber, area=Indiranagar, budget=₹1,800, before noon, provider options, and the truthful verified Groq badge.

> The request contains a service, location, time window and budget. The model proposes a structured plan, then code checks the values. No booking occurs because the AI generated a response.

**1:05–1:35 — Untrusted review.** Click **Read reviews (untrusted)** on a provider, ideally Tech 0-0. Point to the injected instruction; never execute it.

> This provider review contains a prompt-injection attempt. It is third-party data, not an instruction or permission. User intent and approval remain unchanged.

**1:35–2:10 — Exact quote.** Select an available morning slot. Stop at **Review your booking**. Read the **actual** provider, slot and quoted price. The configured hold quote rises ₹37 over the search price.

> The discovery price is provisional. This approval card reflects the actual hold, selected slot and exact price. Nothing has been booked until I approve this precise action.

**2:10–3:15 — Real timeout and readback.** Click **Approve book once**. Wait for authoritative verification; show `book` → provider timeout → `get_booking_status` and final `BOOKED`. Show exactly one appointment. *Only narrate success if visible.*

> The mock provider committed the booking but returned a timeout. Our durable worker checks its authoritative status with the same idempotency key. It does not invent failure or create a second booking.

**3:15–4:15 — Persistence and close.** Refresh, show that the booking persists, and finish with chat/trace side by side.

> The confirmed booking survives refresh. The repository includes outcome-based simulated-user evaluations, approval and idempotency regressions, three actual bug investigations, a raw timeout trace and a two-page design note. This is local synthetic infrastructure, not production HA or demonstrated 100× scale. I would defend separating probabilistic interpretation from deterministic transaction authority. Thank you.

## Failure/stop rules

If Groq omits a required fact, no providers appear, approval vanishes, the simulated timeout does not reconcile, or a status remains unknown, **do not claim success**. Treat the take as a failed test, preserve its trace and start a separate truthful take. The assignment requires a real booking and a handled failure, not a cinematic simulation.

After a successful take: save OBS MP4, watch it end to end for audible microphone, readable chat and trace, correct 3–5 minute duration, complete booking and no secrets. Upload to **unlisted YouTube or Loom**, verify link in a signed-out browser, and only then send the employer email with GitHub plus playable video URL. GitHub's embedded WebM file alone is not the requested hosted video.
