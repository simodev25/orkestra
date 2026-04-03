from app.state_machines.base import StateMachine

class RequestStateMachine(StateMachine):
    TRANSITIONS = {
        "draft": ["submitted", "cancelled"],
        "submitted": ["accepted", "rejected", "cancelled"],
        "accepted": ["converted_to_case"],
        "rejected": [],
        "converted_to_case": [],
        "cancelled": [],
    }
    def __init__(self, initial_state: str = "draft"):
        super().__init__(initial_state)
