// Auth store: session/bearer token + auth config + current user.
// Migrated (and slimmed) from the legacy SessionPanel — nothing else from the
// old workspace store is carried over.
import { create } from "zustand";

import {
  createSession,
  getAuthConfig,
  getStoredAuthToken,
  storeAuthToken,
} from "../api/client";
import type { AuthConfig, AuthUser } from "../api/types";

interface AuthState {
  config: AuthConfig | null;
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  bootstrap: () => Promise<void>;
  signIn: (email: string, name?: string) => Promise<void>;
  signOut: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  config: null,
  user: null,
  token: getStoredAuthToken(),
  loading: false,
  error: null,

  bootstrap: async () => {
    set({ loading: true, error: null });
    try {
      const config = await getAuthConfig();
      set({ config, loading: false });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Failed to load auth config",
      });
    }
  },

  signIn: async (email, name) => {
    set({ loading: true, error: null });
    try {
      const session = await createSession(email, name);
      storeAuthToken(session.access_token);
      set({
        token: session.access_token,
        user: session.user,
        loading: false,
      });
    } catch (err) {
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Sign-in failed",
      });
      throw err;
    }
  },

  signOut: () => {
    storeAuthToken(null);
    set({ token: null, user: null });
  },
}));
