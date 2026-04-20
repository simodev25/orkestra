;(function(){
/* Tabs used inside the detail pane */

function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs">
      {tabs.map(t => (
        <button
          key={t.id}
          className={`tabs__btn ${active === t.id ? "tabs__btn--active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.icon && <Icon name={t.icon} size={12} />}
          {t.label}
          {t.count != null && <span className="count">({t.count})</span>}
        </button>
      ))}
    </div>
  );
}

window.Tabs = Tabs;

})();