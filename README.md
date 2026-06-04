# ltitoolkit

A framework-agnostic **LTI 1.3 Advantage** toolkit for Python. Connect any Python
application to any LTI 1.3 compliant LMS — Canvas, Moodle, Blackboard, and more —
with a single dependency.

> Status: **early development (v0.1.0)** — the vendored LTI engine is in place;
> the FastAPI adapter, Dynamic Registration, and token minting are being built.
> See [`docs/PROJECT.md`](./docs/PROJECT.md) for the design rationale, capability
> boundaries, and roadmap.

## What it does (portable — same code on every LMS)

- **Launch & identity** — verified OIDC/JWT launch: who the user is, which course,
  what role.
- **LTI Advantage**
  - **AGS** — read/write grades for your tool's activities.
  - **NRPS** — fetch the current course roster.
  - **Deep Linking** — let instructors embed your content into a course.
- **Dynamic Registration** — install on a new LMS by pasting one URL (no credentials).
- **Client-credentials tokens** — authenticate as the tool with its own key; no user
  login required.

## What it deliberately does **not** do

LTI is not a remote control for the whole LMS. Listing all courses, browsing/opening
files, or creating native quizzes require each LMS's **proprietary** REST API and are
**not** part of this portable core. Put that code in thin, per-LMS adapters (e.g. a
Canvas adapter) built on top of the toolkit's generic token minting.

## Layout

```
src/ltitoolkit/
├── core/                  # vendored LTI 1.3 engine (PyLTI1p3, rebranded) — internal
├── fastapi/               # FastAPI adapter (Phase 2)
├── token/                 # generic client-credentials token minting (Phase 4)
└── dynamic_registration/  # single-URL install (Phase 5)
```

## Install (development)

```bash
pip install -e ".[fastapi,dev]"
```

## License

MIT. The `core/` engine is a vendored copy of
[PyLTI1p3](https://github.com/dmitry-viskov/pylti1.3) (MIT); its original license
is preserved in [`LICENSE`](./LICENSE).
