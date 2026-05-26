import threading
from enum import Enum
from typing import Callable, List, Optional
import time
import config


class State(Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    DANCING = "DANCING"


_VALID_TRANSITIONS = {
    State.IDLE: {State.LISTENING, State.SPEAKING},
    State.LISTENING: {State.TRANSCRIBING, State.IDLE},
    State.TRANSCRIBING: {State.THINKING, State.IDLE},
    State.THINKING: {State.SPEAKING, State.DANCING, State.IDLE},
    State.SPEAKING: {State.SPEAKING, State.IDLE},
    State.DANCING: {State.DANCING,State.IDLE}
}


class StateMachine:
    """Thread-safe finite state machine for Ron OS status.

    - Use `set_state` to change state (optionally `force=True` to bypass validation).
    - Subscribe callbacks with `subscribe(callback)` where callback(old, new, reason).
    - Use `wait_for(state, timeout)` to block until a state is reached.
    """

    def __init__(self, initial: State = State.IDLE):
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._state = initial
        self._subs: List[Callable[[State, State, Optional[str]], None]] = []

    def get_state(self) -> State:
        with self._lock:
            return self._state

    def subscribe(self, callback: Callable[[State, State, Optional[str]], None]) -> None:
        with self._lock:
            if callback not in self._subs:
                self._subs.append(callback)

    def unsubscribe(self, callback: Callable[[State, State, Optional[str]], None]) -> None:
        with self._lock:
            try:
                self._subs.remove(callback)
            except ValueError:
                pass

    def _notify_subscribers(self, old: State, new: State, reason: Optional[str]) -> None:
        # Run callbacks in background threads to avoid blocking callers
        for cb in list(self._subs):
            try:
                threading.Thread(target=lambda: cb(old, new, reason), daemon=True).start()
            except Exception as e:
                config.logger.error(f"Error scheduling subscriber callback: {e}")

    def can_transition(self, new: State) -> bool:
        with self._lock:
            allowed = _VALID_TRANSITIONS.get(self._state, set())
            return new in allowed

    def set_state(self, new: State, force: bool = False, reason: Optional[str] = None) -> bool:
        """Attempt to set a new state. Returns True if state changed."""
        with self._lock:
            old = self._state
            
            if not force and new not in _VALID_TRANSITIONS.get(old, set()):
                config.logger.warning(f"Invalid transition attempted: {old} -> {new}")
                return False

            self._state = new
            self._cond.notify_all()
            config.logger.info(f"State change: {old} -> {new} ({reason})")
            self._notify_subscribers(old, new, reason)
            return True

    def wait_for(self, target: State, timeout: Optional[float] = None) -> bool:
        """Block until the machine reaches `target` or timeout. Returns True if reached."""
        with self._cond:
            if self._state == target:
                return True
            start = time.time()
            while self._state != target:
                remaining = None if timeout is None else max(0.0, timeout - (time.time() - start))
                if remaining == 0:
                    break
                self._cond.wait(timeout=remaining)
            return self._state == target

    def transition_context(self, new: State, force: bool = False, reason: Optional[str] = None):
        """Context manager useful to set a temporary state and return to IDLE afterwards.

        Example:
            with sm.transition_context(State.LISTENING):
                ...
        """
        sm = self

        class _Ctx:
            def __enter__(self_inner):
                sm.set_state(new, force=force, reason=reason)
                return sm

            def __exit__(self_inner, exc_type, exc, tb):
                # On exit, return to IDLE if currently in a terminal state that should go to IDLE
                try:
                    sm.set_state(State.IDLE, force=True, reason="context-exit")
                except Exception:
                    pass

        return _Ctx()


_GLOBAL_STATUS = StateMachine()


def get_global_status() -> StateMachine:
    return _GLOBAL_STATUS


if __name__ == "__main__":
    # Quick smoke test
    def logger_cb(old, new, reason):
        print(f"Callback: {old} -> {new} ({reason})")

    sm = StateMachine()
    sm.subscribe(logger_cb)
    print("Current:", sm.get_state())
    sm.set_state(State.LISTENING, reason="test")
    sm.set_state(State.TRANSCRIBING, reason="test2")
    sm.set_state(State.THINKING, reason="test3")
    sm.set_state(State.SPEAKING, reason="test4")
    sm.set_state(State.IDLE, reason="done")