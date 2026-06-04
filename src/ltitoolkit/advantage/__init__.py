"""LTI Advantage convenience layer (AGS + NRPS).

Surfaces the portable Advantage services of a validated launch through a small,
documented facade so applications never reach into ``ltitoolkit.core``.
"""

from .service import AdvantageServiceUnavailable, LaunchAdvantage

__all__ = ["LaunchAdvantage", "AdvantageServiceUnavailable"]
