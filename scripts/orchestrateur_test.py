import asyncio

from agentscope.agent import ReActAgent
from agentscope.formatter import OllamaChatFormatter
from agentscope.message import Msg
from agentscope.model import OllamaChatModel
from agentscope.tool import Toolkit, ToolResponse


MODEL_NAME = "gpt-oss:20b-cloud"
OLLAMA_HOST = "http://localhost:11434"


def build_model() -> OllamaChatModel:
    return OllamaChatModel(
        model_name=MODEL_NAME,
        host=OLLAMA_HOST,
        stream=False,
        options={"temperature": 0.2},
        keep_alive="5m",
    )


def build_worker(name: str, sys_prompt: str) -> ReActAgent:
    return ReActAgent(
        name=name,
        sys_prompt=sys_prompt,
        model=build_model(),
        formatter=OllamaChatFormatter(),
    )


scenario_worker = build_worker(
    "ScenarioWorker",
    """Tu es un agent de scénarisation.
Transforme l'objectif en scénario de test.
Réponds avec:
SCENARIO:
SUCCESS_CRITERIA:
TEST_INPUT:
""",
)

execution_worker = build_worker(
    "ExecutionWorker",
    """Tu es un agent d'exécution.
Simule l'exécution du test.
Réponds avec:
EXECUTION_STEPS:
OBSERVED_RESULT:
QUALITY_SIGNAL:
""",
)

judge_worker = build_worker(
    "JudgeWorker",
    """Tu es un agent juge.
Décide PASS ou FAIL avec un score.
Réponds avec:
VERDICT:
SCORE:
RATIONALE:
""",
)


async def run_scenario_worker(task: str) -> ToolResponse:
    res = await scenario_worker(Msg("user", task, "user"))
    return ToolResponse(content=res.get_text_content())


async def run_execution_worker(task: str) -> ToolResponse:
    res = await execution_worker(Msg("user", task, "user"))
    return ToolResponse(content=res.get_text_content())


async def run_judge_worker(task: str) -> ToolResponse:
    res = await judge_worker(Msg("user", task, "user"))
    return ToolResponse(content=res.get_text_content())


async def main():
    toolkit = Toolkit()
    toolkit.register_tool_function(run_scenario_worker)
    toolkit.register_tool_function(run_execution_worker)
    toolkit.register_tool_function(run_judge_worker)

    orchestrator = ReActAgent(
        name="OrchestratorAgent",
        sys_prompt="""Tu es un orchestrateur de test autonome.

Tu disposes de 3 tools:
- run_scenario_worker
- run_execution_worker
- run_judge_worker

Ta mission:
1. analyser l'objectif utilisateur,
2. décider quel worker appeler,
3. appeler les workers dans l'ordre pertinent,
4. produire un verdict final.

Règles:
- commence généralement par le scénario,
- puis exécution,
- puis jugement,
- mais tu peux adapter si nécessaire,
- ne réponds pas avant d'avoir utilisé les tools nécessaires.

Format final obligatoire:
FINAL_SUMMARY:
FINAL_VERDICT:
FINAL_SCORE:
""",
        model=build_model(),
        formatter=OllamaChatFormatter(),
        toolkit=toolkit,
    )

    user_goal = (
        "Tester si un agent sait résumer un document de risques sécurité "
        "pour un COMEX de façon claire, courte et exploitable."
    )

    result = await orchestrator(Msg("user", user_goal, "user"))

    print("\n=== FINAL RESULT ===")
    print(result.get_text_content())


if __name__ == "__main__":
    asyncio.run(main())