import { useState } from "react";

import type { TemplateMeta } from "../../api/types";

type ProjectLauncherProps = {
  templates: TemplateMeta[];
  currentProjectId: string;
  healthStatus: string;
  working: boolean;
  onCreate: (payload: { title: string; topic: string; templateId: string }) => Promise<void>;
  onOpen: (projectId: string) => Promise<void>;
};

export function ProjectLauncher({
  templates,
  currentProjectId,
  healthStatus,
  working,
  onCreate,
  onOpen,
}: ProjectLauncherProps) {
  const [title, setTitle] = useState("Undergraduate Thesis Workspace");
  const [topic, setTopic] = useState("Graph neural networks in recommender systems");
  const [templateId, setTemplateId] = useState("builtin:general_paper");
  const [existingProjectId, setExistingProjectId] = useState("");

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 5 Bootstrap</p>
          <h2 className="panel-title">Project Launcher</h2>
        </div>
        <span className={`badge ${healthStatus === "ok" ? "badge-ok" : "badge-warn"}`}>
          API {healthStatus}
        </span>
      </div>

      <label className="field">
        <span className="field-label">Project title</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>

      <label className="field">
        <span className="field-label">Topic</span>
        <textarea
          rows={3}
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
        />
      </label>

      <label className="field">
        <span className="field-label">Template</span>
        <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
          <option value="">No template</option>
          {templates.map((template) => (
            <option key={template.id ?? template.name} value={template.id ?? ""}>
              {template.name}
            </option>
          ))}
        </select>
      </label>

      <div className="button-row">
        <button
          className="primary-btn"
          disabled={working}
          onClick={() => void onCreate({ title, topic, templateId })}
        >
          Create Project
        </button>
      </div>

      <div className="inline-card">
        <p className="inline-title">Open existing project</p>
        <div className="inline-row">
          <input
            placeholder="Paste project id"
            value={existingProjectId}
            onChange={(event) => setExistingProjectId(event.target.value)}
          />
          <button
            className="ghost-btn"
            disabled={working || !existingProjectId.trim()}
            onClick={() => void onOpen(existingProjectId.trim())}
          >
            Open
          </button>
        </div>
      </div>

      <div className="meta-block">
        <span className="meta-label">Current project</span>
        <code>{currentProjectId || "Not selected"}</code>
      </div>
    </section>
  );
}
