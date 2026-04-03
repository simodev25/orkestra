from app.state_machines.base import StateMachine

class RunStateMachine(StateMachine):
    TRANSITIONS = {
        "created": ["planned", "failed", "cancelled"],
        "planned": ["running", "failed", "cancelled"],
        "running": ["waiting_review", "hold", "blocked", "completed", "failed"],
        "waiting_review": ["running", "blocked", "cancelled"],
        "hold": ["running", "cancelled"],
        "blocked": ["cancelled"],
        "completed": [],
        "failed": [],
        "cancelled": [],
    }
    def __init__(self, initial_state: str = "created"):
        super().__init__(initial_state)
