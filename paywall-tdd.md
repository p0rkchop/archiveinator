# Paywall TDD Protocol

This file governs autonomous test-driven development of paywall bypass methods.
Claude reads it at the start of every TDD session to know how to operate.

---

## Session Startup Checklist

1. Create a new git branch: `tdd/session-YYYY-MM-DD` (append `-2`, `-3` if date already exists)
2. Check for `RESUME.md` in the repo root
   - If present: read it and restore session state
   - If absent: start fresh — begin with the first paywall type group (Piano)
3. Run `uv run pytest tests/ -m "not e2e and not real_url" -q` to confirm baseline is green before touching anything

---

## Site Selection Order

Work through **all sites of one paywall type** before moving to the next type.
Within a type, work in the order sites appear in `tests/qa/sites.yaml`.
Skip any site that is already passing or marked `xfail: true`.

**Type ordering (easiest → hardest):**
1. `piano` — TinyPass/Piano SDK; most common, high leverage
2. `soft` / `metered` — word-count, regwall, soft registration walls
3. `cloudflare` — Cloudflare bot challenge
4. `perimeter-x` — PerimeterX bot challenge
5. `hard` — opaque hard paywalls; archive fallback most relevant

---

## The TDD Loop (per site)

```
PICK a site from the current type group that hasn't passed this session
│
├── RUN: uv run pytest tests/qa/test_real_urls.py -m real_url -k "<name>" -v
│     → Confirm it's failing; read QAResult failure_reasons
│
├── INSPECT: read archiveinator/steps/ code relevant to the failure reason
│     e.g. paywall.py for detection issues, cli.py for bypass loop issues
│
├── IMPLEMENT a change (new CSS selector, header, detection rule, strategy tweak)
│
├── RUN: uv run pytest tests/ -m "not e2e and not real_url" -q  (unit + mock_paywall)
│     → REGRESSION? git revert, add regression test, redesign, loop back to IMPLEMENT
│
├── RUN: uv run pytest tests/qa/test_real_urls.py -m real_url -k "<name>" -v
│     → PASS: commit → open PR → move to next site
│     → FAIL: increment attempt counter
│           attempt < 3: loop back to INSPECT with new hypothesis
│           attempt == 3: record site as intractable in RESUME.md → move to next site
```

**Never retry the exact same code change.** Each attempt must test a distinct hypothesis.

---

## Pass Criterion

A site **passes** when `QAResult` reports all of the following (see `tests/qa/reporter.py`):
- Archive file exists with **no `_partial` suffix** in the filename
- **Word count ≥ 300** words in the saved HTML
- **No paywall/bot-challenge DOM selectors** remain in the saved HTML
- **Page title** does not match bot-challenge patterns ("just a moment", "are you a robot", etc.)

Do not invent alternative pass criteria. Trust the reporter.

---

## Commit & PR Conventions

**After each site passes:**
```bash
git commit -m "fix(paywall): bypass <paywall_type> for <site_name>

What failed: <one line>
What was tried: <one line per failed attempt, if any>
What worked: <one line>
"
```

**Open a PR immediately after the commit:**
- Title: `fix(paywall): bypass <paywall_type> paywall (<site_name>)`
- Body: include failure reasons, approaches tried, passing test output (last 20 lines)
- Do NOT batch multiple sites into one PR — one PR per passing site

---

## Regression Handling

If a new change causes a **previously passing site to regress**:
1. `git revert <commit>` — revert the breaking change immediately
2. Add a unit test or mock_paywall test that reproduces the regression
3. Redesign the approach so **both** the new site and the regressed site pass
4. Only commit the redesigned code once both pass their tests

Do not use conditional logic as a first resort. Find the root cause.

---

## RESUME.md Format

Update `RESUME.md` at the end of every session (or when approaching token limits).
Use this exact format:

```markdown
# TDD Resume State
updated: YYYY-MM-DD HH:MM UTC
session_branch: tdd/session-YYYY-MM-DD
current_paywall_type: piano
sites_passed_this_session:
  - site_name_1
sites_intractable_this_session:
  - site_name: reason all 3 attempts failed
sites_in_progress:
  - site_name: attempt 2/3, last_failure: "word count 87, paywall selector .tp-modal still present"
next_action: "Pick next site from piano group" | "Move to cloudflare group" | "All types done"
```

---

## Token Limit Protocol

When approaching token limits mid-session:
1. Complete the current test run (don't abandon mid-loop)
2. Update `RESUME.md` with exact state
3. `git push origin <session_branch>` — push all committed work
4. Do NOT open a PR for a site that isn't passing yet
5. Do NOT leave uncommitted changes — commit or stash cleanly

---

## Scheduled Resume

A daily cron trigger starts a new TDD session automatically.
The trigger runs this prompt:

> "Resume paywall TDD — read `RESUME.md` in the archiveinator repo root and continue
> the autonomous TDD loop as specified in `paywall-tdd.md`. Start from `next_action`
> in RESUME.md. Create a new session branch `tdd/session-YYYY-MM-DD`."

On resume:
- Read `RESUME.md` → restore `current_paywall_type`, skip already-passed and intractable sites
- Continue from `next_action`
- If `RESUME.md` is absent: start fresh from Piano type group

---

## What NOT to Do

- Do NOT mark sites as `xfail` in `sites.yaml` — leave them as failing tests
- Do NOT push directly to `main`
- Do NOT run all real-URL tests at once during iteration — run one site at a time
- Do NOT open PRs for partially-fixed or still-failing sites
- Do NOT skip the unit + mock_paywall regression check before committing
- Do NOT retry the exact same code change (must test a new hypothesis each attempt)

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `tests/qa/sites.yaml` | Site catalog — paywall types, difficulty, URLs |
| `tests/qa/test_real_urls.py` | Real-URL test runner (use `-k` to filter by site name) |
| `tests/qa/reporter.py` | QAResult validation — defines pass criteria |
| `archiveinator/cli.py` | `_run_paywall_bypass()` — the bypass strategy loop |
| `archiveinator/steps/paywall.py` | Detection logic (HTTP status, DOM selectors, word count) |
| `archiveinator/steps/stealth_browser.py` | Anti-fingerprinting for bot challenges |
| `archiveinator/steps/google_news.py` | Google News referrer bypass |
| `archiveinator/steps/archive_fallback.py` | Wayback / archive.today fallback |
| `archiveinator/bypass_cache.py` | Per-domain strategy cache |
| `RESUME.md` | Cross-session state — written by Claude, read on resume |
