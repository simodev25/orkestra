from app.state_machines.base import StateMachine

class MCPLifecycleStateMachine(StateMachine):
    TRANSITIONS = {
        "draft": ["tested"],
        "tested": ["registered"],
        "registered": ["active"],
        "active": ["degraded", "disabled"],
        "degraded": ["active", "disabled"],
        "disabled": ["active", "archived"],
        "archived": [],
    }
    def __init__(self, initial_state: str = "draft"):
        super().__init__(initial_state)
