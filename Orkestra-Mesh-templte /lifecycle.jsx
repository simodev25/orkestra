;(function(){
/* Promotion path + transition gate — mirrors the 5-step lib/agent-lifecycle model */

const { MAIN_PATH, MAIN_LABELS, GATES } = window.OrkestraData;

const OPERATIONAL = ["deprecated", "disabled", "archived"];

function getSteps(status) {
  const idx = MAIN_PATH.indexOf(status);
  const effective = idx < 0 ? MAIN_PATH.length : idx;
  return MAIN_PATH.map((step, i) => {
    let state = "locked";
    if (i < effective) state = "done";
    else if (i === effective && idx >= 0) state = "current";
    return { step, state, label: MAIN_LABELS[step] };
  });
}

function getGate(from, to) {
  return GATES.find(g => g.from === from && g.to === to) || null;
}

// Same blockers rules as helpers.ts getLifecycleBlockers
function getBlockers(agent, target) {
  const blockers = [];
  if (!agent.prompt_ref && !agent.prompt_content) {
    blockers.push({ key: "prompt_missing", label: "Prompt reference or content is missing", severity: "error" });
  }
  if (!agent.skill_ids || agent.skill_ids.length === 0) {
    blockers.push({ key: "skills_missing", label: "No skills assigned to this agent", severity: "warning" });
  }
  if (target === "designed") {
    if (!agent.purpose)   blockers.push({ key: "purpose_missing", label: "Agent purpose is not defined", severity: "error" });
    if (!agent.family_id) blockers.push({ key: "family_missing",  label: "Agent family is not assigned", severity: "error" });
  }
  if (target === "tested") {
    if (!agent.last_test_status || agent.last_test_status === "not_tested")
      blockers.push({ key: "test_not_executed", label: "Test pack not executed", severity: "error" });
    if (agent.last_test_status === "failed")
      blockers.push({ key: "test_failed", label: "Last test run failed", severity: "error" });
  }
  if (target === "registered") {
    if (!agent.input_contract_ref)  blockers.push({ key: "input_contract_missing",  label: "Input contract reference is missing",  severity: "warning" });
    if (!agent.output_contract_ref) blockers.push({ key: "output_contract_missing", label: "Output contract reference is missing", severity: "warning" });
  }
  if (target === "active") {
    if (!agent.llm_provider || !agent.llm_model)
      blockers.push({ key: "llm_config_missing", label: "LLM provider or model not configured", severity: "warning" });
  }
  return blockers;
}

function nextMain(status) {
  const idx = MAIN_PATH.indexOf(status);
  if (idx < 0 || idx >= MAIN_PATH.length - 1) return null;
  return MAIN_PATH[idx + 1];
}

function PromotionPath({ agent, style = "default" }) {
  const steps = getSteps(agent.status);
  const isOperational = OPERATIONAL.includes(agent.status);
  return (
    <div className="glass-panel promotion">
      <div className="promotion__head" style={{ padding: "0 14px" }}>
        <span className="section-title">Promotion path</span>
        <span className="dim mono" style={{ fontSize: 10.5 }}>
          {isOperational ? `operational · ${agent.status}` : `current · ${agent.status}`}
        </span>
      </div>
      <div className={`promopath promopath--${style}`} style={{ padding: "0 14px 10px" }}>
        {steps.map((s, i) => {
          const dotCls = `promopath__dot promopath__dot--${s.state}`;
          const labCls = `promopath__label promopath__label--${s.state}`;
          const gate = i > 0 ? getGate(steps[i - 1].step, s.step) : null;
          const doneLine = i > 0 && steps[i - 1].state === "done";
          return (
            <React.Fragment key={s.step}>
              {i > 0 && (
                <div className="promopath__connector">
                  <div className={`promopath__line ${doneLine ? "promopath__line--done" : ""}`} />
                  {gate && <div className="promopath__gate">{gate.title}</div>}
                </div>
              )}
              <div className="promopath__step">
                <div className={dotCls}>
                  {s.state === "done"    && <Icon name="check" size={14} strokeWidth={2.5} />}
                  {s.state === "current" && <Icon name="circle" size={10} />}
                  {s.state === "locked"  && <Icon name="lock" size={11} />}
                </div>
                <span className={labCls}>{s.label}</span>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      {/* Operational states — visible only if the agent is operational */}
      {isOperational && (
        <div className="opstates" style={{ padding: "0 14px 14px" }}>
          <span className="section-title" style={{ alignSelf: "center" }}>Operational state</span>
          <StatusBadge status={agent.status} />
          <span className="dim mono" style={{ fontSize: 10.5, alignSelf: "center" }}>
            — main path retained for provenance
          </span>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  return <span className={`badge badge--${status}`}>{(status || "").replace(/_/g, " ")}</span>;
}

function TestBadge({ status }) {
  return <span className={`badge badge--${status || "not_tested"}`}>{(status || "not_tested").replace(/_/g, " ")}</span>;
}

function TransitionGate({ agent, onPromote }) {
  const target = nextMain(agent.status);
  if (!target) {
    // active / operational have no forward gate
    return (
      <div className="gate">
        <div className="gate__head">
          <h3 className="gate__title">No forward transition</h3>
          <span className="gate__flow">
            <span>{agent.status}</span>
            <Icon name="arrow-r" size={11} />
            <span className="dim">—</span>
          </span>
        </div>
        <p className="gate__desc">
          {agent.status === "active"
            ? "Agent is active. Use Admin → Deprecate / Disable to move into an operational state."
            : "Agent is in an operational state. It must be restored to active before further promotion."}
        </p>
      </div>
    );
  }
  const gate = getGate(agent.status, target);
  const blockers = getBlockers(agent, target);
  const errors = blockers.filter(b => b.severity === "error");
  const canPromote = errors.length === 0;

  return (
    <div className="gate">
      <div className="gate__head">
        <div>
          <h3 className="gate__title">Gate · {gate.title}</h3>
          <div className="gate__flow">
            <span>{agent.status}</span>
            <Icon name="arrow-r" size={11} />
            <span className="to">{target}</span>
          </div>
        </div>
        <StatusBadge status={canPromote ? "ready" : "hold"} />
      </div>
      <p className="gate__desc">{gate.description}</p>

      <div className="gate__blockers">
        {blockers.length === 0 ? (
          <div className="blocker blocker--ok">
            <Icon name="check" size={13} />
            All preconditions satisfied.
          </div>
        ) : (
          blockers.map(b => (
            <div key={b.key} className={`blocker blocker--${b.severity}`}>
              <Icon name={b.severity === "error" ? "alert" : "info"} size={13} />
              {b.label}
            </div>
          ))
        )}
      </div>

      <div className="gate__foot">
        <button className="btn btn--ghost">Re-run qualification</button>
        <button
          className={`btn ${canPromote ? "btn--cyan" : ""}`}
          disabled={!canPromote}
          onClick={() => canPromote && onPromote && onPromote(target)}
          style={!canPromote ? { opacity: 0.45, cursor: "not-allowed" } : null}
        >
          Promote to {target}
        </button>
      </div>
    </div>
  );
}

window.PromotionPath    = PromotionPath;
window.TransitionGate   = TransitionGate;
window.StatusBadge      = StatusBadge;
window.TestBadge        = TestBadge;
window.lifecycleHelpers = { getSteps, getGate, getBlockers, nextMain };

})();