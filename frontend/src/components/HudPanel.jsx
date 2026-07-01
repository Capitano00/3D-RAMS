export default function HudPanel({ title, eyebrow, icon: Icon, rightSlot, children, className = "" }) {
  return (
    <section className={`hud-panel ${className}`}>
      <div className="hud-panel-header">
        <div>
          {eyebrow && <p className="hud-eyebrow">{eyebrow}</p>}
          <h2>
            {Icon && <Icon size={18} />}
            {title}
          </h2>
        </div>
        {rightSlot && <div className="hud-panel-right">{rightSlot}</div>}
      </div>
      {children}
    </section>
  );
}
