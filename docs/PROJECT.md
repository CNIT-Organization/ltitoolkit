# ltitoolkit — Project Design & Roadmap

A single reference for *what this is, why it's built the way it is, and what's left
to do.* Consolidated from the original `DECISIONS.md` (rationale) and `plan.md`
(roadmap) so there is one source of truth.

---

## 1. What we are building

A **generic, reusable Python package** — `ltitoolkit` (`pip install ltitoolkit`) —
that lets any Python/FastAPI app connect to **any LTI 1.3 LMS** (Canvas, Moodle,
Blackboard, …). It is deliberately **not** tied to any product or company.

- **Base:** we *vendor* (copy in) `PyLTI1p3` and make it our own — we do **not**
  pip-depend on it, so we own and can patch it.
- **We build new on top:** a **FastAPI adapter**, **Dynamic Registration**, a clean
  drop-in API, and generic **client-credentials token minting**.

## 2. Key facts we settled (so we don't re-debate)

- **LTI 1.3 is the standard.** Ignore LTI 2.0 forever (dead branch). LTI 1.1 is
  dead (OAuth 1.0a, support ended 2022).
- **LTI Advantage = the 3 services** on top of 1.3: Deep Linking, NRPS (roster),
  AGS (grades).
- **PyLTI1p3 is unmaintained** (last release Nov 2022) **but safe to vendor**:
  ~4,600 lines, correct RS256 crypto, PyJWT 2.x compatible. The spec it implements
  is frozen, so "stale" ≠ "broken."
- **MaritimeMVP is already on LTI 1.3** (not old OAuth). Its real problems: it's
  hardcoded to Canvas, and it has **no Dynamic Registration**. This toolkit fixes both.

---

## 3. DO / DON'T

**DO**
- Vendor PyLTI1p3 into `src/ltitoolkit/core/` and rebrand it as ours.
- Keep the original `LICENSE` file as-is — it is MIT and is the only legal
  requirement. It also grants the right to rebrand/sell. One file = done.
- Build a FastAPI adapter (mirrors `core/contrib/flask/`).
- Build Dynamic Registration (single-URL, no-credentials install) — our biggest win.
- Reuse the already-implemented AGS, NRPS, Deep Linking from the vendored core.
- Add a generic client-credentials token minter (tool signs with its own key → gets
  an LMS API token → **no user login, no copied credentials**).
- Use a clean library layout (`src/ltitoolkit/…`).
- Keep per-LMS proprietary API code in thin separate adapters (`adapters/canvas/`, …).

**DON'T**
- Don't put any product/company/maritime name in the package.
- Don't put LMS-proprietary REST code (course/file/quiz APIs) into the portable core.
- Don't use the old per-user Canvas OAuth login flow — prefer client-credentials.
- Don't pip-depend on PyLTI1p3 — we vendor it.
- Don't strip the `LICENSE` file.

---

## 4. Capabilities — what it CAN and CANNOT do

**CAN (portable — same code on every LTI 1.3 LMS):**
- Launch + verified identity (who, which course, what role)
- NRPS — roster of the **current** course
- AGS — push grades back to the gradebook
- Deep Linking — instructor embeds our content into a course
- Dynamic Registration — one-URL install, no credentials

**CANNOT (not part of LTI — needs per-LMS proprietary API):**
- "List ALL courses in the LMS" — impossible via LTI (only knows the launched course)
- List / download / open course files (PDFs), create quizzes, browse content
  - ✅ Doable on **Canvas** with no user login via client-credentials + Canvas API
  - ⚠️ Each other LMS = its own API + its own adapter; some may not support it
- One request to query "all LMSs at once" — impossible (each LMS is separate)

**Rule of thumb:** LTI = "a user came in the front door — here's who they are and how
to grade them." It is **not** a remote control for the whole LMS.

---

## 5. The 3 layers + "no second user login"

The student authenticates **ONCE** (the LTI 1.3 launch) and **never** logs in again.
What feels like a "second authentication" is **not** a user login — it's the tool
fetching a token automatically with its own key, invisible to the student.

| Layer | What you get | Auth needed | Portable? | Lives in |
|-------|--------------|-------------|-----------|----------|
| **1. Launch JWT** | Course name/id, student role, identity | Just the launch | ✅ all LMSs | `ltitoolkit` |
| **2. LTI Advantage** (AGS, NRPS) | Roster + read/write grades for our own activities | Auto tool token (no user login) | ✅ all LMSs | `ltitoolkit` |
| **3. LMS proprietary API** | List/create quizzes, list/open PDFs, full gradebook | Auto tool token + admin approves API scopes once at install | ❌ per-LMS | thin adapter |

- Layers **1 + 2** → built once, reused on **every** LMS.
- Layer **3** → LMS-specific endpoints + parsing, but `ltitoolkit` still provides the
  **token (auth)** generically. New LMS = small job (URLs + parsing, not auth).
- The only "extra" anywhere: at install the **admin** ticks the API scopes once. The
  **student** never does anything extra.

### The "paste a URL, no credentials" install (client's ask) — IS possible
1. Admin pastes our registration URL → clicks Submit (**Dynamic Registration**,
   approves scopes once). No credentials copied.
2. On launch, the tool signs a JWT with its **own key** → `client_credentials` grant
   → gets an LMS API token. **No user login.**
3. Tool calls the LMS API (e.g. Canvas `GET /api/v1/courses/:id/files`) → shows PDFs.

Steps 1–2 are reusable (in `ltitoolkit`); step 3 is per-LMS (a thin adapter).

---

## 6. Roadmap & status

| Phase | What | Status |
|-------|------|--------|
| **1** | Scaffold: src/ layout, vendored & rebranded core, LICENSE kept, packaging, ruff/mypy | ✅ Done |
| **2** | FastAPI adapter (login → launch, async-safe, cross-site cookies) | ✅ Done |
| **4** | LTI Advantage facade (AGS/NRPS) + client-credentials token minter (expiry-aware cache) | ✅ Done |
| **5** | Dynamic Registration (openid-config discovery, register POST + persist, `StoredToolConf` bridge) | ✅ Done (code) |
| **6** | Canvas Layer-3 adapter (`CanvasAPIClient`: files, quizzes, public-url, pagination) | ✅ Done (code) |
| **0** | Get a Canvas test environment (Free-for-Teacher) — **needs a real account** | ⏳ Pending |
| **3** | Real launch from a real Canvas course (proof-of-concept) | ⏳ Needs Phase 0 |
| **5.4** | Paste-URL install on real Canvas/Moodle | ⏳ Needs Phase 0 |
| **7** | Integrate into MaritimeMVP (replace old `services/lti`, drop per-user OAuth) | ⏳ Pending |
| — | Multi-LMS validation: prove against Canvas **and** Moodle | ⏳ Needs test LMS |

**Current state:** the standalone library is code-complete and green — all offline
tests pass, ruff + mypy clean. What remains is real-LMS validation (gated on a Canvas
test account) and integration into MaritimeMVP.

---

## 7. Best practices adopted (studied, not copied)

- From **Hypothesis lms**: expiry-aware token caching, explicit timeouts, a typed
  `ExternalRequestError` taxonomy (status/url/timeout), no retries on POST,
  Link-header pagination.
- Packaging hygiene: `src/` layout, hatchling, `from __future__ import annotations`,
  Python floor 3.10 (3.9 is EOL), ruff + mypy in CI-ready config.
- Async-over-sync: eager request-data extraction + `run_in_threadpool` for the
  blocking JWKS validation, so the sync core stays usable under FastAPI.
