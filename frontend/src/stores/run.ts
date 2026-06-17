// Run store: status + timeline for a single project run.
// Polling cadence is driven from the RunPage component; this store only owns
// state + fetch actions.
import { create } from "zustand";

import { getStatus, getTimeline } from "../api/client";
import type { RunStatus, TimelineEntry } from "../api/types";

interface RunState {
  projectId: string | null;
  status: RunStatus | null;
  timeline: TimelineEntry[];
  loading: boolean;
  error: string | null;
  load: (projectId: string) => Promise<void>;
  refresh: (projectId: string) => Promise<void>;
  reset: () => void;
}

export const useRunStore = create<RunState>((set) => ({
  projectId: null,
  status: null,
  timeline: [],
  loading: false,
  error: null,

  load: async (projectId) => {
    set({ projectId, loading: true, error: null });
    try {
      const [status, timeline] = await Promise.all([
        getStatus(projectId),
        getTimeline(projectId),
      ]);
      set({ status, timeline, loading: false });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Failed to load run",
      });
    }
  },

  refresh: async (projectId) => {
    try {
      const [status, timeline] = await Promise.all([
        getStatus(projectId),
        getTimeline(projectId),
      ]);
      set({ projectId, status, timeline });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to refresh run",
      });
    }
  },

  reset: () => {
    set({ projectId: null, status: null, timeline: [], loading: false, error: null });
  },
}));
