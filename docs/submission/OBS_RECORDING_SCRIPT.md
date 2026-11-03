# Orange Invest OBS recording script

Record one continuous walkthrough lasting about **4 minutes 35 seconds**. Show the application chat and Live activity pane together. The main story is a real request, a corrected quote, explicit approval, a provider timeout and verified recovery. Memory and cancellation demonstrate that the same safeguards continue after booking.

This script targets the accepted local release **ac1493e**. The exact initial prompt below passed a live Groq browser preflight on 3 November 2026. That is one successful sample, not a guarantee that every model response will be correct.

## Before recording

1. Open **http://127.0.0.1:8080/** in a browser. Maximise the window and keep the layout wide enough to show chat on the left and Live activity on the right. Do not record a mobile-width layout.
2. In OBS, capture this browser window and your microphone. A readable 1080p recording at 30 fps is sufficient; verify a short test recording has clear text and audible narration. Keep the script on another screen or printed paper.
3. Record to MKV and remux the finished recording to MP4 if needed. OBS recommends MKV because an interrupted recording can otherwise be lost; its recording guide documents automatic remuxing. [Official OBS recording guidance](https://obsproject.com/kb/standard-recording-output-guide).
4. Keep `.env`, terminals containing configuration, personal email and unrelated tabs outside the captured window. The application never needs the Groq key typed into the browser.
5. Use one fresh account from the table. These are deliberately public, synthetic local-demo credentials. Existing alice/bob workflows have not been reset.

| Take | Username | Password |
| --- | --- | --- |
| First take | `obs-take1-190158` | `synthetic-test` |
| Second take | `obs-take2-190158` | `synthetic-test` |
| Third take | `obs-take3-190158` | `synthetic-test` |

Each account uses the test-admin-configured **timeout_after_success** branch and a **37 INR quote increase**. This intentionally makes the mock provider commit a booking and then time out. Say this on camera. It does not change the provider's normal specified probability distribution or give chat control over fault injection.

Log in before starting OBS. Stop at the empty workspace, select **Groq · Live**, and leave the message box empty. On a new take, sign out and use the next fresh account; reloading a completed workflow does not reset it.

## Copy these messages

**Initial request**

```text
Find a plumber in Indiranagar this week, mornings only, under 1800.
```

**One fact correction**

```text
Change only my budget to under 1900. Keep the service, area, week and morning limit unchanged.
```

Use the application's actual responses. Read the displayed provider, date and amount rather than assuming the values in an earlier screenshot.

## Timed walkthrough and spoken script

### 0:00 to 0:20 Introduce the product and the controlled failure

**Do:** Start recording on the empty workspace. Keep both panels visible. Point briefly to the mode selector and Live activity pane.

**Say:**

> I'm Ashish. This is my local home-service agent for Orange Invest. Groq interprets the conversation, while code controls approval and booking. For this demonstration, I configured the mock provider to commit a booking and then return a timeout, so we can watch recovery happen in the real interface.

### 0:20 to 0:50 Submit a constrained request

**Do:** Paste the initial request and click **Send** once. Wait for provider cards. Point to the current plan and verified model badge. Briefly leave the interface idle while speaking so the Send button can be seen remaining usable during background polling.

**Say:**

> I need a plumber in Indiranagar, this week, mornings only, under eighteen hundred rupees. The current plan retains those constraints. The badge identifies the actual verified Groq response. Model output is a proposed plan; it has not authorised a booking.

**Check:** The plan shows plumber, Indiranagar, budget 1800 and latest hour 12. Providers are visible. If the response asks for clarification, follow the guidance at the end; do not narrate missing fields as if they were present.

### 0:50 to 1:10 Show the injection boundary

**Do:** On a provider card, click **Read reviews (untrusted)**. Point to the malicious instruction in the review. Do not follow it or paste it into chat.

**Say:**

> This provider review contains an instruction-injection attempt. The application labels and renders it as untrusted data. Reviews do not become user instructions, grant approval or enter the remote intent extractor's context. I still control the next action.

### 1:10 to 1:35 Show the exact quote before permission

**Do:** Click one available morning slot. Stop on **Review your booking**. Point to provider, new slot, price and quote-change notice. Do not click Approve yet.

**Say:**

> Search price is only discovery information. This card shows the actual hold quote, the selected provider and slot, and a revision-bound approval. In this fixture the quote rises by thirty-seven rupees. Nothing has been booked yet.

**Read actual values:** If the screen shows search 900 and hold 937, say those amounts. If it shows another pair, read that pair. Never recite a price that is not visible.

### 1:35 to 2:00 Correct one fact and replace the old approval

**Do:** Paste the budget correction and click **Send**. Wait for the old approval card to disappear and providers to return. Check service, area, week and morning limit are retained. Select a newly available slot and pause on the new approval card.

**Say:**

> I am changing only the budget to nineteen hundred. The other constraints remain. The old approval is invalidated, and I must review a fresh card. An earlier confirmation cannot authorise this new revision.

### 2:00 to 2:40 Approve once and show timeout recovery

**Do:** Read the new card, then click **Approve book** once. Keep chat and trace visible while the operation runs. Wait for **BOOKED**. Scroll within the Live activity pane if needed to show **book · provider timeout** followed by **get_booking_status** and verified completion. Scroll the main page enough to show the single appointment row.

**Say:**

> I approve this exact action now. The provider has committed, but its response times out. The application treats the outcome as unverified and checks authoritative booking status. It does not create a new booking request. Only after readback does it report BOOKED, and there is one appointment in the provider records.

**Important:** If the screen is still pending, describe it as pending and wait. Do not click Approve again. A timeout alone proves neither success nor failure.

### 2:40 to 2:55 Demonstrate durable reconnect

**Do:** Reload the page once. Wait for **BOOKED** and the same single appointment. Do not start a new request.

**Say:**

> Reloading reconnects to the persisted workflow and operation. The same booking returns; browser state is not the booking authority.

The selector can return to **Scripted · Offline** after reload. This honestly indicates the mode for a future message; it does not change the completed Groq request or provider booking. Do not describe an offline badge as live Groq verification.

### 2:55 to 3:30 Demonstrate user controlled memory

**Do:** In **Your preferences**, leave **Area** selected. Enter `Indiranagar` and click **Remember**. Click **Correct**, replace the value with `Koramangala`, and click **Remember**. Then click **Forget**. Pause on **Forgotten**.

**Say:**

> Stable preferences are separate from booking truth. I can explicitly save an area, correct it and forget it. Memory is user-scoped and versioned. Forget suppresses the operational value; the retained tombstone cannot restore it to future context. I am not claiming forensic erasure of database pages or backups.

### 3:30 to 4:05 Demonstrate a new approval for cancellation

**Do:** Scroll to **Your appointments**. Click **Cancel appointment**. Pause on **Review cancellation**. Point to the exact action, provider and current slot. Click **Approve cancel** once. Wait for **CANCELLED** and the appointment's cancelled status. The fixture's first cancellation call returns a transient 503; recovery may be quick, so show the trace after completion rather than inventing a long outage.

**Say:**

> Cancellation needs its own approval. The original booking consent does not carry forward. The mock's first cancel call has a transient failure; bounded recovery uses the same operation and verifies provider state. The final status is now CANCELLED.

### 4:05 to 4:35 Close with the evidence and limits

**Do:** Keep the final status and trace on screen. If time allows, show the public repository's submission index in a pre-opened second browser tab for the last ten seconds. Do not spend time scrolling through raw test logs.

**Say:**

> The repository includes the two-page design note, generated evaluation table, three observed bugs with regression evidence, and an annotated raw timeout trace. The release passed sixty-five original tests, thirty-nine distributed checks, twenty-eight offline end-to-end scenarios, twenty model-adapter checks and five additional security tests. Everything here uses local mock providers. The hundred-times scaling section is a design plan, not a measured performance claim. The central guarantee is separate approval, one logical effect and truthful recovery.

**Do:** Stop recording. Aim for **3:00 to 5:00**, preferably around **4:35**. If actions run faster, pause on the evidence rather than adding unrelated features.

## If a response differs during rehearsal

| What you see | What to do |
| --- | --- |
| Model unavailable or unverified | Say so accurately. For a reproducible assignment demo, visibly select **Scripted · Offline** and repeat the request. State that the workflow portion uses the offline interpreter; the repository contains separate real Groq smoke evidence. Never label this fallback as a live Groq result. |
| A missing-field question | Supply only the requested field, then verify all previously accepted constraints remain. If it repeats a fact already in the displayed plan, record the limitation honestly and investigate before treating that take as a clean demonstration. |
| No available slots | Check that you used a fresh account and the exact supported area/service. Do not alter SQL, reset shared data or pretend a provider exists. Use the next fresh account before starting a new take. |
| slot_taken or FAILED | Read the actual reason. A failed operation is not a booking. The prepared accounts use a timeout-after-success fixture, so check the signed-in username before a new take. Do not repeatedly approve the same failed card. |
| Pending or OUTCOME UNKNOWN | Wait and use **Reconnect / refresh** on the same request. Narrate uncertainty until provider readback is verified. |
| Approve card expired | Obtain a fresh quote and approval. Do not claim the old card remains valid. |
| More than five minutes | Make a new continuous take with the next fresh account. Omit memory or cancellation if needed; retain full booking, exact approval, handled failure and side-by-side trace. |

## Optional reschedule segment

Only add this if the recording will stay below five minutes. Before cancellation, choose a genuinely available future slot for the same provider, enter it in the appointment's date/time field, click **Reschedule**, review the new card, then **Approve reschedule**. Wait for **RESCHEDULED** and the changed appointment time. Do not guess an unsupported timestamp or bypass the new approval.

## Finish and share

Play back the complete file. Confirm readable chat and trace, audible narration, actual approval, BOOKED, a visible handled failure, correct duration, and no private material. Upload the final take to Loom or **unlisted YouTube** and open the link in a signed-out/private browser window to verify playback. YouTube documents that an unlisted video is viewable by people with its link without requiring a Google account. [Official YouTube visibility guidance](https://support.google.com/youtube/answer/157177).

Suggested title: **Orange Invest Founding AI Engineer Assignment Ashish Sharma**.

Send the final hosted link back for inclusion in the submission index and prepared employer email. Public GitHub access alone does not satisfy the recorded-demo delivery requirement, and this script is not proof that a recording or email has been delivered.
