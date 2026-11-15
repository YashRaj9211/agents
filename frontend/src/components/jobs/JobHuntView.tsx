import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './JobHuntView.css';
import { Badge, Button } from '../common';
import {
  SearchIcon,
  RefreshIcon,
  TrashIcon,
  DownloadIcon,
  CheckIcon,
  GlobeIcon,
  SparkleIcon,
  FileIcon,
  PlayIcon,
} from '../icons/Icons';
import {
  fetchJobHunt,
  setJobStatus,
  deleteJob,
  loadSampleJobs,
  clearSampleJobs,
  getJobResumeUrl,
  type JobItem,
  type JobStats,
  type JobProfile,
  type JobStatus,
  type JobVerdict,
} from '../../services/api';
import { useChatStore } from '../../store';

const PARAM_LABELS: Record<string, string> = {
  skills: 'Skills',
  experience: 'Experience',
  role_fit: 'Role fit',
  location: 'Location',
  compensation: 'Compensation',
  growth: 'Growth',
  company: 'Company',
};

const VERDICT_LABEL: Record<JobVerdict, string> = {
  strong: 'Strong match',
  good: 'Good match',
  stretch: 'Stretch',
  skip: 'Low fit',
};

const STATUS_LABEL: Record<JobStatus, string> = {
  new: 'New',
  shortlisted: 'Shortlisted',
  tailored: 'Resume ready',
  applied: 'Applied',
  rejected: 'Rejected',
};

const PIPELINE_PROMPTS = {
  scout:
    'Scout about 100 jobs that fit my profile. Ask me for target roles, locations and which saved browser profile to use if you do not already know them. Save every posting you find.',
  match: 'Evaluate every unevaluated job against my profile, score each on all parameters and explain why.',
  tailor: 'Tailor a single-file HTML resume for each of my top 5 matching jobs that does not have one yet.',
  full: 'Run the full job hunt: scout about 100 jobs for me, match them to my profile, then tailor resumes for the top 5.',
};

const A4_WIDTH_PX = 794;

const scoreColor = (score: number): string => {
  if (score >= 80) return 'var(--jh-strong)';
  if (score >= 65) return 'var(--jh-good)';
  if (score >= 50) return 'var(--jh-stretch)';
  return 'var(--jh-skip)';
};

const ScoreRing: React.FC<{ score: number | null; size?: number }> = ({ score, size = 52 }) => {
  const stroke = size >= 80 ? 7 : 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = score == null ? 0 : score / 100;
  return (
    <div className="jh-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--jh-track)" strokeWidth={stroke} />
        {score != null && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={scoreColor(score)}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${c * pct} ${c}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        )}
      </svg>
      <span className="jh-ring-value" style={{ fontSize: size >= 80 ? 24 : 15 }}>
        {score == null ? '–' : score}
      </span>
    </div>
  );
};

const Stage: React.FC<{
  index: number;
  title: string;
  metric: string;
  hint: string;
  done: boolean;
  progress?: number;
  action: string;
  onAction: () => void;
}> = ({ index, title, metric, hint, done, progress, action, onAction }) => (
  <div className={`jh-stage ${done ? 'is-done' : ''}`}>
    <div className="jh-stage-top">
      <span className="jh-stage-index">{done ? <CheckIcon size={14} /> : index}</span>
      <span className="jh-stage-title">{title}</span>
    </div>
    <div className="jh-stage-metric">{metric}</div>
    <div className="jh-stage-hint">{hint}</div>
    {progress != null && (
      <div className="jh-stage-bar">
        <span style={{ width: `${Math.min(100, progress)}%` }} />
      </div>
    )}
    <button type="button" className="jh-stage-action" onClick={onAction}>
      <PlayIcon size={12} /> {action}
    </button>
  </div>
);

