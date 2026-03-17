import { useState } from "react";

import type { AuthConfig, AuthUser } from "../../api/types";

type AuthState = "checking" | "anonymous" | "user" | "service";

type SessionPanelProps = {
  authConfig: AuthConfig | null;
  authState: AuthState;
  authUser: AuthUser | null;
  authBusy: boolean;
  authError: string;
  workspaceBusy: boolean;
  onSignIn: (payload: { email: string; name: string }) => Promise<void>;
  onSignOut: () => Promise<void>;
};

function getStatusLabel(authState: AuthState, authConfig: AuthConfig | null): string {
  if (authState === "checking") {
    return "Checking";
  }
  if (authState === "user") {
    return "Signed in";
  }
  if (authState === "service") {
    return "Service token";
  }
  if (authConfig?.auth_required) {
    return "Sign-in required";
  }
  return "Anonymous";
}

export function SessionPanel({
  authConfig,
  authState,
  authUser,
  authBusy,
  authError,
  workspaceBusy,
  onSignIn,
  onSignOut,
}: SessionPanelProps) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const locked = Boolean(authConfig?.auth_required) && authState === "anonymous";
  const canSubmit =
    !authBusy && !workspaceBusy && Boolean(email.trim()) && Boolean(authConfig?.session_enabled);

  return (
    <section className="panel" data-testid="auth-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Access Control</p>
          <h2 className="panel-title">Session</h2>
        </div>
        <span className="badge badge-soft" data-testid="auth-mode-chip">
          {getStatusLabel(authState, authConfig)}
        </span>
      </div>

      <div className="auth-meta-grid">
        <div className="auth-meta-card">
          <span className="meta-label">Workspace mode</span>
          <strong>{authConfig?.auth_required ? "Protected API" : "Open API"}</strong>
        </div>
        <div className="auth-meta-card">
          <span className="meta-label">Session login</span>
          <strong>{authConfig?.session_enabled ? "Enabled" : "Unavailable"}</strong>
        </div>
      </div>

      {authUser ? (
        <div className="inline-card">
          <p className="inline-title">Active user</p>
          <strong data-testid="auth-user-email">{authUser.email}</strong>
          <p className="auth-copy">
            {authUser.name || "Unnamed user"} · {authUser.role}
          </p>
          <div className="button-row">
            <button
              className="ghost-btn"
              data-testid="auth-signout-button"
              disabled={authBusy || workspaceBusy}
              onClick={() => void onSignOut()}
            >
              Sign out
            </button>
          </div>
        </div>
      ) : (
        <>
          {authState === "service" ? (
            <div className="inline-card">
              <p className="inline-title">Service token active</p>
              <p className="auth-copy">
                Requests already carry a configured bearer token. You can still create a user
                session below if you want project ownership and user-level audit trails.
              </p>
            </div>
          ) : null}

          <div className={locked ? "inline-card auth-locked" : "inline-card"}>
            <p className="inline-title">
              {locked ? "Sign in to unlock the workspace" : "Create a session"}
            </p>
            <p className="auth-copy">
              {authConfig?.session_enabled
                ? "Use an email-based session so new projects are linked to your user identity."
                : "This server does not expose session login. Configure AUTH_SECRET or provide a bearer token."}
            </p>

            <label className="field">
              <span className="field-label">Email</span>
              <input
                data-testid="auth-email-input"
                disabled={authBusy || workspaceBusy || !authConfig?.session_enabled}
                placeholder="student@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label className="field">
              <span className="field-label">Display name</span>
              <input
                data-testid="auth-name-input"
                disabled={authBusy || workspaceBusy || !authConfig?.session_enabled}
                placeholder="Optional"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>

            <div className="button-row">
              <button
                className="primary-btn"
                data-testid="auth-submit-button"
                disabled={!canSubmit}
                onClick={() => void onSignIn({ email, name })}
              >
                Sign in
              </button>
            </div>
          </div>
        </>
      )}

      {authError ? (
        <p className="auth-error" data-testid="auth-error">
          {authError}
        </p>
      ) : null}
    </section>
  );
}
