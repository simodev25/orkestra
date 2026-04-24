;(function(){
/* Tweaks panel. Controls density, accent hue, promotion-path style, and a "show operational" toggle. */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density": "normal",
  "accent": "#00d4ff",
  "promopathStyle": "default",
  "showOperationalFilter": true
}/*EDITMODE-END*/;

const ACCENTS = [
  { v: "#00d4ff", label: "cyan (default)" },
  { v: "#a78bfa", label: "purple" },
  { v: "#10b981", label: "green" },
  { v: "#f59e0b", label: "amber" },
  { v: "#ef4444", label: "red" },
];

function TweaksPanel({ state, setState, open, onClose }) {
  if (!open) return null;
  return (
    <div className="tweaks animate-slide-up">
      <div className="tweaks__head">
        <div className="tweaks__title">Tweaks</div>
        <button className="tweaks__close" onClick={onClose}><Icon name="x" size={14} /></button>
      </div>

      <div className="tweaks__row">
        <label>Density</label>
        <select className="field" value={state.density} onChange={e => setState({ ...state, density: e.target.value })}>
          <option value="compact">compact</option>
          <option value="normal">normal</option>
          <option value="roomy">roomy</option>
        </select>
      </div>

      <div className="tweaks__row">
        <label>Accent hue</label>
        <div className="swatches">
          {ACCENTS.map(a => (
            <div
              key={a.v}
              className="swatch"
              style={{ background: a.v }}
              aria-pressed={state.accent === a.v}
              title={a.label}
              onClick={() => setState({ ...state, accent: a.v })}
            />
          ))}
        </div>
      </div>

      <div className="tweaks__row">
        <label>Promotion path</label>
        <select
          className="field"
          value={state.promopathStyle}
          onChange={e => setState({ ...state, promopathStyle: e.target.value })}
        >
          <option value="default">Filled circles</option>
          <option value="rail">Rail (hollow)</option>
          <option value="classic">Classic (square current)</option>
        </select>
      </div>

      <div className="tweaks__row">
        <label>Show operational</label>
        <input
          type="checkbox"
          checked={state.showOperationalFilter}
          onChange={e => setState({ ...state, showOperationalFilter: e.target.checked })}
        />
      </div>

      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "var(--ork-dim)", marginTop: 10, paddingTop: 8, borderTop: "1px dashed var(--ork-border)" }}>
        Toggle "Tweaks" in the toolbar to show/hide.
      </div>
    </div>
  );
}

function useTweaksWiring() {
  const [state, setState] = React.useState(TWEAK_DEFAULTS);
  const [open,  setOpen]  = React.useState(false);

  // Apply side effects
  React.useEffect(() => {
    document.documentElement.style.setProperty("--accent", state.accent);
    document.body.classList.remove("density-compact", "density-normal", "density-roomy");
    document.body.classList.add(`density-${state.density}`);
    window.__ORK_STYLE__ = state.promopathStyle;
  }, [state]);

  React.useEffect(() => {
    function onMsg(ev) {
      const d = ev.data || {};
      if (d.type === "__activate_edit_mode")   setOpen(true);
      if (d.type === "__deactivate_edit_mode") setOpen(false);
    }
    window.addEventListener("message", onMsg);
    try { window.parent.postMessage({ type: "__edit_mode_available" }, "*"); } catch {}
    return () => window.removeEventListener("message", onMsg);
  }, []);

  function commit(next) {
    setState(next);
    try { window.parent.postMessage({ type: "__edit_mode_set_keys", edits: next }, "*"); } catch {}
  }

  return { state, setState: commit, open, setOpen };
}

window.TweaksPanel = TweaksPanel;
window.useTweaksWiring = useTweaksWiring;

})();