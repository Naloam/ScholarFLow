// Settings: auth (sign-in / bearer) + read-only LLM config (model + api base;
// the key is never shown). Keeps the user oriented about which model a run uses.
import { useEffect, useState } from "react";

import { getHarnessConfig, type HarnessConfig } from "../api/client";
import { ErrorState } from "../components/States";
import { Spinner } from "../components/Spinner";
import { useAuthStore } from "../stores/auth";

export function SettingsPage() {
  const { config, user, token, bootstrap, signIn, signOut } = useAuthStore();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [harness, setHarness] = useState<HarnessConfig | null>(null);
  const [harnessError, setHarnessError] = useState<string | null>(null);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    getHarnessConfig()
      .then(setHarness)
      .catch((err: unknown) =>
        setHarnessError(err instanceof Error ? err.message : "Failed to load LLM config"),
      );
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim()) {
      return;
    }
    try {
      await signIn(email.trim(), name.trim() || undefined);
      setEmail("");
      setName("");
    } catch {
      // surfaced via store
    }
  }

  const authProtected = config?.api_protected ?? false;

  return (
    <div className="page page--settings">
      <header className="page__head">
        <div>
          <h1 className="page__title">Settings</h1>
          <p className="page__subtitle">Authentication and model configuration.</p>
        </div>
      </header>

      <section className="settings__block">
        <h2 className="section__title">Authentication</h2>
        {user ? (
          <div className="authstate">
            <div>
              Signed in as <strong>{user.email}</strong>
              {user.name ? ` (${user.name})` : null}
            </div>
            <button type="button" className="btn btn--ghost" onClick={signOut}>
              Sign out
            </button>
          </div>
        ) : config?.session_enabled ? (
          <form className="authform" onSubmit={handleSubmit}>
            <input
              className="input"
              type="email"
              placeholder="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <input
              className="input"
              type="text"
              placeholder="name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button type="submit" className="btn btn--primary">Sign in</button>
          </form>
        ) : (
          <p className="muted">
            Session auth is not enabled on the server.
            {authProtected ? " The API is protected — provide a bearer token via VITE_API_TOKEN." : null}
          </p>
        )}
        {token ? <p className="muted">A bearer token is stored in this browser.</p> : null}
      </section>

      <section className="settings__block">
        <h2 className="section__title">LLM configuration (read-only)</h2>
        {harnessError ? <ErrorState message={harnessError} /> : null}
        {!harness && !harnessError ? <Spinner label="Loading config…" /> : null}
        {harness ? (
          <dl className="configlist">
            <div className="configlist__row">
              <dt>Model</dt>
              <dd><code>{harness.llm_model}</code></dd>
            </div>
            <div className="configlist__row">
              <dt>Writer model</dt>
              <dd><code>{harness.llm_writer_model}</code></dd>
            </div>
            <div className="configlist__row">
              <dt>API base</dt>
              <dd><code>{harness.llm_api_base}</code></dd>
            </div>
            <div className="configlist__row">
              <dt>Sandbox</dt>
              <dd><code>{harness.sandbox_backend}</code></dd>
            </div>
            <div className="configlist__row">
              <dt>API key</dt>
              <dd className="muted">hidden — never exposed to the client</dd>
            </div>
          </dl>
        ) : null}
      </section>
    </div>
  );
}
