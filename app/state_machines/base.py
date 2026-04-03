"""Base state machine with audit history."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class TransitionRecord:
    from_state: str
    to_state: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""


class StateMachine:
    TRANSITIONS: dict[str, list[str]] = {}

    def __init__(self, initial_state: str):
        if initial_state not in self.TRANSITIONS:
            raise ValueError(f"Invalid initial state: {initial_state}")
        self._state = initial_state
        self._history: list[TransitionRecord] = []

    @property
    def state(self) -> str:
        return self._state

    @property
    def history(self) -> list[TransitionRecord]:
        return list(self._history)

    @property
    def is_terminal(self) -> bool:
        return not self.TRANSITIONS.get(self._state, [])

    def can_transition(self, target: str) -> bool:
        return target in self.TRANSITIONS.get(self._state, [])

    def transition(self, target: str, reason: str = "") -> bool:
        if not self.can_transition(target):
            logger.warning(
                f"State transition rejected: {self._state} → {target} "
                f"(allowed: {self.TRANSITIONS.get(self._state, [])})"
            )
            return False
        record = TransitionRecord(from_state=self._state, to_state=target, reason=reason)
        self._history.append(record)
        logger.info(f"State: {self._state} → {target} ({reason})")
        self._state = target
        return True

    def get_allowed_transitions(self) -> list[str]:
        return list(self.TRANSITIONS.get(self._state, []))
