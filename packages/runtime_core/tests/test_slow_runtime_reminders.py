from runtime_core.reminder_classifier import ReminderIntent, RuleBasedReminderClassifier
from runtime_core.reminder_parser import parse_reminder_request


def test_rule_based_classifier_detects_reminder_turn() -> None:
    classifier = RuleBasedReminderClassifier()

    assert classifier.classify("Remind me tomorrow to pay rent") == ReminderIntent.CREATE_REMINDER


def test_rule_based_classifier_detects_non_reminder_turn() -> None:
    classifier = RuleBasedReminderClassifier()

    assert classifier.classify("What time is it?") == ReminderIntent.NON_REMINDER


def test_reminder_parser_extracts_title_and_optional_time() -> None:
    parsed = parse_reminder_request("Remind me tomorrow at 9am to pay rent")

    assert parsed.title == "pay rent"
    assert parsed.scheduled_at_text == "tomorrow at 9am"


def test_reminder_parser_leaves_time_empty_when_missing() -> None:
    parsed = parse_reminder_request("Remind me to pay rent")

    assert parsed.title == "pay rent"
    assert parsed.scheduled_at_text is None
