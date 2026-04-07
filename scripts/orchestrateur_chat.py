import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from agentscope.agent import ReActAgent
from agentscope.formatter import OllamaChatFormatter
from agentscope.message import Msg
from agentscope.model import OllamaChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, ToolResponse


MODEL_NAME = "gpt-oss:20b-cloud"
OLLAMA_HOST = "http://localhost:11434"
TEMPERATURE = 0.2
KEEP_ALIVE = "5m"


# =============================================================================
# Session state
# =============================================================================

@dataclass
class TestRunRecord:
    run_id: int
    target_agent_id: str
    objective: str
    scenario: str
    execution_result: str
    judgment: str


@dataclass
class TestSessionState:
    target_agent_id: Optional[str] = None
    target_agent_label: Optional[str] = None
    last_objective: Optional[str] = None
    last_scenario: Optional[str] = None
    last_execution_result: Optional[str] = None
    last_judgment: Optional[str] = None
    current_status: str = "idle"
    run_counter: int = 0
    history: list[TestRunRecord] = field(default_factory=list)

    def to_summary_text(self) -> str:
        history_summary = []
        for run in self.history[-3:]:
            history_summary.append(
                f"- run_id={run.run_id}, agent={run.target_agent_id}, objective={run.objective}"
            )

        history_text = "\n".join(history_summary) if history_summary else "- aucun run"

        return f"""SESSION_STATE:
target_agent_id: {self.target_agent_id or "None"}
target_agent_label: {self.target_agent_label or "None"}
last_objective: {self.last_objective or "None"}
current_status: {self.current_status}
last_scenario: {self.last_scenario or "None"}
last_execution_result: {self.last_execution_result or "None"}
last_judgment: {self.last_judgment or "None"}

RECENT_HISTORY:
{history_text}
"""


SESSION = TestSessionState()


# =============================================================================
# Model / agent builders
# =============================================================================

def build_model(stream: bool = True) -> OllamaChatModel:
    return OllamaChatModel(
        model_name=MODEL_NAME,
        host=OLLAMA_HOST,
        stream=stream,
        options={"temperature": TEMPERATURE},
        keep_alive=KEEP_ALIVE,
    )


def build_subagent(name: str, sys_prompt: str) -> ReActAgent:
    return ReActAgent(
        name=name,
        sys_prompt=sys_prompt,
        model=build_model(stream=False),
        formatter=OllamaChatFormatter(),
    )


# =============================================================================
# Testable agents registry
# =============================================================================

TESTABLE_AGENTS: dict[str, dict[str, Any]] = {
    "summary_agent": {
        "label": "Summary Agent",
        "description": "Agent de synthèse orienté résumés exécutifs et COMEX.",
        "capabilities": [
            "summarization",
            "executive_briefing",
            "risk_summary",
        ],
    },
    "identity_resolution_agent": {
        "label": "Identity Resolution Agent",
        "description": "Agent de résolution d'identité d'entreprise / entité cible.",
        "capabilities": [
            "entity_resolution",
            "disambiguation",
            "company_lookup",
        ],
    },
    "policy_review_agent": {
        "label": "Policy Review Agent",
        "description": "Agent d'analyse policy / conformité d'une sortie agentique.",
        "capabilities": [
            "policy_review",
            "compliance_check",
            "safety_evaluation",
        ],
    },
}


def get_agent_registry_text() -> str:
    lines = []
    for agent_id, meta in TESTABLE_AGENTS.items():
        capabilities = ", ".join(meta["capabilities"])
        lines.append(
            f"- agent_id={agent_id} | label={meta['label']} | "
            f"description={meta['description']} | capabilities={capabilities}"
        )
    return "\n".join(lines)


# =============================================================================
# SubAgents
# =============================================================================

scenario_subagent = build_subagent(
    "ScenarioSubAgent",
    """Tu es un sous-agent de scénarisation de test.

Tu aides l'orchestrateur à transformer un besoin de test en scénario concret
pour un agent sous test.

Tu réponds toujours en français.

Format obligatoire :
SCENARIO:
<description courte et exploitable>

SUCCESS_CRITERIA:
- <critère 1>
- <critère 2>
- <critère 3>

TEST_INPUT:
<entrée de test réaliste>
""",
)

judge_subagent = build_subagent(
    "JudgeSubAgent",
    """Tu es un sous-agent juge.

Tu évalues la sortie d'un agent sous test par rapport à un scénario et à des
critères de succès.

Tu réponds toujours en français.

Format obligatoire :
VERDICT: PASS ou FAIL ou PARTIAL
SCORE: <nombre entre 0.00 et 1.00>
RATIONALE:
<explication courte>
""",
)

