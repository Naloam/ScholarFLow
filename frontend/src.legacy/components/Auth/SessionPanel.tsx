import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { AuthConfig, AuthUser } from "../../api/types";

type AuthState = "checking" | "anonymous" | "user" | "service";

type SessionPanelProps = {
  authConfig: AuthConfig | null;
  authState: AuthState;
  authUser: AuthUser | null;
  authBusy: boolean;
  authError: string;
  workspaceBusy: boolean;
  onSignIn: (payload: {
    email: string;
    name: string;
    role: "student" | "tutor";
  }) => Promise<void>;
  onSignOut: () => Promise<void>;
};

function getStatusLabel(
  authState: AuthState,
  authConfig: AuthConfig | null,
  t: (key: string) => string,
): string {
  if (authState === "checking") {
    return t("session.checking");
  }
  if (authState === "user") {
    return t("session.signedIn");
  }
  if (authState === "service") {
    return t("session.serviceToken");
  }
  if (authConfig?.api_protected) {
    return authConfig.session_enabled
      ? t("session.signinRequired")
      : t("session.tokenRequired");
  }
  return t("session.anonymous");
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
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<"student" | "tutor">("student");
  const openWorkspace = !authConfig?.api_protected;
  const locked =
    Boolean(authConfig?.api_protected) && authState === "anonymous";
  const canSubmit =
    !authBusy &&
    !workspaceBusy &&
    Boolean(email.trim()) &&
    Boolean(authConfig?.session_enabled);

  return (
    <section className="panel" data-testid="auth-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("session.eyebrow")}</p>
          <h2 className="panel-title">{t("session.title")}</h2>
        </div>
        <span className="badge badge-soft" data-testid="auth-mode-chip">
          {getStatusLabel(authState, authConfig, t)}
        </span>
      </div>

      <div className="auth-meta-grid">
        <div className="auth-meta-card">
          <span className="meta-label">{t("session.workspaceMode")}</span>
          <strong>
            {authConfig?.api_protected
              ? t("session.protectedApi")
              : t("session.openApi")}
          </strong>
        </div>
        <div className="auth-meta-card">
          <span className="meta-label">{t("session.sessionLogin")}</span>
          <strong>
            {authConfig?.session_enabled
              ? t("session.enabled")
              : t("session.unavailable")}
          </strong>
        </div>
      </div>

      {authUser ? (
        <div className="inline-card">
          <p className="inline-title">{t("session.activeUser")}</p>
          <strong data-testid="auth-user-email">{authUser.email}</strong>
          <p className="auth-copy">
            {authUser.name || t("session.unnamedUser")} · {authUser.role}
          </p>
          <div className="button-row">
            <button
              className="ghost-btn"
              data-testid="auth-signout-button"
              disabled={authBusy || workspaceBusy}
              onClick={() => void onSignOut()}
            >
              {t("session.signOut")}
            </button>
          </div>
        </div>
      ) : (
        <>
          {authState === "service" ? (
            <div className="inline-card">
              <p className="inline-title">{t("session.serviceTokenActive")}</p>
              <p className="auth-copy">{t("session.serviceTokenCopy")}</p>
            </div>
          ) : null}

          <div className={locked ? "inline-card auth-locked" : "inline-card"}>
            <p className="inline-title">
              {locked
                ? authConfig?.session_enabled
                  ? t("session.lockedSessionTitle")
                  : t("session.lockedTokenTitle")
                : openWorkspace
                  ? t("session.openAccessTitle")
                  : t("session.createSessionTitle")}
            </p>
            <p className="auth-copy">
              {openWorkspace && !authConfig?.session_enabled
                ? t("session.openAccessCopy")
                : authConfig?.session_enabled
                  ? t("session.lockedSessionCopy")
                  : t("session.lockedTokenCopy")}
            </p>

            <label className="field">
              <span className="field-label">{t("session.emailLabel")}</span>
              <input
                id="auth-email-input"
                name="auth_email"
                data-testid="auth-email-input"
                disabled={
                  authBusy || workspaceBusy || !authConfig?.session_enabled
                }
                placeholder="student@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>

            <label className="field">
              <span className="field-label">{t("session.nameLabel")}</span>
              <input
                id="auth-name-input"
                name="auth_name"
                data-testid="auth-name-input"
                disabled={
                  authBusy || workspaceBusy || !authConfig?.session_enabled
                }
                placeholder={t("session.namePlaceholder")}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>

            <label className="field">
              <span className="field-label">{t("session.roleLabel")}</span>
              <select
                id="auth-role-select"
                name="auth_role"
                data-testid="auth-role-select"
                disabled={
                  authBusy || workspaceBusy || !authConfig?.session_enabled
                }
                value={role}
                onChange={(event) =>
                  setRole(event.target.value as "student" | "tutor")
                }
              >
                <option value="student">{t("session.student")}</option>
                <option value="tutor">{t("session.tutor")}</option>
              </select>
            </label>

            <div className="button-row">
              <button
                className="primary-btn"
                data-testid="auth-submit-button"
                disabled={!canSubmit}
                onClick={() => void onSignIn({ email, name, role })}
              >
                {t("session.signIn")}
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
