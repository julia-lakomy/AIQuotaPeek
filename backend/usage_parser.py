"""Extract only the two requested limits from the visible Usage page text.

These pages have no documented personal-subscription API. Keep parsing here so a
site change cannot silently turn an unrelated percentage into a limit.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta


HEADINGS = {
    "chatgpt": {
        "session": re.compile(r"^(?:current|obecna|bieżąca)\s+(?:session|sesja)$", re.I),
        "weekly": re.compile(r"^(?:weekly\s+limit|limit\s+tygodniowy|tygodniowy\s+limit)$", re.I),
    },
    "claude": {
        "session": re.compile(r"^(?:current\s+session|obecna\s+sesja|bieżąca\s+sesja)$", re.I),
        "weekly": re.compile(r"^(?:weekly\s+limits?|limity?\s+tygodniow[ey]|limit\s+tygodniowy)$", re.I),
    },
}

PERCENT = re.compile(
    r"(?:(?P<n1>\d{1,3})\s*%\s*(?P<mode1>used|remaining|left|wykorzystan[eo]|zużyt[eo]|pozostało)"
    r"|(?P<mode2>remaining|left|pozostało|used|wykorzystano|zużyto)\s*(?P<n2>\d{1,3})\s*%)",
    re.I,
)
WEEKDAYS = {
    "monday": 0, "poniedziałek": 0, "tuesday": 1, "wtorek": 1,
    "wednesday": 2, "środa": 2, "thursday": 3, "czwartek": 3,
    "friday": 4, "piątek": 4, "saturday": 5, "sobota": 5,
    "sunday": 6, "niedziela": 6,
}
POLISH_WEEKDAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)?\b", re.I)
RELATIVE = re.compile(
    r"(?:reset\s+za|resets?\s+in)\s*"
    r"(?:(\d+)\s*(?:dni|dzień|days?|d)\s*(?:i|and)?\s*)?"
    r"(?:(\d+)\s*(?:godz\.?|hours?|hrs?|h)\s*(?:i|and)?\s*)?"
    r"(?:(\d+)\s*(?:min\.?|minutes?|mins?|m))?",
    re.I,
)


def _reset_label(raw: str, now: datetime) -> str | None:
    text = raw.strip()
    relative = RELATIVE.search(text)
    if relative and any(part is not None for part in relative.groups()):
        days, hours, minutes = (int(part or 0) for part in relative.groups())
        target = now + timedelta(days=days, hours=hours, minutes=minutes)
        return f"~{POLISH_WEEKDAYS[target.weekday()]} {target:%H:%M}"

    time_match = TIME.search(text)
    if not time_match:
        return None
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    meridiem = time_match.group(3)
    if meridiem:
        hour = hour % 12 + (12 if meridiem.upper() == "PM" else 0)
    if hour > 23 or minute > 59:
        return None

    before_time = text[:time_match.start()].casefold()
    weekday = next((day for name, day in WEEKDAYS.items() if name in before_time), None)
    if weekday is None:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
    else:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        candidate += timedelta(days=(weekday - now.weekday()) % 7)
        if candidate <= now:
            candidate += timedelta(days=7)
    return f"{POLISH_WEEKDAYS[candidate.weekday()]} {candidate:%H:%M}"


def _find_metric(lines: list[str], start: int, end: int, now: datetime) -> dict:
    remaining = None
    reset = None
    for line in lines[start:end]:
        match = PERCENT.search(line)
        if match and remaining is None:
            number = int(match.group("n1") or match.group("n2"))
            mode = (match.group("mode1") or match.group("mode2")).casefold()
            if 0 <= number <= 100:
                remaining = 100 - number if mode.startswith(("used", "wykorzyst", "zużyt")) else number
        if reset is None and ("reset" in line.casefold() or "zerow" in line.casefold()):
            reset = _reset_label(line, now)
    return {"remaining": remaining, "reset": reset}


def parse_usage(service: str, text: str, now: datetime) -> dict:
    if service not in HEADINGS:
        raise ValueError(f"Unknown service: {service}")
    text = re.sub(
        r"(?i)(current session|weekly limits?|limit tygodniowy)(?=resets?|reset|pozostało|\d{1,3}\s*%)",
        r"\1\n",
        text,
    )
    text = re.sub(r"(?i)\b(AM|PM)(?=\d{1,3}\s*%)", r"\1\n", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    anchors: dict[str, int] = {}
    for index, line in enumerate(lines):
        for key, pattern in HEADINGS[service].items():
            if key not in anchors and pattern.fullmatch(line):
                anchors[key] = index

    result = {"session": {"remaining": None, "reset": None}, "weekly": {"remaining": None, "reset": None}}
    for key, start in anchors.items():
        next_anchor = min((index for index in anchors.values() if index > start), default=len(lines))
        result[key] = _find_metric(lines, start + 1, min(next_anchor, start + 14), now)

    # Claude can show the weekly reset/percentage after the session block
    # without a standalone "Weekly limits" line. Use the second reset pair.
    if service == "claude" and result["weekly"]["remaining"] is None and "session" in anchors:
        session_start = anchors["session"] + 1
        first_percent = next(
            (index for index in range(session_start, min(len(lines), session_start + 8)) if PERCENT.search(lines[index])),
            None,
        )
        if first_percent is not None:
            second_reset = next(
                (index for index in range(first_percent + 1, min(len(lines), first_percent + 10)) if "reset" in lines[index].casefold()),
                None,
            )
            if second_reset is not None:
                result["weekly"] = _find_metric(lines, second_reset, min(len(lines), second_reset + 4), now)
    return result
