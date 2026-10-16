"""Size limits for imported datasets, and the request-body limit derived from them.

The browser sends a file as base64 text inside JSON. Base64 turns every 3 bytes into 4
characters, so a file of ``n`` bytes needs ``4 * ceil(n / 3)`` characters. The limits are
therefore stated twice, deliberately:

* ``MAX_FILE_BYTES`` caps the decoded file, the quantity a user understands;
* ``MAX_BASE64_CHARS`` is the base64 length of a file of that size (the schema limit). As
  2 MiB is not a multiple of 3, a string of this length can decode to up to 2 bytes more,
  so the decoded size is checked separately;
* ``MAX_REQUEST_BYTES`` caps the whole HTTP body, before any of it is parsed, with room for
  the JSON around the file and the parsing options.
"""

from __future__ import annotations

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB of CSV text
MAX_BASE64_CHARS = 4 * ((MAX_FILE_BYTES + 2) // 3)
MAX_DATA_ROWS = 50_000
MAX_COLUMNS = 100
MAX_COLUMN_NAME_CHARS = 200

# Room for the JSON envelope and the options (at most 20 missing-value markers of 32
# characters and 100 type overrides: a few kilobytes). Generous, and still tiny next to the
# file itself.
_OPTIONS_MARGIN_BYTES = 64 * 1024
MAX_REQUEST_BYTES = MAX_BASE64_CHARS + _OPTIONS_MARGIN_BYTES

# What the response echoes back: enough to read, never the whole file.
PREVIEW_ROWS = 20
MAX_DISPLAY_CHARS = 120
TOP_CATEGORIES = 10
MAX_EXAMPLES = 5
MAX_HISTOGRAM_BINS = 50
