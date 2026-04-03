from app.state_machines.base import StateMachine

class AgentLifecycleStateMachine(StateMachine):
    TRANSITIONS = {
        "draft": ["tested"],
        "tested": ["registered"],
        "registered": ["active"],
        "active": ["deprecated", "disabled"],
        "deprecated": ["archived"],
        "disabled": ["active", "archived"],
        "archived": [],
    }
    def __init__(self, initial_state: str = "draft"):
        super().__init__(initial_state)
