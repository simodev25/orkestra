from app.state_machines.base import StateMachine

class ApprovalStateMachine(StateMachine):
    TRANSITIONS = {
        "requested": ["assigned", "cancelled"],
        "assigned": ["pending", "cancelled"],
        "pending": ["approved", "rejected", "refine_required"],
        "approved": [],
        "rejected": [],
        "refine_required": [],
        "cancelled": [],
    }
    def __init__(self, initial_state: str = "requested"):
        super().__init__(initial_state)
