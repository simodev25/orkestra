from app.state_machines.base import StateMachine

class CaseStateMachine(StateMachine):
    TRANSITIONS = {
        "created": ["ready_for_planning"],
        "ready_for_planning": ["planning"],
        "planning": ["running", "blocked"],
        "running": ["waiting_review", "blocked", "completed"],
        "waiting_review": ["running", "completed", "blocked"],
        "blocked": ["planning", "archived"],
        "completed": ["archived"],
        "archived": [],
    }
    def __init__(self, initial_state: str = "created"):
        super().__init__(initial_state)
