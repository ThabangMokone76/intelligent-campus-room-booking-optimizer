"""Canonical faculty styling shared by UI, exports and migrations."""
from __future__ import annotations

FACULTY_STYLES = {
    "NAS": {"background": "#059669", "foreground": "#FFFFFF", "label": "Natural & Applied Sciences"},
    "EMS": {"background": "#7C3AED", "foreground": "#FFFFFF", "label": "Economic & Management Sciences"},
    "EDU": {"background": "#F6B221", "foreground": "#241A00", "label": "Education"},
    "HUM": {"background": "#D97706", "foreground": "#FFFFFF", "label": "Humanities"},
}
DEFAULT_FACULTY_STYLE = {"background": "#E5E7EB", "foreground": "#111827", "label": "Other"}


def get_faculty_style(faculty_code: str | None) -> dict[str, str]:
    return dict(FACULTY_STYLES.get((faculty_code or "").upper(), DEFAULT_FACULTY_STYLE))


def apply_canonical_faculty_colours(conn) -> None:
    for code, style in FACULTY_STYLES.items():
        conn.execute(
            "UPDATE faculties SET colour_hex=? WHERE UPPER(faculty_code)=?",
            (style["background"], code),
        )
