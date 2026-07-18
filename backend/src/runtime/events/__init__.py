"""Phase 5 — Events Package."""

def __getattr__(name: str):
    if name == "event_bus":
        from src.runtime.events.event_bus import get_event_bus
        return get_event_bus()
    if name == "Event":
        from src.runtime.events.event_bus import Event
        return Event
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
