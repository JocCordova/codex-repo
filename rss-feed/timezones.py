from __future__ import annotations

import logging
from datetime import tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.tz import gettz

logger = logging.getLogger(__name__)


def resolve_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        fallback = gettz(name)
        if fallback is not None:
            logger.warning("Timezone '%s' not found in zoneinfo, falling back to dateutil/tzdata", name)
            return fallback
        raise ValueError(
            f"Unknown timezone '{name}'. Install tzdata or use a valid IANA timezone such as 'Europe/Berlin'."
        ) from None
