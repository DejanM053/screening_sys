import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/", label: "Queue" },
  { to: "/mobile", label: "Mobile Approval" },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-60 flex-shrink-0 flex-col border-r border-slate-700 bg-surface">
      <div className="border-b border-slate-700 px-4 py-4">
        <div className="text-lg font-bold text-text-primary">Compliance Engine</div>
        <div className="text-xs text-text-secondary">Sanctions Screening</div>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `rounded px-3 py-2 text-sm font-medium ${
                isActive ? "bg-accent/20 text-accent" : "text-text-secondary hover:bg-bg hover:text-text-primary"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto border-t border-slate-700 p-3 text-xs text-text-secondary">
        <div className="font-semibold text-text-primary">Analyst</div>
        <div>analyst@sokin.example</div>
        <div className="mt-1 inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-green-500" /> Available
        </div>
      </div>
    </aside>
  );
}
