class SessionConversationRegistry:
    def __init__(self) -> None:
        self._session_dialogs: dict[str, str] = {}

    def bind_dialog(self, session_id: str, dialog_id: str) -> None:
        self._session_dialogs[session_id] = dialog_id

    def get_dialog_id(self, session_id: str) -> str | None:
        return self._session_dialogs.get(session_id)
