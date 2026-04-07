class SessionTaskRegistry:
    def __init__(self) -> None:
        self._task_sessions: dict[str, str] = {}
        self._session_tasks: dict[str, list[str]] = {}

    def bind_task(self, session_id: str, task_id: str) -> None:
        existing_session_id = self._task_sessions.get(task_id)
        if existing_session_id == session_id:
            return

        if existing_session_id is not None:
            existing_task_ids = self._session_tasks[existing_session_id]
            self._session_tasks[existing_session_id] = [
                existing_task_id
                for existing_task_id in existing_task_ids
                if existing_task_id != task_id
            ]

        self._task_sessions[task_id] = session_id
        self._session_tasks.setdefault(session_id, []).append(task_id)

    def get_session_id(self, task_id: str) -> str | None:
        return self._task_sessions.get(task_id)

    def list_task_ids(self, session_id: str) -> list[str]:
        return list(self._session_tasks.get(session_id, []))