export const JobHuntView: React.FC = () => {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [stats, setStats] = useState<JobStats | null>(null);
  const [profile, setProfile] = useState<JobProfile>({});
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [verdict, setVerdict] = useState<'all' | JobVerdict>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | JobStatus>('all');
  const [showDescription, setShowDescription] = useState(false);
  const [resumeNonce, setResumeNonce] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const frameWrapRef = useRef<HTMLDivElement | null>(null);
  const [frameScale, setFrameScale] = useState(0.6);

  // The resume is a fixed A4 page (794px wide); scale it down to fit the preview pane.
  const bindFrameWrap = useCallback((node: HTMLDivElement | null) => {
    frameWrapRef.current = node;
    if (!node) return;
    const fit = () => setFrameScale(Math.min(1, node.clientWidth / A4_WIDTH_PX));
    fit();
    new ResizeObserver(fit).observe(node);
  }, []);

  const setActiveTab = useChatStore((s) => s.setActiveTab);
  const setSelectedAgentId = useChatStore((s) => s.setSelectedAgentId);
  const sendMessage = useChatStore((s) => s.sendMessage);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await fetchJobHunt();
      setJobs(data.jobs);
      setStats(data.stats);
      setProfile(data.profile || {});
      setWeights(data.weights || {});
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(() => load(true), 0);
    // Agents write in the background, so keep the board fresh while it is open.
    const timer = window.setInterval(() => load(true), 5000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return jobs.filter((j) => {
      if (verdict !== 'all' && j.evaluation?.verdict !== verdict) return false;
      if (statusFilter !== 'all' && j.status !== statusFilter) return false;
      if (!q) return true;
      return [j.title, j.company, j.location, j.source, ...(j.skills || [])].join(' ').toLowerCase().includes(q);
    });
  }, [jobs, search, verdict, statusFilter]);

  const selected = useMemo(
    () => jobs.find((j) => j.id === selectedId) ?? filtered[0] ?? null,
    [jobs, filtered, selectedId]
  );

  const runPrompt = (agentId: string, prompt: string) => {
    setSelectedAgentId(agentId);
    setActiveTab('orchestrator');
    void sendMessage(prompt);
  };

  const changeStatus = async (job: JobItem, status: JobStatus) => {
    setJobs((prev) => prev.map((j) => (j.id === job.id ? { ...j, status } : j)));
    try {
      await setJobStatus(job.id, status);
    } finally {
      load(true);
    }
  };

  const removeJob = async (job: JobItem) => {
    if (!window.confirm(`Remove "${job.title}" at ${job.company}?`)) return;
    await deleteJob(job.id);
    setSelectedId(null);
    load(true);
  };

  const hasSample = jobs.some((j) => j.source === 'sample');
  const total = stats?.total ?? 0;
  const evaluated = stats?.evaluated ?? 0;

  const printResume = () => {
    const win = iframeRef.current?.contentWindow;
    if (win) {
      win.focus();
      win.print();
    }
  };

  return (
    <div className="jh-root">
      <header className="jh-header">
        <div>
          <h1 className="jh-title">Job Hunt</h1>
          <p className="jh-subtitle">
            Scout jobs with your browser profile, rank them against your resume, and get a tailored one-page resume for the best fits.
          </p>
        </div>
        <div className="jh-header-actions">
          <Button variant="ghost" icon={<RefreshIcon size={14} />} onClick={() => load()}>
            Refresh
          </Button>
          {hasSample ? (
            <Button variant="secondary" onClick={() => clearSampleJobs().then(() => load())}>
              Clear sample data
            </Button>
          ) : (
            <Button variant="secondary" onClick={() => loadSampleJobs().then(() => load())}>
              Preview with sample data
            </Button>
          )}
          <Button variant="primary" icon={<SparkleIcon size={14} />} onClick={() => runPrompt('root_agent', PIPELINE_PROMPTS.full)}>
            Run full pipeline
          </Button>
        </div>
      </header>

      {hasSample && (
        <div className="jh-banner">Showing SAMPLE data so you can preview the dashboard. Real runs ignore and replace it.</div>
      )}
      {error && <div className="jh-banner jh-banner-error">{error}. Is the backend running?</div>}

      <section className="jh-pipeline" aria-label="Pipeline">
        <Stage
          index={1}
          title="Profile"
          metric={profile.name && !profile.sample ? profile.name : profile.sample ? 'Sample profile' : 'Not set'}
          hint={
            profile.target_roles?.length
              ? `Targeting ${profile.target_roles.slice(0, 2).join(', ')}`
              : 'Resume facts, target roles, locations'
          }
          done={Boolean(stats?.has_profile) && !profile.sample}
          action={stats?.has_profile ? 'Update profile' : 'Set up profile'}
          onAction={() =>
            runPrompt(
              'job_scout_agent',
              'Set up my candidate profile. Ask me for my resume (path or pasted text), target roles, locations, work mode and salary expectation, then save it.'
            )
          }
        />
        <Stage
          index={2}
          title="Scout"
          metric={`${total} / 100 jobs`}
          hint="Browser agent collects postings with your profile"
          done={total >= 100}
          progress={total}
          action="Scout jobs"
          onAction={() => runPrompt('job_scout_agent', PIPELINE_PROMPTS.scout)}
        />
        <Stage
          index={3}
          title="Match"
          metric={`${evaluated} / ${total} ranked`}
          hint={`${stats?.strong ?? 0} strong · ${stats?.good ?? 0} good matches`}
          done={total > 0 && evaluated === total}
          progress={total ? (evaluated / total) * 100 : 0}
          action="Rank jobs"
          onAction={() => runPrompt('job_matcher_agent', PIPELINE_PROMPTS.match)}
        />
        <Stage
          index={4}
          title="Tailor"
          metric={`${stats?.tailored ?? 0} ${stats?.tailored === 1 ? 'resume' : 'resumes'}`}
          hint="Single-file HTML/CSS, print-ready A4"
          done={(stats?.tailored ?? 0) >= 5}
          progress={((stats?.tailored ?? 0) / 5) * 100}
          action="Tailor top 5"
          onAction={() => runPrompt('resume_tailor_agent', PIPELINE_PROMPTS.tailor)}
        />
      </section>

      {total === 0 && !loading ? (
        <div className="jh-empty">
          <div className="jh-empty-icon">
            <GlobeIcon size={28} />
          </div>
          <h2>No jobs yet</h2>
          <p>
            Start with <b>Scout jobs</b>: the browser agent opens your saved profile on LinkedIn, Naukri and others, and saves what it finds
            here. Or preview the dashboard with sample data.
          </p>
          <div className="jh-empty-actions">
            <Button variant="primary" onClick={() => runPrompt('job_scout_agent', PIPELINE_PROMPTS.scout)}>
              Scout jobs
            </Button>
            <Button variant="secondary" onClick={() => loadSampleJobs().then(() => load())}>
              Preview with sample data
            </Button>
          </div>
        </div>
      ) : (
        <div className="jh-board">
          <div className="jh-list-col">
            <div className="jh-filters">
              <label className="jh-search">
                <SearchIcon size={14} />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title, company, skill…" />
              </label>
              <div className="jh-chips" role="tablist" aria-label="Match filter">
                {(['all', 'strong', 'good', 'stretch', 'skip'] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    className={`jh-chip ${verdict === v ? 'is-active' : ''}`}
                    onClick={() => setVerdict(v)}
                  >
                    {v === 'all' ? 'All' : VERDICT_LABEL[v]}
                  </button>
                ))}
              </div>
              <select
                className="jh-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | JobStatus)}
                aria-label="Filter by status"
              >
                <option value="all">Any status</option>
                {(Object.keys(STATUS_LABEL) as JobStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>

            <div className="jh-list">
              {filtered.length === 0 && <div className="jh-none">No jobs match these filters.</div>}
              {filtered.map((job, i) => {
                const ev = job.evaluation;
                return (
                  <button
                    type="button"
                    key={job.id}
                    className={`jh-card ${selected?.id === job.id ? 'is-selected' : ''} ${job.status === 'rejected' ? 'is-rejected' : ''}`}
                    onClick={() => {
                      setSelectedId(job.id);
                      setShowDescription(false);
                    }}
                  >
                    <ScoreRing score={ev ? ev.overall : null} />
                    <div className="jh-card-body">
                      <div className="jh-card-title">
                        <span className="jh-rank">#{i + 1}</span> {job.title}
                      </div>
                      <div className="jh-card-company">
                        {job.company}
                        {job.location ? ` · ${job.location}` : ''}
                      </div>
                      <div className="jh-meta">
                        {job.work_mode && <span className="jh-tag">{job.work_mode}</span>}
                        {job.salary && <span className="jh-tag">{job.salary}</span>}
                        {job.source && <span className="jh-tag jh-tag-soft">{job.source}</span>}
                        {job.has_resume && <span className="jh-tag jh-tag-ok">Resume</span>}
                      </div>
                    </div>
                    <div className="jh-card-side">
                      {ev && (
                        <span className={`jh-verdict jh-verdict-${ev.verdict}`}>{VERDICT_LABEL[ev.verdict]}</span>
                      )}
                      <span className={`jh-status jh-status-${job.status}`}>{STATUS_LABEL[job.status]}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <aside className="jh-detail">
            {!selected ? (
              <div className="jh-none">Select a job to see why it fits.</div>
            ) : (
              <>
                <div className="jh-detail-head">
                  <ScoreRing score={selected.evaluation?.overall ?? null} size={92} />
                  <div className="jh-detail-heading">
                    <h2>{selected.title}</h2>
                    <div className="jh-detail-company">
                      {selected.company}
                      {selected.location ? ` · ${selected.location}` : ''}
                    </div>
                    <div className="jh-meta">
                      {selected.evaluation && (
                        <span className={`jh-verdict jh-verdict-${selected.evaluation.verdict}`}>
                          {VERDICT_LABEL[selected.evaluation.verdict]}
                        </span>
                      )}
                      {selected.salary && <span className="jh-tag">{selected.salary}</span>}
                      {selected.work_mode && <span className="jh-tag">{selected.work_mode}</span>}
                      {selected.experience_level && <span className="jh-tag">{selected.experience_level}</span>}
                      {selected.posted && <span className="jh-tag jh-tag-soft">{selected.posted}</span>}
                    </div>
                  </div>
                </div>

                <div className="jh-actions">
                  {selected.status !== 'shortlisted' && selected.status !== 'applied' && (
                    <Button size="sm" variant="secondary" onClick={() => changeStatus(selected, 'shortlisted')}>
                      Shortlist
                    </Button>
                  )}
                  {selected.status !== 'applied' && (
                    <Button size="sm" variant="primary" icon={<CheckIcon size={13} />} onClick={() => changeStatus(selected, 'applied')}>
                      Mark applied
                    </Button>
                  )}
                  {selected.status !== 'rejected' ? (
                    <Button size="sm" variant="ghost" onClick={() => changeStatus(selected, 'rejected')}>
                      Reject
                    </Button>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => changeStatus(selected, 'new')}>
                      Restore
                    </Button>
                  )}
                  {selected.url && !selected.url.includes('example.com') && (
                    <a className="jh-link" href={selected.url} target="_blank" rel="noreferrer noopener">
                      <GlobeIcon size={13} /> Open posting
                    </a>
                  )}
                  <button type="button" className="jh-icon-btn" title="Remove job" onClick={() => removeJob(selected)}>
                    <TrashIcon size={14} />
                  </button>
                </div>

                {selected.evaluation ? (
                  <>
                    <h3 className="jh-h3">Why this score</h3>
                    <div className="jh-params">
                      {Object.entries(PARAM_LABELS).map(([key, label]) => {
                        const p = selected.evaluation?.parameters[key];
                        if (!p) return null;
                        return (
                          <div className="jh-param" key={key}>
                            <div className="jh-param-top">
                              <span>
                                {label} <em>{weights[key] ? `${weights[key]}%` : ''}</em>
                              </span>
                              <b style={{ color: scoreColor(p.score) }}>{p.score}</b>
                            </div>
                            <div className="jh-bar">
                              <span style={{ width: `${p.score}%`, background: scoreColor(p.score) }} />
                            </div>
                            {p.note && <div className="jh-param-note">{p.note}</div>}
                          </div>
                        );
                      })}
                    </div>

                    <div className="jh-reasons">
                      {selected.evaluation.why.length > 0 && (
                        <div className="jh-reason jh-reason-good">
                          <h4>Why it suits you</h4>
                          <ul>{selected.evaluation.why.map((w, i) => <li key={i}>{w}</li>)}</ul>
                        </div>
                      )}
                      {selected.evaluation.gaps.length > 0 && (
                        <div className="jh-reason jh-reason-gap">
                          <h4>Gaps</h4>
                          <ul>{selected.evaluation.gaps.map((w, i) => <li key={i}>{w}</li>)}</ul>
                        </div>
                      )}
                      {selected.evaluation.red_flags.length > 0 && (
                        <div className="jh-reason jh-reason-flag">
                          <h4>Red flags</h4>
                          <ul>{selected.evaluation.red_flags.map((w, i) => <li key={i}>{w}</li>)}</ul>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="jh-callout">
                    Not ranked yet.{' '}
                    <button type="button" className="jh-linkbtn" onClick={() => runPrompt('job_matcher_agent', PIPELINE_PROMPTS.match)}>
                      Run the matcher
                    </button>
                  </div>
                )}

                {selected.skills?.length > 0 && (
                  <div className="jh-meta jh-skills">
                    {selected.skills.map((s) => (
                      <span className="jh-tag jh-tag-soft" key={s}>{s}</span>
                    ))}
                  </div>
                )}

                {selected.description && (
                  <div className="jh-desc">
                    <button type="button" className="jh-linkbtn" onClick={() => setShowDescription((v) => !v)}>
                      {showDescription ? 'Hide' : 'Show'} job description
                    </button>
                    {showDescription && <p>{selected.description}</p>}
                  </div>
                )}

                <h3 className="jh-h3">Tailored resume</h3>
                {selected.has_resume ? (
                  <div className="jh-resume">
                    <div className="jh-resume-bar">
                      <Badge variant="success" size="sm">{selected.resume?.template} template</Badge>
                      <div className="jh-resume-actions">
                        <Button size="sm" variant="secondary" icon={<FileIcon size={13} />} onClick={printResume}>
                          Print / Save PDF
                        </Button>
                        <a className="jh-link" href={getJobResumeUrl(selected.id, true)}>
                          <DownloadIcon size={13} /> HTML
                        </a>
                        <button type="button" className="jh-linkbtn" onClick={() => setResumeNonce((n) => n + 1)}>
                          Reload
                        </button>
                      </div>
                    </div>
                    {selected.resume?.notes?.length ? (
                      <ul className="jh-notes">{selected.resume.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
                    ) : null}
                    <div className="jh-frame-wrap" ref={bindFrameWrap} style={{ height: 1123 * frameScale }}>
                      <iframe
                        key={`${selected.id}-${resumeNonce}-${selected.resume?.generated_at}`}
                        ref={iframeRef}
                        title={`Resume for ${selected.title}`}
                        src={getJobResumeUrl(selected.id)}
                        className="jh-frame"
                        style={{ width: A4_WIDTH_PX, height: 1123, transform: `scale(${frameScale})` }}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="jh-callout">
                    No resume yet for this job.{' '}
                    <button
                      type="button"
                      className="jh-linkbtn"
                      onClick={() =>
                        runPrompt(
                          'resume_tailor_agent',
                          `Tailor a single-file HTML resume for the job "${selected.title}" at ${selected.company} (job id ${selected.id}).`
                        )
                      }
                    >
                      Tailor with agent
                    </button>
                  </div>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
};
