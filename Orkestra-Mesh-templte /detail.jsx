;(function(){
/* Detail pane — mirrors frontend/src/app/agents/[id]/page.tsx */

const mcpByIdMap = Object.fromEntries(window.OrkestraData.MCP_CATALOG.map(m => [m.id, m]));

function KV({ k, v, mono }) {
  return (
    <>
      <span className="k">{k}</span>
      <span className={`v ${mono ? "mono" : ""}`}>{v ?? "—"}</span>
    </>
  );
}

function Block({ title, action, children }) {
  return (
    <section className="block">
      <div className="block__title">
        <span className="section-title">{title}</span>
        {action}
      </div>
      {children}
    </section>
  );
}

function DetailHeader({ agent, onClose }) {
  return (
    <div className="detail__head">
      <div className="detail__idrow">
        <span className="detail__id">{agent.id}</span>
        <span className="dim mono" style={{ fontSize: 11 }}>· v{agent.version}</span>
        <span className="right">
          <StatusBadge status={agent.status} />
        </span>
      </div>
      <h2 className="detail__name">{agent.name}</h2>
      <p className="detail__purpose">{agent.purpose}</p>
      <div className="detail__meta">
        <span className="chip"><Icon name="bot" size={11} /> family · {agent.family_id}</span>
        <span className="chip"><Icon name="shield" size={11} /> {agent.criticality}</span>
        <span className="chip">cost · {agent.cost_profile}</span>
        <span className="chip">llm · {agent.llm_model}</span>
        <span className="chip"><Icon name="clock" size={11} /> {agent.usage_count.toLocaleString()} runs</span>
      </div>
      <div className="row" style={{ marginTop: 14, gap: 8 }}>
        <button className="btn btn--cyan"><Icon name="flask" size={12} /> Test Lab</button>
        <button className="btn btn--purple">Edit</button>
        <button className="btn"><Icon name="history" size={12} /> History</button>
        <button className="btn btn--red" style={{ marginLeft: "auto" }}>Delete</button>
      </div>
    </div>
  );
}

function DetailsTab({ agent }) {
  const isOrch = agent.family_id === "orchestration";
  const mcps = agent.allowed_mcps || [];
  const forbidden = agent.forbidden_effects || [];
  const skills = agent.skills_resolved || [];
  return (
    <div className="tabpane">
      {/* Lifecycle */}
      <PromotionPath agent={agent} style={window.__ORK_STYLE__ || "default"} />
      <TransitionGate agent={agent} onPromote={(target) => {
        alert(`Promoted ${agent.name} → ${target} (mock)`);
      }} />

      {/* Identity */}
      <Block title="Identity">
        <div className="kv">
          <KV k="name"      v={agent.name} />
          <KV k="agent_id"  v={agent.id}      mono />
          <KV k="family_id" v={agent.family_id} mono />
          <KV k="version"   v={agent.version}  mono />
          <KV k="owner"     v={agent.owner}    mono />
          <KV k="updated"   v={new Date(agent.updated_at).toLocaleString()} mono />
        </div>
      </Block>

      {/* Mission */}
      <Block title="Mission / Description">
        <div className="kv">
          <KV k="purpose"     v={agent.purpose} />
          <KV k="description" v={agent.description || "—"} />
        </div>
      </Block>

      {/* Skills */}
      <Block title={`Skills (${skills.length})`}>
        {skills.length === 0 ? (
          <p className="dim mono" style={{ fontSize: 11.5 }}>No skills assigned.</p>
        ) : (
          <div>
            {skills.map(s => (
              <div key={s.skill_id} className="skill">
                <span className="skill__id">{s.skill_id}</span>
                <span className="skill__label">{s.label}</span>
                <span className="skill__cat">[{s.category}]</span>
              </div>
            ))}
          </div>
        )}
      </Block>

      {/* Selection hints */}
      <Block title="Selection hints">
        <pre className="codebox codebox--muted">{JSON.stringify(agent.selection_hints || {}, null, 2)}</pre>
      </Block>

      {/* Pipeline OR MCP permissions */}
      {isOrch ? (
        <Block
          title="Pipeline d'agents"
          action={
            <span className={`routing routing--${agent.routing_mode || "sequential"}`}>
              {(agent.routing_mode || "sequential") === "dynamic" ? "Dynamique (LLM choisit)" : "Séquentiel (ordre fixe)"}
            </span>
          }
        >
          {(agent.pipeline_agent_ids || []).length === 0 ? (
            <p className="dim mono" style={{ fontSize: 11.5 }}>No agents in pipeline.</p>
          ) : (
            <div className="pipe">
              {agent.pipeline_agent_ids.map((id, i) => (
                <div key={id} className="pipe__row">
                  <span className="pipe__idx">{i + 1}</span>
                  <span className="pipe__id">{id}</span>
                  <span className="pipe__link">voir →</span>
                </div>
              ))}
            </div>
          )}
        </Block>
      ) : (
        <Block title={`MCP permissions (${mcps.length})`}>
          {mcps.length === 0 ? (
            <p className="dim mono" style={{ fontSize: 11.5 }}>No allowed MCPs configured.</p>
          ) : (
            <div>
              {mcps.map(id => {
                const m = mcpByIdMap[id];
                return (
                  <div key={id} className="mcprow">
                    <Icon name="wrench" size={14} style={{ color: "var(--ork-muted)" }} />
                    <div>
                      <div><span className="mcprow__name">{m ? m.name : id}</span>  <span className="mcprow__id">{id}</span></div>
                      <div className="mcprow__meta">
                        {m && <span className="mcprow__effect">{m.effect_type}</span>}
                        {m && <StatusBadge status={m.orkestra_state} />}
                        {m && m.approval_required && <span className="chip chip--mini" style={{ color: "var(--ork-amber)" }}>approval</span>}
                      </div>
                    </div>
                    <Icon name="chevron" size={12} style={{ color: "var(--ork-dim)" }} />
                  </div>
                );
              })}
            </div>
          )}
          {forbidden.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="section-title" style={{ marginBottom: 6 }}>forbidden_effects</div>
              <div className="forbidden">
                {forbidden.map(e => <span key={e} className="forbidden__item">{e}</span>)}
              </div>
            </div>
          )}
        </Block>
      )}

      {/* Contracts */}
      <Block title="Contracts">
        <div className="kv">
          <KV k="input_contract_ref"  v={agent.input_contract_ref  || "—"} mono />
          <KV k="output_contract_ref" v={agent.output_contract_ref || "—"} mono />
        </div>
      </Block>

      {/* Prompt */}
      <Block title="Prompt" action={<span className="chip chip--mini">{agent.prompt_ref || "no ref"}</span>}>
        <pre className="codebox">{agent.prompt_content || "—"}</pre>
      </Block>

      {/* Skills file */}
      {agent.skills_content && (
        <Block title="Skills file" action={<span className="chip chip--mini">{agent.skills_ref || "no ref"}</span>}>
          <pre className="codebox codebox--muted">{agent.skills_content}</pre>
        </Block>
      )}

      {/* Limitations */}
      <Block title="Limitations">
        {agent.limitations && agent.limitations.length > 0 ? (
          <div className="forbidden">
            {agent.limitations.map((l, i) => (
              <span key={i} className="forbidden__item" style={{ color: "var(--ork-amber)", background: "color-mix(in oklch, var(--ork-amber) 10%, transparent)", borderColor: "color-mix(in oklch, var(--ork-amber) 20%, transparent)" }}>{l}</span>
            ))}
          </div>
        ) : <p className="dim mono" style={{ fontSize: 11.5 }}>—</p>}
      </Block>

      {/* Reliability / tests */}
      <Block title="Reliability / Tests">
        <div className="kv">
          <span className="k">last_test_status</span>
          <span className="v"><TestBadge status={agent.last_test_status} /></span>
          <KV k="last_validated_at" v={agent.last_validated_at ? new Date(agent.last_validated_at).toLocaleString() : "—"} mono />
        </div>
      </Block>

      {/* Usage metadata */}
      <Block title="Usage metadata">
        <div className="kv">
          <KV k="usage_count" v={agent.usage_count.toLocaleString()} mono />
          <KV k="criticality" v={agent.criticality} />
          <KV k="cost_profile" v={agent.cost_profile} />
          <KV k="llm_provider" v={agent.llm_provider} mono />
          <KV k="llm_model" v={agent.llm_model} mono />
          <KV k="allow_code_execution" v={String(agent.allow_code_execution)} mono />
          <KV k="created_at" v={new Date(agent.created_at).toLocaleString()} mono />
        </div>
      </Block>
    </div>
  );
}

function ChatTab({ agent }) {
  const storageKey = `chat_${agent.id}`;
  const [messages, setMessages] = React.useState(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? JSON.parse(saved) : (window.OrkestraData.SAMPLE_CHAT || []);
    } catch { return window.OrkestraData.SAMPLE_CHAT || []; }
  });
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const bottomRef = React.useRef(null);

  React.useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(messages)); } catch {}
    bottomRef.current && bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function send() {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages(m => [...m, { role: "user", content: text }]);
    setLoading(true);
    setTimeout(() => {
      setMessages(m => [...m, {
        role: "agent",
        content: `Ack — "${text.slice(0, 60)}${text.length > 60 ? "…" : ""}". Mock response from ${agent.name}. In production this calls /api/agents/${agent.id}/chat.`,
        tool_calls: [{ tool_name: "mock_tool" }],
        duration_ms: 430 + Math.floor(Math.random() * 800),
      }]);
      setLoading(false);
    }, 700);
  }

  return (
    <div className="tabpane" style={{ padding: 0 }}>
      <div className="chat glass-panel" style={{ margin: 16, borderRadius: 6 }}>
        <div className="chat__scroll">
          {messages.length === 0 && (
            <div className="chat__empty">
              Parle directement à <span style={{ color: "var(--accent)" }}>{agent.name}</span>.<br />
              <em>Pas de scénario, pas de scoring — conversation brute.</em>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`chat__row ${m.role === "user" ? "u" : "a"}`}>
              <div className={`chat__bubble ${m.role === "user" ? "u" : "a"}`}>
                <div className={`chat__who ${m.role === "user" ? "u" : "a"}`}>
                  {m.role === "user" ? "you" : agent.name}
                  {m.duration_ms && <span className="dim" style={{ marginLeft: 8 }}>{m.duration_ms}ms</span>}
                </div>
                <div>{m.content}</div>
                {m.tool_calls && m.tool_calls.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    {m.tool_calls.map((tc, j) => (
                      <span key={j} className="chat__toolchip">{tc.tool_name}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat__row a">
              <div className="chat__bubble a">
                <div className="thinking"><span className="dot" /><span className="dot" /><span className="dot" /> {agent.name} is thinking…</div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div className="chat__input">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder={`Message ${agent.name}… (Enter to send)`}
            rows={1}
          />
          <button className="btn btn--cyan" onClick={send} disabled={loading || !input.trim()}>
            <Icon name="send" size={12} /> Send
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailPane({ agent }) {
  const [tab, setTab] = React.useState("details");
  if (!agent) {
    return (
      <div className="detail" style={{ padding: 24, textAlign: "center" }}>
        <p className="mono dim" style={{ fontSize: 12 }}>Select an agent to inspect.</p>
      </div>
    );
  }
  return (
    <div className="detail">
      <DetailHeader agent={agent} />
      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "details", label: "Details",     icon: "file" },
          { id: "chat",    label: "Chat direct", icon: "message" },
        ]}
      />
      {tab === "details" && <DetailsTab agent={agent} />}
      {tab === "chat"    && <ChatTab    agent={agent} />}
    </div>
  );
}

window.DetailPane = DetailPane;

})();