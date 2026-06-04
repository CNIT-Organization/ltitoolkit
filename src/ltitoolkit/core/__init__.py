"""Vendored LTI 1.3 Advantage engine.

This package is a vendored, rebranded copy of PyLTI1p3 (MIT licensed). It
provides the spec-correct, security-critical LTI 1.3 primitives: OIDC login,
JWT/JWKS validation, message launches, and the LTI Advantage services
(Assignment & Grade Services, Names & Role Provisioning, Deep Linking).

We vendor rather than depend on it so we own the code and can patch it; upstream
is unmaintained (last release 2022) but implements a frozen specification. See
``LICENSE`` at the repository root for the original MIT terms.

Do not import from here directly in application code — use the public
``ltitoolkit`` API and framework adapters instead. This subpackage is internal.
"""

# Upstream PyLTI1p3 release this vendored copy is based on.
VENDORED_FROM = "PyLTI1p3 2.0.0"

__version__ = "2.0.0"
