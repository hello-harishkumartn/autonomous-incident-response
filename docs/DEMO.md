# 3-Minute Recruiter Demo Script

Two options below: a terminal-only demo (zero setup risk, always works)
and a browser demo (more visually impressive, needs Node too). Do the
terminal one if you're not sure about the room's setup; do both if you
have a projector and 3 minutes is really 4.

## Option A — terminal only (safest, ~90 seconds)

**Say:** "This is an agent that gets paged, investigates a simulated
production incident, and fixes it — with a real approval gate for risky
actions. No API key, no Docker, nothing installed beyond Python."

```bash
scripts/demo.sh
```

While it runs, narrate the timeline as it prints:

- *"It checks fleet health first — it doesn't know what's wrong yet."*
- *"Found payment_service unhealthy — it inspects it, then pulls logs."*
- *"The logs show an exception right after a deploy — it checks
  deployment history to confirm before proposing anything."*
- *(when the approval prompt appears)* **"Here's the part that matters:
  rolling back a deployment is HIGH_RISK, so it stops and asks. This isn't
  a hardcoded rule that happened to fire — the risk level is computed from
  what it's about to do."**
- *"Approved, executed, health-checked, resolved. Five iterations, one
  approval, ground truth matches."*

**Say:** "Ten scenarios like this are scripted and reproducible —
`scripts/demo.sh redis_failure`, `db_connection_exhaustion`, etc. — and
there's a benchmark that runs all of them and scores accuracy, escalation
rate, and cost. That result is committed at
`eval/results/baseline_offline_provider.json`."

## Option B — browser, watch it evolve live (~2.5 minutes)

Setup (do this *before* the room, not during):

```bash
# terminal 1
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload

# terminal 2
cd frontend && npm install && npm run dev
```

Open `http://localhost:3000`.

1. **Inject** — click a scenario card (`redis_failure` is a good pick: it
   forces the approval gate and shows cascading symptoms on two other
   services). You land on the incident page, phase `alerted`.
2. **Start investigation** — check "Auto-approve HIGH_RISK actions" *off*
   the first time (you want to demo the approval panel), click **Start
   investigation**.
3. **Narrate the timeline panel filling in live** (it commits after every
   iteration, so this is real, not a canned animation): health check →
   inspect → logs → diagnostic → hypothesis confirmed.
4. **The approval panel appears** with the proposed action and its
   rationale. Click **Approve & execute** yourself, live. **Say:** "That
   API call is the only thing standing between a plan and it actually
   touching anything."
5. Point at the **service health grid** turning green, and the
   **execution graph** panel showing exactly which phases this run visited.
6. **Say:** "Everything you just watched — decision, evidence, action,
   result — is what's shown. The model's raw reasoning never is."

## If something goes wrong

- **`scripts/demo.sh` fails to find Python**: it needs `python3` or
  `python` on PATH to create the venv the first time; point it at one
  with `PYTHON=/path/to/python3 scripts/demo.sh` — or just run the two
  `pip install` lines from Option B's terminal 1 manually first.
- **Browser shows nothing / CORS error**: confirm the backend is on
  `:8000` and `frontend/.env.local` (copy from `.env.local.example`) has
  `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- **No Gemini key handy**: that's expected and fine — say so. "It's running
  the deterministic offline provider right now; same code path resolves
  against Gemini with `GEMINI_API_KEY` set, Ollama is wired as a free local
  fallback too."

## The 10-second pitch if you only have 10 seconds

"An SRE agent with a real state machine, budgets, a sandboxed executor,
and a human approval gate for anything risky — not a chatbot wearing an
SRE costume."
