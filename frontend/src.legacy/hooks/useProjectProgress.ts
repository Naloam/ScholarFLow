import { useEffect } from "react";

import { API_BASE_URL, getAuthToken } from "../api/client";
import type { ProjectProgressSnapshot } from "../api/types";
import { useWorkspaceStore } from "../stores/workspace";

function getProgressUrl(projectId: string): string {
  const base = new URL(API_BASE_URL);
  const protocol = base.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL(
    `${protocol}//${base.host}/ws/projects/${projectId}/progress`,
  );
  const token = getAuthToken();
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function useProjectProgress() {
  const currentProjectId = useWorkspaceStore((state) => state.currentProjectId);
  const applyProgressSnapshot = useWorkspaceStore(
    (state) => state.applyProgressSnapshot,
  );
  const setConnectionState = useWorkspaceStore(
    (state) => state.setConnectionState,
  );
  const refreshProject = useWorkspaceStore((state) => state.refreshProject);

  useEffect(() => {
    if (!currentProjectId) {
      setConnectionState("disconnected");
      return;
    }

    let active = true;
    let socket: WebSocket | null = null;
    let fallbackTimer: number | null = null;
    let reconnectTimer: number | null = null;
    let reconnectAttempt = 0;

    const clearFallback = () => {
      if (fallbackTimer !== null) {
        window.clearInterval(fallbackTimer);
        fallbackTimer = null;
      }
    };

    const startFallback = () => {
      if (fallbackTimer !== null) {
        return;
      }
      fallbackTimer = window.setInterval(() => {
        void refreshProject();
      }, 10000);
    };

    const scheduleReconnect = () => {
      if (!active || reconnectTimer !== null) {
        return;
      }
      const delay = Math.min(1000 * 2 ** reconnectAttempt, 10000);
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        reconnectAttempt += 1;
        connect();
      }, delay);
    };

    const connect = () => {
      if (!active) {
        return;
      }

      setConnectionState("connecting");
      const nextSocket = new WebSocket(getProgressUrl(currentProjectId));
      socket = nextSocket;

      nextSocket.onopen = () => {
        if (!active || socket !== nextSocket) {
          return;
        }
        reconnectAttempt = 0;
        clearFallback();
        setConnectionState("live");
      };

      nextSocket.onmessage = (event) => {
        if (!active || socket !== nextSocket) {
          return;
        }
        const payload = JSON.parse(event.data) as
          | ProjectProgressSnapshot
          | { error: string };
        if ("error" in payload) {
          setConnectionState("disconnected");
          startFallback();
          return;
        }
        applyProgressSnapshot(payload);
      };

      nextSocket.onerror = () => {
        if (!active || socket !== nextSocket) {
          return;
        }
        nextSocket.close();
      };

      nextSocket.onclose = () => {
        if (!active || socket !== nextSocket) {
          return;
        }
        setConnectionState("disconnected");
        startFallback();
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      active = false;
      clearFallback();
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [
    applyProgressSnapshot,
    currentProjectId,
    refreshProject,
    setConnectionState,
  ]);
}
