"""Player match keys. The files do not share an id."""

import unicodedata

# Alternate spelling -> canonical key. Applied after name_key, before lookup.
ALIASES = {
    "trey-murphy": "trey-murphy-iii",
    "alex-sarr": "alexandre-sarr",
    "cam-johnson": "cameron-johnson",
}

# Periods and apostrophes are removed rather than turned into hyphens.
_DROPPED = str.maketrans("", "", ".'’‘ʼ")


def name_key(name: str) -> str:
    """Build the match key for a display name.

    Accented letters become the plain letter. Deleting the whole letter
    would split Jokić from Jokic.
    """
    plain = "".join(
        char
        for char in unicodedata.normalize("NFKD", name)
        if unicodedata.category(char) != "Mn"
    )
    lowered = plain.lower().translate(_DROPPED)
    parts: list[str] = []
    chunk: list[str] = []
    for char in lowered:
        if char.isalnum():
            chunk.append(char)
        elif chunk:
            parts.append("".join(chunk))
            chunk = []
    if chunk:
        parts.append("".join(chunk))
    return "-".join(parts)


def canonical_name_key(name: str) -> str:
    """Match key after the starting alias list."""
    key = name_key(name)
    return ALIASES.get(key, key)
