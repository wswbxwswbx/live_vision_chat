from datetime import datetime


def test_in_memory_reminder_service_creates_record() -> None:
    from execution.reminder_service import InMemoryReminderService

    service = InMemoryReminderService()

    reminder = service.create_reminder(
        title="Pay rent",
        scheduled_at_text="tomorrow at 9am",
        scheduled_at_iso=None,
        source_session_id="s1",
        task_id="task-1",
        raw_user_input="Remind me tomorrow at 9am to pay rent",
    )

    assert reminder["title"] == "Pay rent"
    assert reminder["task_id"] == "task-1"
    assert reminder["source_session_id"] == "s1"
    assert reminder["scheduled_at_text"] == "tomorrow at 9am"
    assert reminder["scheduled_at_iso"] is None
    assert reminder["status"] == "scheduled"
    assert reminder["raw_user_input"] == "Remind me tomorrow at 9am to pay rent"
    assert reminder["id"].startswith("reminder-")
    datetime.fromisoformat(reminder["created_at"])


def test_in_memory_reminder_service_lists_created_records() -> None:
    from execution.reminder_service import InMemoryReminderService

    service = InMemoryReminderService()

    first = service.create_reminder(
        title="Pay rent",
        scheduled_at_text="tomorrow at 9am",
        scheduled_at_iso=None,
        source_session_id="s1",
        task_id="task-1",
        raw_user_input="Remind me tomorrow at 9am to pay rent",
    )
    second = service.create_reminder(
        title="Join standup",
        scheduled_at_text="today at 10am",
        scheduled_at_iso="2026-04-08T10:00:00+08:00",
        source_session_id="s2",
        task_id="task-2",
        raw_user_input="Remind me today at 10am to join standup",
    )

    reminders = service.list_reminders()

    assert [reminder["id"] for reminder in reminders] == [first["id"], second["id"]]
    assert reminders[1]["scheduled_at_iso"] == "2026-04-08T10:00:00+08:00"
