;(function(){
/* Sidebar + topbar. Nav mirrors frontend/src/components/layout/sidebar.tsx */

const NAV = [
  { label: "Dashboard",       href: "/",                          icon: "activity", group: null },
  { label: "Agents",          href: "/agents",                    icon: "bot",      group: "Registries", badge: "10" },
  { label: "Orchestrateurs",  href: "/agents/orchestrators/new",  icon: "bot",      group: null },
  { label: "Families",        href: "/agents/families",           icon: "bot",      group: null, badge: "6" },
  { label: "Agent Skills",    href: "/agents/skills",             icon: "bot",      group: null, badge: "11" },
  { label: "Test Lab",        href: "/test-lab",                  icon: "flask",    group: null },
  { label: "Test Lab Config", href: "/test-lab/config",           icon: "sliders",  group: null },
  { label: "MCP Catalog",     href: "/mcps",                      icon: "wrench",   group: null, badge: "10" },
  { label: "Admin",           href: "/admin",                     icon: "settings", group: "Configuration" },
];

function Sidebar({ activeHref = "/agents" }) {
  const grouped = [];
  let current = null;
  for (const item of NAV) {
    if (item.group) { current = item.group; grouped.push({ section: item.group }); }
    grouped.push(item);
  }
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">O</div>
        <div>
          <h1 className="sidebar__title">ORKESTRA</h1>
          <p className="sidebar__subtitle">ORCHESTRATION</p>
        </div>
      </div>
      <nav className="sidebar__nav">
        {grouped.map((item, i) => {
          if (item.section) {
            return <p key={`s${i}`} className="sidebar__section">{item.section}</p>;
          }
          const active = item.href === activeHref;
          return (
            <div
              key={item.label}
              className={`navlink ${active ? "navlink--active" : ""}`}
            >
              <Icon name={item.icon} size={14} strokeWidth={active ? 2 : 1.5} />
              <span>{item.label}</span>
              {item.badge && <span className="navlink__badge">{item.badge}</span>}
            </div>
          );
        })}
      </nav>
      <div className="sidebar__foot">v0.1.0 — Phase 1</div>
    </aside>
  );
}

function Topbar() {
  return (
    <div className="topbar">
      <div className="topbar__crumbs">
        <span>orkestra</span>
        <Icon name="chevron" size={11} />
        <span>registries</span>
        <Icon name="chevron" size={11} />
        <strong>agents</strong>
      </div>
      <div className="topbar__right">
        <div className="topbar__health">
          <span className="glow-dot" />
          api · healthy
        </div>
        <button className="topbar__btn"><Icon name="refresh" size={12} /> refresh</button>
        <button className="topbar__btn"><Icon name="cpu" size={12} /> env · local</button>
      </div>
    </div>
  );
}

window.Sidebar = Sidebar;
window.Topbar = Topbar;

})();