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
Tu aides l'orchestrateur à transformer un besoin en scénario de test.
Réponds de façon courte et opérationnelle.""",
)

execution_worker = build_worker(
    "ExecutionWorker",
    """Tu es un agent d'exécution.
Tu simules ou exécutes un test demandé par l'orchestrateur.
Réponds de façon courte et structurée.""",
)

judge_worker = build_worker(
    "JudgeWorker",
    """Tu es un agent juge.
Tu évalues un résultat de test et tu donnes un verdict clair.
Réponds de façon courte et structurée.""",
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


def build_orchestrator() -> ReActAgent:
    toolkit = Toolkit()
    toolkit.register_tool_function(run_scenario_worker)
    toolkit.register_tool_function(run_execution_worker)
    toolkit.register_tool_function(run_judge_worker)

    return ReActAgent(
        name="OrchestratorAgent",
        sys_prompt="""Tu es un orchestrateur de test interactif.

Tu dialogues directement avec l'utilisateur.
Tu peux :
- répondre toi-même si la demande est simple,
- appeler run_scenario_worker si l'utilisateur veut définir un scénario,
- appeler run_execution_worker si l'utilisateur veut lancer ou simuler un test,
- appeler run_judge_worker si l'utilisateur veut évaluer un résultat.

Règles :
- parle comme un copilote d'orchestration,
- garde le contexte de la conversation,
- appelle les tools seulement quand c'est utile,
- si l'utilisateur affine sa demande, adapte le plan,
- reste concret.

Quand tu réponds à l'utilisateur :
- explique ce que tu fais,
- donne un résultat clair,
- ne fais pas de blabla inutile.
""",
        model=build_model(),
        formatter=OllamaChatFormatter(),
        toolkit=toolkit,
    )


async def main():
    orchestrator = build_orchestrator()

    print("Mode interactif OrchestratorAgent")
    print("Tape 'exit' pour quitter.\n")

    msg = None

    while True:
        user_input = input("Toi > ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Fin de session.")
            break

        msg = Msg("user", user_input, "user")
        response = await orchestrator(msg)

        print(f"\nOrchestrator > {response.get_text_content()}\n")


if __name__ == "__main__":
    asyncio.run(main())