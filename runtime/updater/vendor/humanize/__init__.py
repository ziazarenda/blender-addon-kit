"""Main package for humanize."""

from __future__ import annotations

__lazy_modules__ = {
    "humanize._version",
    "humanize.filesize",
    "humanize.i18n",
    "humanize.number",
    "humanize.time",
}

from .filesize import naturalsize
from .i18n import activate, deactivate, decimal_separator, thousands_separator
from .number import (
    apnumber,
    clamp,
    fractional,
    intcomma,
    intword,
    metric,
    ordinal,
    scientific,
)
from .time import (
    naturaldate,
    naturalday,
    naturaldelta,
    naturaltime,
    precisedelta,
)

from ._version import __version__

__all__ = [
    "__version__",
    "activate",
    "apnumber",
    "clamp",
    "deactivate",
    "decimal_separator",
    "fractional",
    "intcomma",
    "intword",
    "metric",
    "naturaldate",
    "naturalday",
    "naturaldelta",
    "naturalsize",
    "naturaltime",
    "ordinal",
    "precisedelta",
    "scientific",
    "thousands_separator",
]
