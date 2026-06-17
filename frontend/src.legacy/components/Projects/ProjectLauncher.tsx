import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ProjectListItem, TemplateMeta } from "../../api/types";

type ProjectLauncherProps = {
  templates: TemplateMeta[];
  currentProjectId: string;
  availableProjects: ProjectListItem[];
  healthStatus: string;
  working: boolean;
  authLocked: boolean;
  onCreate: (payload: {
    title: string;
    topic: string;
    templateId: string;
  }) => Promise<void>;
  onOpen: (projectId: string) => Promise<void>;
};

export function ProjectLauncher({
  templates,
  currentProjectId,
  availableProjects,
  healthStatus,
  working,
  authLocked,
  onCreate,
  onOpen,
}: ProjectLauncherProps) {
  const { t } = useTranslation();
  const [title, setTitle] = useState("Undergraduate Thesis Workspace");
  const [topic, setTopic] = useState(
    "Graph neural networks in recommender systems",
  );
  const [templateId, setTemplateId] = useState("builtin:general_paper");
  const [existingProjectId, setExistingProjectId] = useState("");

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{t("project.eyebrow")}</p>
          <h2 className="panel-title">{t("project.title")}</h2>
        </div>
        <span
          className={`badge ${healthStatus === "ok" ? "badge-ok" : "badge-warn"}`}
        >
          {healthStatus === "ok" ? t("project.apiOk") : t("project.apiWarn")}
        </span>
      </div>

      <label className="field">
        <span className="field-label">{t("project.projectTitle")}</span>
        <input
          id="project-title-input"
          name="project_title"
          data-testid="project-title-input"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>

      <label className="field">
        <span className="field-label">{t("project.topic")}</span>
        <textarea
          id="project-topic-input"
          name="project_topic"
          data-testid="project-topic-input"
          rows={3}
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
        />
      </label>

      <label className="field">
        <span className="field-label">{t("project.template")}</span>
        <select
          id="project-template-select"
          name="project_template"
          data-testid="project-template-select"
          value={templateId}
          onChange={(event) => setTemplateId(event.target.value)}
        >
          <option value="">{t("project.noTemplate")}</option>
          {templates.map((template) => (
            <option
              key={template.id ?? template.name}
              value={template.id ?? ""}
            >
              {template.name}
            </option>
          ))}
        </select>
      </label>

      <div className="button-row">
        <button
          className="primary-btn"
          data-testid="create-project-button"
          disabled={working || authLocked}
          onClick={() => void onCreate({ title, topic, templateId })}
        >
          {t("project.createProject")}
        </button>
      </div>

      {authLocked ? (
        <div
          className="inline-card auth-locked"
          data-testid="project-launcher-locked"
        >
          <p className="inline-title">{t("project.workspaceLocked")}</p>
          <p className="auth-copy">{t("project.workspaceLockedCopy")}</p>
        </div>
      ) : null}

      <div className="inline-card">
        <p className="inline-title">{t("project.openExisting")}</p>
        <div className="inline-row">
          <input
            id="open-project-input"
            name="open_project_id"
            data-testid="open-project-input"
            placeholder={t("project.pasteProjectId")}
            value={existingProjectId}
            onChange={(event) => setExistingProjectId(event.target.value)}
          />
          <button
            className="ghost-btn"
            data-testid="open-project-button"
            disabled={working || authLocked || !existingProjectId.trim()}
            onClick={() => void onOpen(existingProjectId.trim())}
          >
            {t("project.open")}
          </button>
        </div>
      </div>

      <div className="inline-card">
        <p className="inline-title">{t("project.accessibleProjects")}</p>
        {availableProjects.length === 0 ? (
          <p className="auth-copy">{t("project.noProjectsCopy")}</p>
        ) : (
          <div className="stack">
            {availableProjects.map((project, index) => {
              const isCurrent = project.id === currentProjectId;
              const accessLabel =
                project.access_mode === "mentor"
                  ? t("project.mentorReadonly")
                  : project.access_mode === "anonymous"
                    ? t("project.openWorkspace")
                    : t("project.projectOwner");
              return (
                <article
                  key={project.id}
                  className="feedback-card"
                  data-testid={
                    index === 0 ? "accessible-project-card" : undefined
                  }
                >
                  <div className="inline-row">
                    <strong>{project.title}</strong>
                    <span className="badge badge-soft">{accessLabel}</span>
                  </div>
                  <p>{project.topic || t("project.noTopic")}</p>
                  <small>{project.id}</small>
                  <div className="button-row">
                    <button
                      className={isCurrent ? "primary-btn" : "ghost-btn"}
                      disabled={working}
                      onClick={() => void onOpen(project.id)}
                    >
                      {isCurrent ? t("project.opened") : t("project.open")}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <div className="meta-block">
        <span className="meta-label">{t("project.currentProject")}</span>
        <code data-testid="current-project-id">
          {currentProjectId || t("project.notSelected")}
        </code>
      </div>
    </section>
  );
}
