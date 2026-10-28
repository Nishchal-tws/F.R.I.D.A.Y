from collections import deque

class ConversationMemory:
    def __init__(self, max_messages: int = 30):
        self.messages = deque(maxlen=max_messages)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def as_messages(self) -> list[dict]:
        return list(self.messages)
