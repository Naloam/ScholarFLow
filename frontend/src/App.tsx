// Top-level routes. Left nav is always visible via AppLayout (Outlet).
// Routes are flat and self-describing — this is the fix for the legacy
// "everything hidden in collapsible panels" IA.
//
// Uses a data router (createBrowserRouter) so V3's PaperEditor can call
// useBlocker (unsaved-changes navigation guard). BrowserRouter would throw
// "useBlocker must be used within a data router" and crash the ReportPage.
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReportPage } from "./pages/ReportPage";
import { RunPage } from "./pages/RunPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkspacePage } from "./pages/WorkspacePage";

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <ProjectsPage /> },
      { path: "/projects/:projectId", element: <RunPage /> },
      { path: "/projects/:projectId/files", element: <WorkspacePage /> },
      { path: "/projects/:projectId/files/*", element: <WorkspacePage /> },
      { path: "/projects/:projectId/report", element: <ReportPage /> },
      { path: "/settings", element: <SettingsPage /> },
      { path: "*", element: <ProjectsPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
