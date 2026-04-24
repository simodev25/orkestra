;(function(){
/* Agent Registry list page — filters + stats + table */

const { AGENTS, FAMILIES, MCP_CATALOG } = window.OrkestraData;

function StatCard({ label, value, delta, accent = "cyan", pct = 75 }) {
  return (
    <div className={`stat stat--${accent}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__row">
        <span className="stat-value stat__value">{value}</span>
        {delta && <span className="stat__delta">{delta}</span>}
      </div>
      <div className="stat__bar"><span style={{ width: pct + "%" }} /></div>
    </div>
  );
}

function StatRow({ agents }) {
  const total = agents.length;
  const active      = agents.filter(a => a.status === "active").length;
  const tested      = agents.filter(a => ["tested", "registered", "active"].includes(a.status)).length;
  const deprecated  = agents.filter(a => a.status === "deprecated").length;
  const inPipeline  = agents.filter(a => a.pipeline_agent_ids && a.pipeline_agent_ids.length > 0).length;
  return (
    <div className="stats">
      <StatCard label="Agents actifs"        value={active}     accent="green"  delta={`/ ${total} total`}  pct={(active / total) * 100} />
      <StatCard label="Agents testés"        value={tested}     accent="cyan"   delta="includes registered + active" pct={(tested / total) * 100} />
      <StatCard label="Agents dépréciés"     value={deprecated} accent="amber"  delta="archive candidates" pct={(deprecated / total) * 100 + 5} />
      <StatCard label="Agents workflow courant" value={inPipeline} accent="purple" delta="used in pipelines"  pct={(inPipeline / total) * 100} />
    </div>
  );
}

function Filters({ filters, setFilters, onGenerate }) {
  function update(k, v) { setFilters({ ...filters, [k]: v }); }
  return (
    <>
      <div className="pagehead">
        <div>
          <h1>Agent Registry</h1>
          <p>
            Governed registry of specialized agents with mission, MCP permissions, contracts,
            lifecycle, and reliability metadata.
          </p>
        </div>
        <div className="pagehead__actions">
          <button className="btn btn--cyan"><Icon name="plus" size={12} /> Add Agent</button>
          <button className="btn btn--purple" onClick={onGenerate}>
            <Icon name="sparkles" size={12} /> Generate Agent with AI
          </button>
        </div>
      </div>

      <div className="glass-panel filters">
        <div className="fieldwrap" style={{ gridColumn: "span 2" }}>
          <Icon name="search" size={13} />
          <input
            className="field"
            placeholder="search name, id, purpose, skill"
            value={filters.q}
            onChange={e => update("q", e.target.value)}
          />
        </div>
        <select className="field" value={filters.family}      onChange={e => update("family", e.target.value)}>
          <option value="all">family: all</option>
          {FAMILIES.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
        <select className="field" value={filters.status}      onChange={e => update("status", e.target.value)}>
          <option value="all">status: all</option>
          <option value="draft">draft</option>
          <option value="designed">designed</option>
          <option value="tested">tested</option>
          <option value="registered">registered</option>
          <option value="active">active</option>
          <option value="deprecated">deprecated</option>
          <option value="disabled">disabled</option>
          <option value="archived">archived</option>
        </select>
        <select className="field" value={filters.criticality} onChange={e => update("criticality", e.target.value)}>
          <option value="all">criticality: all</option>
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
          <option value="critical">critical</option>
        </select>
        <select className="field" value={filters.cost_profile} onChange={e => update("cost_profile", e.target.value)}>
          <option value="all">cost_profile: all</option>
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
          <option value="variable">variable</option>
        </select>
      </div>
    </>
  );
}

function RegistryTable({ agents, selectedId, onSelect }) {
  if (agents.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: 48, textAlign: "center" }}>
        <p className="mono dim" style={{ fontSize: 12 }}>No agents match these filters.</p>
      </div>
    );
  }
  return (
    <div className="tablewrap">
      <table className="table">
        <thead>
          <tr>
            <th>name</th>
            <th>agent_id</th>
            <th>family</th>
            <th>purpose</th>
            <th>skills</th>
            <th>mcps</th>
            <th>crit.</th>
            <th>cost</th>
            <th>version</th>
            <th>status</th>
            <th>last test</th>
          </tr>
        </thead>
        <tbody>
          {agents.map(a => (
            <tr
              key={a.id}
              className={a.id === selectedId ? "is-selected" : ""}
              onClick={() => onSelect(a.id)}
            >
              <td className="col-name">
                {a.name}
                <span className="sub">owner · {a.owner || "—"}</span>
              </td>
              <td className="col-id">{a.id}</td>
              <td className="col-fam">{a.family_id}</td>
              <td style={{ maxWidth: 240 }}>
                <span style={{
                  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
                  overflow: "hidden", textOverflow: "ellipsis",
                }}>{a.purpose}</span>
              </td>
              <td>{(a.skill_ids || []).length}</td>
              <td>{(a.allowed_mcps || []).length}</td>
              <td><span className={`crit crit--${a.criticality}`}>{a.criticality}</span></td>
              <td>{a.cost_profile}</td>
              <td className="cyan">{a.version}</td>
              <td><StatusBadge status={a.status} /></td>
              <td><TestBadge status={a.last_test_status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="tablefoot">
        <span>{agents.length} agents · page 1 of 1</span>
        <div className="tablefoot__pager">
          <button className="pagerbtn">‹</button>
          <button className="pagerbtn" aria-current="true">1</button>
          <button className="pagerbtn">›</button>
        </div>
      </div>
    </div>
  );
}

function applyFilters(agents, f) {
  const q = (f.q || "").toLowerCase().trim();
  return agents.filter(a => {
    if (f.family      !== "all" && a.family_id   !== f.family)      return false;
    if (f.status      !== "all" && a.status      !== f.status)      return false;
    if (f.criticality !== "all" && a.criticality !== f.criticality) return false;
    if (f.cost_profile !== "all" && a.cost_profile !== f.cost_profile) return false;
    if (q) {
      const hay = [a.name, a.id, a.purpose, ...(a.skill_ids || [])].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

window.RegistryList = {
  Filters, StatRow, RegistryTable, applyFilters,
};

})();