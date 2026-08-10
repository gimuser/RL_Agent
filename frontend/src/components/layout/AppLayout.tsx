import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      <div className="app-shell__content">
        <Header onMenu={() => setMenuOpen(true)} />
        <main className="main-content"><Outlet /></main>
      </div>
    </div>
  );
}
