from __future__ import annotations

from enum import Enum


class ReminderIntent(str, Enum):
    CREATE_REMINDER = "create_reminder"
    NON_REMINDER = "non_reminder"


class RuleBasedReminderClassifier:
    def classify(self, text: str) -> ReminderIntent:
        lowered = text.strip().lower()
        if "remind me" in lowered or "提醒我" in text:
            return ReminderIntent.CREATE_REMINDER
        return ReminderIntent.NON_REMINDER