robustness_subagent = build_subagent(
    "RobustnessSubAgent",
    """Tu es un sous-agent de robustesse.

Tu proposes un test complémentaire plus dur ou un edge case à partir d'un test
déjà exécuté.

Tu réponds toujours en français.

Format obligatoire :
FOLLOWUP_TEST:
<test complémentaire>

WHY_IT_MATTERS:
<pourquoi ce test est utile>
""",
)


# =============================================================================
# Agent under test simulation layer
# =============================================================================

async def run_target_agent_logic(agent_id: str, task: str) -> str:
    """
    Simule l'exécution de l'agent sous test.

    Dans ton vrai système, cette fonction devra appeler le vrai agent enregistré
    dans Orkestra, pas simuler la réponse.
    """
    if agent_id == "summary_agent":
        return f"""RÉPONSE_AGENT:
Synthèse COMEX des principaux risques :
- Risque 1 : exposition fournisseur et MFA insuffisant.
- Risque 2 : vulnérabilités critiques non patchées.
- Risque 3 : coordination insuffisante de la réponse à incident.

Actions prioritaires :
- Généraliser la MFA sur les accès tiers.
- Réduire le délai de patching critique.
- Formaliser les rôles de réponse à incident.

COMMENTAIRE:
Réponse courte, structurée, orientée décideurs.

TASK_REPLAY:
{task}
"""

    if agent_id == "identity_resolution_agent":
        return f"""RÉPONSE_AGENT:
Entreprise cible identifiée avec confiance moyenne.
- Candidat 1 : entité légale principale
- Candidat 2 : établissement secondaire potentiellement ambigu

COMMENTAIRE:
L'agent a identifié un risque d'homonymie et demande une confirmation.

TASK_REPLAY:
{task}
"""

    if agent_id == "policy_review_agent":
        return f"""RÉPONSE_AGENT:
Analyse policy réalisée.
- Pas de violation majeure détectée
- Quelques formulations trop vagues
- Recommandation : renforcer la traçabilité du verdict

COMMENTAIRE:
Sortie globalement conforme mais perfectible.

TASK_REPLAY:
{task}
"""

    return f"""RÉPONSE_AGENT:
Agent inconnu ou non implémenté.

COMMENTAIRE:
Le registre des agents testables doit être enrichi.

TASK_REPLAY:
{task}
"""


# =============================================================================
# Tools exposed to OrchestratorAgent
# =============================================================================

async def list_testable_agents() -> ToolResponse:
    return ToolResponse(content=get_agent_registry_text())


async def select_target_agent(agent_id: str) -> ToolResponse:
    meta = TESTABLE_AGENTS.get(agent_id)
    if not meta:
        return ToolResponse(
            content=f"ERROR: agent_id inconnu: {agent_id}"
        )

    SESSION.target_agent_id = agent_id
    SESSION.target_agent_label = meta["label"]

    return ToolResponse(
        content=(
            f"TARGET_AGENT_SELECTED:\n"
            f"agent_id: {agent_id}\n"
            f"label: {meta['label']}\n"
            f"description: {meta['description']}"
        )
    )


async def run_scenario_subagent(task: str) -> ToolResponse:
    res = await scenario_subagent(Msg("user", task, "user"))
    return ToolResponse(content=res.get_text_content())


async def run_target_agent_under_test(task: str) -> ToolResponse:
    if not SESSION.target_agent_id:
        return ToolResponse(
            content="ERROR: aucun agent sous test sélectionné."
        )

    result = await run_target_agent_logic(SESSION.target_agent_id, task)
    return ToolResponse(content=result)


async def run_judge_subagent(task: str) -> ToolResponse:
    res = await judge_subagent(Msg("user", task, "user"))
    return ToolResponse(content=res.get_text_content())


async def run_robustness_subagent(task: str) -> ToolResponse:
    res = await robustness_subagent(Msg("user", task, "user"))
    return ToolResponse(content=res.get_text_content())


async def get_session_state() -> ToolResponse:
    return ToolResponse(content=SESSION.to_summary_text())


async def save_test_run(
    objective: str,
    scenario: str,
    execution_result: str,
    judgment: str,
) -> ToolResponse:
    SESSION.run_counter += 1
    record = TestRunRecord(
        run_id=SESSION.run_counter,
        target_agent_id=SESSION.target_agent_id or "unknown",
        objective=objective,
        scenario=scenario,
        execution_result=execution_result,
        judgment=judgment,
    )
    SESSION.history.append(record)
    SESSION.last_objective = objective
    SESSION.last_scenario = scenario
    SESSION.last_execution_result = execution_result
    SESSION.last_judgment = judgment
    SESSION.current_status = "awaiting_user"

    return ToolResponse(
        content=f"RUN_SAVED: run_id={record.run_id}, status=awaiting_user"
    )


# =============================================================================
# OrchestratorAgent
# =============================================================================

