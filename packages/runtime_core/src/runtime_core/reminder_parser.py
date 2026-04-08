from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedReminderRequest:
    title: str
    scheduled_at_text: str | None


def parse_reminder_request(text: str) -> ParsedReminderRequest:
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered.startswith("remind me "):
        remainder = stripped[10:]
        lowered_remainder = remainder.lower()
        if lowered_remainder.startswith("to "):
            return ParsedReminderRequest(title=remainder[3:].strip(), scheduled_at_text=None)
        if " to " in lowered_remainder:
            index = lowered_remainder.index(" to ")
            scheduled_at_text = remainder[:index].strip() or None
            title = remainder[index + 4 :].strip()
            return ParsedReminderRequest(title=title, scheduled_at_text=scheduled_at_text)
        return ParsedReminderRequest(title=remainder.strip(), scheduled_at_text=None)

    if stripped.startswith("提醒我"):
        remainder = stripped[3:].strip()
        if "去" in remainder:
            before, after = remainder.split("去", 1)
            return ParsedReminderRequest(
                title=after.strip(),
                scheduled_at_text=before.strip() or None,
            )
        return ParsedReminderRequest(title=remainder, scheduled_at_text=None)

    return ParsedReminderRequest(title=stripped, scheduled_at_text=None)
