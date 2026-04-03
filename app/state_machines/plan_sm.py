from app.state_machines.base import StateMachine

class PlanStateMachine(StateMachine):
    TRANSITIONS = {
        "draft": ["validated", "adjusted_by_control", "rejected"],
        "validated": ["executing"],
        "adjusted_by_control": ["executing", "rejected"],
        "rejected": [],
        "executing": ["completed", "superseded"],
        "completed": [],
        "superseded": [],
    }
    def __init__(self, initial_state: str = "draft"):
        super().__init__(initial_state)
