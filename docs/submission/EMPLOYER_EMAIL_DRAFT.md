# Employer email draft - do not send until the two links are usable

To: hr@orangeinvest.app

Subject: Founding AI Engineer assignment - Ashish Sharma

Dear Orange Invest team,

I am sharing my Founding AI Engineer assignment after the requested deadline. I understand if the review window has closed, and would appreciate your consideration if late submissions are still being reviewed.

The application runs locally against the assignment's fixed mock-provider contract. It supports booking, rescheduling and cancellation, with separate exact-quote approval and verified provider readback. A live Groq `openai/gpt-oss-20b` adapter interprets requests; deterministic code retains action authority.

- Repository: https://github.com/ashish198684/orange-invest-founding-ai-assignment
- 3-5 minute demo: **INSERT VERIFIED LOOM OR UNLISTED YOUTUBE URL**
- Two-page design note: https://github.com/ashish198684/orange-invest-founding-ai-assignment/blob/main/docs/submission/ARCHITECTURE_DESIGN_NOTE.pdf
- Generated evaluation table: https://github.com/ashish198684/orange-invest-founding-ai-assignment/blob/main/artifacts/evals/results.csv
- Three real bugs and fixes: https://github.com/ashish198684/orange-invest-founding-ai-assignment/blob/main/docs/submission/THREE_BUGS.md
- Raw timeout trace and annotation: https://github.com/ashish198684/orange-invest-founding-ai-assignment/blob/main/docs/submission/TIMEOUT_TRACE_ANNOTATION.md

The accepted release passed 65 original regressions, 39 distributed checks, 28 offline end-to-end evaluations, 20 Groq adapter tests and five additional security/trace tests. The browser tests cover code-enforced approval, timeout-after-success recovery and the polling defect found during live review. The repository retains both failing and passing evidence.

The design note distinguishes the proposed 100x scaling plan from measured local behavior. Providers and payments are simulated; no production availability or general model-reliability claim is made.

Thank you for your time,

Ashish Sharma

---

Delivery preparation only. Before sending: replace the video placeholder with an actually playable link and verify the recipient can access the repository and its linked files. Public repository visibility has been sponsor-authorised and applied. No email has been sent by preparing this file.
