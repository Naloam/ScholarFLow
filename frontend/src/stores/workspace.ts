// Workspace store: selected file path + its content for a project.
import { create } from "zustand";

import { getFile } from "../api/client";

interface WorkspaceState {
  projectId: string | null;
  selectedPath: string;
  content: string;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  selectFile: (projectId: string, path: string) => Promise<void>;
  reset: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  projectId: null,
  selectedPath: "research_report.md",
  content: "",
  loading: false,
  notFound: false,
  error: null,

  selectFile: async (projectId, path) => {
    set({ projectId, selectedPath: path, loading: true, notFound: false, error: null, content: "" });
    try {
      const content = await getFile(projectId, path);
      set({ content, loading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to read file";
      const status = (err as { status?: number }).status;
      set({
        loading: false,
        notFound: status === 404,
        // 404 is expected for not-yet-generated files — not a hard error.
        error: status === 404 ? null : message,
      });
    }
  },

  reset: () => {
    set({
      projectId: null,
      selectedPath: "research_report.md",
      content: "",
      loading: false,
      notFound: false,
      error: null,
    });
  },
}));
