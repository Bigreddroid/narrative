import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import TopBar from "./TopBar.jsx";

export default function AppShell({ children }) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg-base">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-hidden relative">
          {children || <Outlet />}
        </main>
      </div>
    </div>
  );
}
