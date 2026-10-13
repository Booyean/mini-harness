class EventBus:
    def __init__(self):
        self._handlers = {}

    def on(self, event_type, handler):
        self._handlers.setdefault(event_type, []).append(handler)

    def emit(self, event_type, **data):
        for handler in self._handlers.get(event_type, []):
            handler(**data)

    def clear(self):
        self._handlers.clear()


DEFAULT_BUS = EventBus()
