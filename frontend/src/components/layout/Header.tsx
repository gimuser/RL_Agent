import { useApi } from "../../hooks/useApi";
import { dashboardService } from "../../services/dashboard.service";
import { StatusBadge } from "../ui/StatusBadge";

export function Header({ onMenu }: { onMenu: () => void }) {
  const system = useApi(dashboardService.getSystemHealth, { poll: true });
  const database = useApi(dashboardService.getDatabaseHealth, { poll: true });
  const apiStatus = system.data?.status === "ok" ? "online" : system.error ? "offline" : "unknown";
  const dbStatus = database.data?.status ?? (database.error ? "offline" : "unknown");

  return (
    <header className="topbar">
      <button className="menu-button" type="button" aria-label="Open navigation" onClick={onMenu}>☰</button>
      <div className="topbar__crumb">
        <span className="topbar__eyebrow">SYSTEM STATUS</span>
        <div className="topbar__statuses">
          <StatusBadge value={`API ${apiStatus}`} />
          <StatusBadge value={`Database ${dbStatus}`} />
        </div>
      </div>
      <div className="topbar__right">
        <button className="icon-button" aria-label="Notifications" type="button">
          <span aria-hidden="true">♧</span>
          <span className="notification-dot" />
        </button>
        <div className="profile" aria-label="Signed in analyst">
          <div className="profile__avatar">SA</div>
          <div>
            <strong>SOC Analyst</strong>
            <span>Supervision</span>
          </div>
        </div>
      </div>
    </header>
  );
}
