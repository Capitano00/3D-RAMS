import { Search } from "lucide-react";

export default function EmptyState({ title = "No data yet", children, icon: Icon = Search }) {
  return (
    <div className="hud-empty-state">
      <Icon size={22} />
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
