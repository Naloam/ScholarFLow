import { useState } from "react";

import type {
  AuthUser,
  MentorAccessEntry,
  MentorFeedbackEntry,
} from "../../api/types";
import { formatDate } from "../../utils/format";

type MentorPanelProps = {
  projectId: string;
  projectOwnerId?: string | null;
  selectedDraftVersion: number | null;
  authUser: AuthUser | null;
  mentorAccess: MentorAccessEntry[];
  mentorFeedback: MentorFeedbackEntry[];
  disabled: boolean;
  onInvite: (payload: { email: string; name: string }) => Promise<void>;
  onSubmitFeedback: (payload: {
    draft_version?: number | null;
    summary: string;
    strengths: string;
    concerns: string;
    next_steps: string;
  }) => Promise<void>;
};

export function MentorPanel({
  projectId,
  projectOwnerId,
  selectedDraftVersion,
  authUser,
  mentorAccess,
  mentorFeedback,
  disabled,
  onInvite,
  onSubmitFeedback,
}: MentorPanelProps) {
  const [mentorEmail, setMentorEmail] = useState("mentor@example.com");
  const [mentorName, setMentorName] = useState("Supervisor");
  const [summary, setSummary] = useState("The draft already has a workable structure and clear scope.");
  const [strengths, setStrengths] = useState("The introduction and related work sections are easy to follow.");
  const [concerns, setConcerns] = useState("Evidence support is still thin around the central claims.");
  const [nextSteps, setNextSteps] = useState("Add stronger citations for the core argument and tighten the method section.");
  const isOwner = Boolean(authUser?.id && projectOwnerId && authUser.id === projectOwnerId);
  const canInvite = Boolean(projectId) && isOwner && !disabled && mentorEmail.trim().includes("@");
  const canReview =
    Boolean(projectId) &&
    !isOwner &&
    authUser?.role === "tutor" &&
    !disabled &&
    summary.trim().length >= 4 &&
    strengths.trim().length >= 4 &&
    concerns.trim().length >= 4 &&
    nextSteps.trim().length >= 4;

  return (
    <section className="panel" data-testid="mentor-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Phase 7 Collaboration</p>
          <h2 className="panel-title">Mentor Panel</h2>
        </div>
        <span className="badge badge-soft" data-testid="mentor-access-count">
          {mentorAccess.length} mentors
        </span>
      </div>

      {!projectId ? (
        <div className="empty-state">
          <p>No project selected.</p>
          <span>Open a project before inviting a mentor or writing mentor feedback.</span>
        </div>
      ) : null}

      {projectId && isOwner ? (
        <div className="inline-card">
          <p className="inline-title">Invite a mentor</p>
          <label className="field">
            <span className="field-label">Mentor email</span>
            <input
              id="mentor-email-input"
              name="mentor_email"
              data-testid="mentor-email-input"
              disabled={disabled}
              value={mentorEmail}
              onChange={(event) => setMentorEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Display name</span>
            <input
              id="mentor-name-input"
              name="mentor_name"
              data-testid="mentor-name-input"
              disabled={disabled}
              value={mentorName}
              onChange={(event) => setMentorName(event.target.value)}
            />
          </label>
          <div className="button-row">
            <button
              className="primary-btn"
              data-testid="mentor-invite-button"
              disabled={!canInvite}
              onClick={() => void onInvite({ email: mentorEmail, name: mentorName })}
            >
              Invite Mentor
            </button>
          </div>
        </div>
      ) : null}

      {projectId && canReview ? (
        <div className="inline-card">
          <p className="inline-title">Submit mentor review</p>
          <p className="auth-copy">
            Reviewing draft version {selectedDraftVersion ?? "latest"} in read-only mentor mode.
          </p>
          <label className="field">
            <span className="field-label">Summary</span>
            <textarea
              id="mentor-summary-input"
              name="mentor_summary"
              data-testid="mentor-summary-input"
              rows={2}
              disabled={disabled}
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Strengths</span>
            <textarea
              id="mentor-strengths-input"
              name="mentor_strengths"
              data-testid="mentor-strengths-input"
              rows={2}
              disabled={disabled}
              value={strengths}
              onChange={(event) => setStrengths(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Concerns</span>
            <textarea
              id="mentor-concerns-input"
              name="mentor_concerns"
              data-testid="mentor-concerns-input"
              rows={2}
              disabled={disabled}
              value={concerns}
              onChange={(event) => setConcerns(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Next steps</span>
            <textarea
              id="mentor-next-steps-input"
              name="mentor_next_steps"
              data-testid="mentor-next-steps-input"
              rows={2}
              disabled={disabled}
              value={nextSteps}
              onChange={(event) => setNextSteps(event.target.value)}
            />
          </label>
          <div className="button-row">
            <button
              className="primary-btn"
              data-testid="mentor-submit-feedback-button"
              disabled={!canReview}
              onClick={() =>
                void onSubmitFeedback({
                  draft_version: selectedDraftVersion,
                  summary,
                  strengths,
                  concerns,
                  next_steps: nextSteps,
                })
              }
            >
              Submit Mentor Feedback
            </button>
          </div>
        </div>
      ) : null}

      <div className="stack">
        <div className="inline-card">
          <p className="inline-title">Granted mentors</p>
          {mentorAccess.length === 0 ? (
            <p className="auth-copy">No mentor access granted for this project yet.</p>
          ) : (
            <div className="stack">
              {mentorAccess.map((entry, index) => (
                <article
                  key={entry.id}
                  className="feedback-card"
                  data-testid={index === 0 ? "mentor-access-card" : undefined}
                >
                  <strong>{entry.mentor_name || entry.mentor_email}</strong>
                  <p>{entry.mentor_email}</p>
                  <small>{formatDate(entry.created_at)} · {entry.status}</small>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="inline-card">
          <p className="inline-title">Mentor feedback log</p>
          {mentorFeedback.length === 0 ? (
            <p className="auth-copy">No mentor feedback submitted yet.</p>
          ) : (
            <div className="stack">
              {mentorFeedback.map((entry, index) => (
                <article
                  key={entry.id}
                  className="feedback-card"
                  data-testid={index === 0 ? "mentor-feedback-card" : undefined}
                >
                  <strong>{entry.mentor_name || entry.mentor_email}</strong>
                  <p>{entry.summary}</p>
                  <p>
                    <strong>Strengths:</strong> {entry.strengths}
                  </p>
                  <p>
                    <strong>Concerns:</strong> {entry.concerns}
                  </p>
                  <p>
                    <strong>Next:</strong> {entry.next_steps}
                  </p>
                  <small>
                    Draft v{entry.draft_version ?? "latest"} · {formatDate(entry.created_at)}
                  </small>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
