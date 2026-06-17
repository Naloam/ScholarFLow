import { useEffect } from "react";

import { WorkspacePage } from "./pages/WorkspacePage";
import { useProjectProgress } from "./hooks/useProjectProgress";
import { useWorkspaceStore } from "./stores/workspace";

export default function App() {
  const bootstrap = useWorkspaceStore((state) => state.bootstrap);
  useProjectProgress();

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return <WorkspacePage />;
}