def build_orchestrator() -> ReActAgent:
    toolkit = Toolkit()

    toolkit.register_tool_function(list_testable_agents)
    toolkit.register_tool_function(select_target_agent)
    toolkit.register_tool_function(run_scenario_subagent)
    toolkit.register_tool_function(run_target_agent_under_test)
    toolkit.register_tool_function(run_judge_subagent)
    toolkit.register_tool_function(run_robustness_subagent)
    toolkit.register_tool_function(get_session_state)
    toolkit.register_tool_function(save_test_run)

    return ReActAgent(
        name="OrchestratorAgent",
        sys_prompt="""Tu es OrchestratorAgent, l'orchestrateur interactif de test d'agents d'Orkestra.

Mission centrale :
- tu testes des agents ;
- tu pilotes des sous-agents spécialisés ;
- tu exécutes l'agent sous test ;
- tu rends un verdict ;
- puis tu redonnes la main à l'utilisateur pour lancer des tests complémentaires.

Important :
- tu ne testes pas des tâches abstraites ;
- tu testes toujours un agent sous test explicite ;
- si aucun agent n'est sélectionné, tu dois d'abord aider l'utilisateur à en choisir un.

Tu disposes des tools suivants :
- list_testable_agents : liste les agents testables
- select_target_agent : sélectionne l'agent sous test
- run_scenario_subagent : construit un scénario
- run_target_agent_under_test : exécute le vrai agent sous test
- run_judge_subagent : juge le résultat
- run_robustness_subagent : propose un test complémentaire
- get_session_state : lit l'état de session
- save_test_run : sauvegarde un run terminé

Règles de comportement :
1. Tu réponds toujours en français.
2. Tu restes direct, technique, utile.
3. Si l'utilisateur dit "teste cet agent" ou "teste l'agent X", tu dois :
   - vérifier/sélectionner l'agent sous test,
   - construire le scénario,
   - exécuter l'agent sous test,
   - faire juger le résultat,
   - sauvegarder le run,
   - puis restituer un bilan.
4. Après un test terminé, tu dois repasser en mode attente utilisateur.
5. Tu dois explicitement proposer des suites possibles :
   - test plus strict
   - cas ambigu
   - robustesse
   - comparaison
   - nouvelle variante
6. Si l'utilisateur demande un test complémentaire, tu dois t'appuyer sur l'état de session et l'historique récent.
7. Ne fais pas de blabla.
8. Quand c'est pertinent, commence par lire l'état de session.

Quand tu rends un résultat final de test, utilise cette structure :

RÉSUMÉ:
<résumé court>

STATUT:
<PASS | FAIL | PARTIAL | INFO>

AGENT_SOUS_TEST:
<agent_id ou label>

DÉTAILS:
<points importants>

OPTIONS_SUIVANTES:
- <option 1>
- <option 2>
- <option 3>
""",
        model=build_model(stream=True),
        formatter=OllamaChatFormatter(),
        toolkit=toolkit,
    )


# =============================================================================
# Streaming helpers
# =============================================================================

async def stream_agent_reply(agent: ReActAgent, user_input: str) -> Optional[str]:
    final_text: Optional[str] = None

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(Msg("user", user_input, "user")),
    ):
        text = msg.get_text_content()
        if not text:
            continue

        final_text = text
        print("\rOrchestrator > " + text, end="", flush=True)

        if last:
            print()

    return final_text


# =============================================================================
# CLI
# =============================================================================

HELP_TEXT = """
Commandes utiles :
- /help
- /exit
- /agents
- /state
- /examples
"""

EXAMPLES_TEXT = """
Exemples :
1. liste les agents testables
2. sélectionne l'agent summary_agent
3. teste cet agent sur un cas COMEX cybersécurité
4. fais un test complémentaire plus sévère
5. propose un edge case
6. rejoue le dernier test avec des critères plus stricts
7. teste identity_resolution_agent sur un cas d'homonymie
"""


async def main() -> None:
    orchestrator = build_orchestrator()

    print("Mode interactif OrchestratorAgent")
    print(HELP_TEXT)

    while True:
        try:
            user_input = input("Toi > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nFin de session.")
            break

        if not user_input:
            continue

        normalized = user_input.lower()

        if normalized in {"/exit", "/quit", "exit", "quit"}:
            print("Fin de session.")
            break

        if normalized == "/help":
            print(HELP_TEXT)
            continue

        if normalized == "/examples":
            print(EXAMPLES_TEXT)
            continue

        if normalized == "/agents":
            print("\nAgents testables :")
            print(get_agent_registry_text())
            print()
            continue

        if normalized == "/state":
            print("\nÉtat de session :")
            print(SESSION.to_summary_text())
            print()
            continue

        SESSION.current_status = "running"
        await stream_agent_reply(orchestrator, user_input)
        print()


if __name__ == "__main__":
    asyncio.run(main())