"""Per-LMS adapters for *proprietary* (Layer 3) APIs.

Everything in this package is intentionally **outside** the portable LTI core.
LTI standardises identity, roster (NRPS), and grades (AGS) — but **not** browsing
course files, listing quizzes, or reading the full gradebook. Those require each
LMS's own REST API, which differs per vendor and is not portable.

Adapters here build on the portable pieces (`ltitoolkit.token` for auth,
`ltitoolkit.http` for sessions, `ltitoolkit.exceptions` for errors) but call
vendor-specific endpoints. Use them only against the LMS they target.
"""
