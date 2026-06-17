// Top-level routes. Left nav is always visible via AppLayout (Outlet).
// Routes are flat and self-describing — this is the fix for the legacy
// "everything hidden in collapsible panels" IA.
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReportPage } from "./pages/ReportPage";
import { RunPage } from "./pages/RunPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkspacePage } from "./pages/WorkspacePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<RunPage />} />
          <Route path="/projects/:projectId/files" element={<WorkspacePage />} />
          <Route path="/projects/:projectId/files/*" element={<WorkspacePage />} />
          <Route path="/projects/:projectId/report" element={<ReportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<ProjectsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
