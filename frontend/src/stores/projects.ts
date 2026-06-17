// Projects store: list of research-harness workspaces + "New run" creation.
import { create } from "zustand";

import { listProjects, startRun } from "../api/client";
import type { ProjectSummary } from "../api/types";

interface ProjectsState {
  projects: ProjectSummary[];
  loading: boolean;
  error: string | null;
  creating: boolean;
  loadProjects: () => Promise<void>;
  createRun: (idea: string) => Promise<string>;
}

function newProjectId(): string {
  // Mirror the backend default scheme: v0_<8 hex>.
  const rand = Math.random().toString(16).slice(2, 10);
  return `v0_${rand}`;
}

export const useProjectsStore = create<ProjectsState>((set, get) => ({
  projects: [],
  loading: false,
  error: null,
  creating: false,

  loadProjects: async () => {
    set({ loading: true, error: null });
    try {
      const projects = await listProjects();
      set({ projects, loading: false });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Failed to load projects",
      });
    }
  },

  createRun: async (idea) => {
    set({ creating: true, error: null });
    try {
      const projectId = newProjectId();
      const result = await startRun(projectId, { idea, steps: "all" });
      // Optimistically insert so the Projects list reflects the new run immediately.
      const optimistic: ProjectSummary = {
        project_id: result.project_id,
        idea,
        status: "running",
        steps_done: [],
        last_ts: new Date().toISOString(),
      };
      set({ projects: [optimistic, ...get().projects], creating: false });
      return result.project_id;
    } catch (err) {
      set({
        creating: false,
        error: err instanceof Error ? err.message : "Failed to start run",
      });
      throw err;
    }
  },
}));
