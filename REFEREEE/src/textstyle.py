"""
Plain-text bold/italic via Unicode "Mathematical Alphanumeric" glyphs.

FullCalendar renders event titles as plain text (textContent, not innerHTML) for
security, so literal Markdown/HTML markup would show up as-is instead of rendering.
These are real, distinct Unicode codepoints that display bold/italic in any font
without needing HTML — used to show referee names styled directly in the calendar.
Only plain A-Z/a-z are mapped; accented letters and non-Latin characters pass
through unchanged (no bold/italic Unicode block covers those).
"""

_BOLD_UPPER_BASE = 0x1D400
_BOLD_LOWER_BASE = 0x1D41A
_ITALIC_UPPER_BASE = 0x1D434
_ITALIC_LOWER_BASE = 0x1D44E
_ITALIC_SMALL_H = "ℎ"  # U+1D455 is unassigned; italic 'h' uses this legacy slot instead


def _map_letters(text: str, upper_base: int, lower_base: int, small_h: str = None) -> str:
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(upper_base + (ord(ch) - ord("A"))))
        elif small_h and ch == "h":
            out.append(small_h)
        elif "a" <= ch <= "z":
            out.append(chr(lower_base + (ord(ch) - ord("a"))))
        else:
            out.append(ch)
    return "".join(out)


def bold(text: str) -> str:
    return _map_letters(text, _BOLD_UPPER_BASE, _BOLD_LOWER_BASE)


def italic(text: str) -> str:
    return _map_letters(text, _ITALIC_UPPER_BASE, _ITALIC_LOWER_BASE, _ITALIC_SMALL_H)
