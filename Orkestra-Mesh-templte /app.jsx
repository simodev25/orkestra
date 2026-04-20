;(function(){
/* App shell that assembles everything */

const { AGENTS } = window.OrkestraData;
const { Filters, StatRow, RegistryTable, applyFilters } = window.RegistryList;

function App() {
  const tweaks = useTweaksWiring();

  const [filters, setFilters] = React.useState({
    q: "",
    family: "all",
    status: "all",
    criticality: "all",
    cost_profile: "all",
  });

  const [selectedId, setSelectedId] = React.useState(() => {
    try { return localStorage.getItem("ork_selected") || "agent_retriever_docs"; }
    catch { return "agent_retriever_docs"; }
  });

  React.useEffect(() => {
    try { localStorage.setItem("ork_selected", selectedId); } catch {}
  }, [selectedId]);

  const filtered = React.useMemo(() => applyFilters(AGENTS, filters), [filters]);
  const selected = AGENTS.find(a => a.id === selectedId) || filtered[0] || AGENTS[0];

  return (
    <div className="app" data-screen-label="01 Agent Registry">
      <Sidebar activeHref="/agents" />
      <main className="main">
        <Topbar />
        <div className="page animate-fade-in">
          <Filters filters={filters} setFilters={setFilters} onGenerate={() => alert("AI generation flow (mock)")} />
          <StatRow agents={AGENTS} />
          <div className="split">
            <RegistryTable agents={filtered} selectedId={selected?.id} onSelect={setSelectedId} />
            <DetailPane agent={selected} />
          </div>
        </div>
      </main>

      <TweaksPanel state={tweaks.state} setState={tweaks.setState} open={tweaks.open} onClose={() => tweaks.setOpen(false)} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

})();