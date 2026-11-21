import React, { useEffect, useState } from 'react';
import { ActivityIcon, PanelLeftIcon } from '../components/icons/Icons';
import { useChatStore } from '../store';
import { ActivitySection } from '../components/layout/ActivitySection';
import { Sidebar } from '../components/layout/Sidebar';
import { WelcomeHero } from '../components/chat/WelcomeHero';
import { MessageList } from '../components/chat/MessageList';
import { ChatInputBar } from '../components/chat/ChatInputBar';
import { RunStepsPanel } from '../components/chat/RunStepsPanel';
import { HumanInputCard } from '../components/chat/HumanInputCard';
import { RunningAgentsPanel } from '../components/runs/RunningAgentsPanel';
import { ArtifactsView } from '../components/artifacts/ArtifactsView';
import { JobHuntView } from '../components/jobs/JobHuntView';
import { UiPanel } from '../components/panel/UiPanel';

export const ChatDashboardPage: React.FC = () => {
  // Store subscriptions
  const activeTab = useChatStore((s) => s.activeTab);
  const setActiveTab = useChatStore((s) => s.setActiveTab);

  const selectedAgentId = useChatStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useChatStore((s) => s.setSelectedAgentId);

  const availableAgents = useChatStore((s) => s.availableAgents);
  const loadAgents = useChatStore((s) => s.loadAgents);


  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const selectSession = useChatStore((s) => s.selectSession);
  const createNewChat = useChatStore((s) => s.createNewChat);
  const renameSession = useChatStore((s) => s.renameSession);
  const deleteSession = useChatStore((s) => s.deleteSession);

  const searchQuery = useChatStore((s) => s.searchQuery);
  const setSearchQuery = useChatStore((s) => s.setSearchQuery);

  const messages = useChatStore((s) => s.messages);
  const isThinking = useChatStore((s) => s.isThinking);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const deleteMessage = useChatStore((s) => s.deleteMessage);

  const quickActions = useChatStore((s) => s.quickActions);
  const checkHealth = useChatStore((s) => s.checkHealth);
  const backendOnline = useChatStore((s) => s.backendOnline);


  const runSteps = useChatStore((s) => s.runSteps);
  const runStartedAt = useChatStore((s) => s.runStartedAt);
  const toggleStep = useChatStore((s) => s.toggleStep);
  const pendingHumanInput = useChatStore((s) => s.pendingHumanInput);
  const isWaitingForHuman = useChatStore((s) => s.isWaitingForHuman);
  const isSubmittingAnswer = useChatStore((s) => s.isSubmittingAnswer);
  const submitHumanAnswer = useChatStore((s) => s.submitHumanAnswer);
  const error = useChatStore((s) => s.error);

  // Parallel run management: the fleet of agents executing right now, plus the
  // ability to jump into (or stop) any one of them.
  const activeRuns = useChatStore((s) => s.activeRuns);
  const activeRunLimit = useChatStore((s) => s.activeRunLimit);
  const loadActiveRuns = useChatStore((s) => s.loadActiveRuns);
  const stopRun = useChatStore((s) => s.stopRun);
  const stoppingRunIds = useChatStore((s) => s.stoppingRunIds);

  const uiPanels = useChatStore((s) => s.uiPanels);
  const activePanelId = useChatStore((s) => s.activePanelId);
  const panelOpen = useChatStore((s) => s.panelOpen);
  const openPanel = useChatStore((s) => s.openPanel);
  const closePanel = useChatStore((s) => s.closePanel);
  const removePanel = useChatStore((s) => s.removePanel);

  // The open conversation lives in the URL (?session=<id>) so reload, back/forward
  // and shared links land on the same chat. localStorage is the fallback for a
  // bare URL. `restored` keeps the sync below from wiping the id before the
  // session list has loaded.
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    checkHealth();
    loadAgents().then(() => {
      const { sessions: list, selectSession: select } = useChatStore.getState();
      let wanted = new URLSearchParams(window.location.search).get('session');
      if (!wanted) {
        try {
          wanted = localStorage.getItem('activeSessionId');
        } catch {
          /* storage unavailable */
        }
      }
      if (wanted && list.some((s) => s.id === wanted)) void select(wanted);
      setRestored(true);
    });
  }, [checkHealth, loadAgents]);

  useEffect(() => {
    if (!restored) return;
    const url = new URL(window.location.href);
    if (activeSessionId) url.searchParams.set('session', activeSessionId);
    else url.searchParams.delete('session');
    if (url.href !== window.location.href) {
      window.history.pushState(null, '', url);
    }
    try {
      if (activeSessionId) localStorage.setItem('activeSessionId', activeSessionId);
      else localStorage.removeItem('activeSessionId');
    } catch {
      /* storage unavailable */
    }
  }, [activeSessionId, restored]);

  // Browser back/forward changes the URL; follow it.
  useEffect(() => {
    const onPop = () => {
      const id = new URLSearchParams(window.location.search).get('session');
      const state = useChatStore.getState();
      if (id && id !== state.activeSessionId && state.sessions.some((s) => s.id === id)) {
        void state.selectSession(id);
      }
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // Runs continue in the backend while the user reads another conversation, so
  // the panel polls rather than relying only on the stream this tab started.
  useEffect(() => {
    loadActiveRuns();
    const timer = window.setInterval(() => {
      loadActiveRuns();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadActiveRuns]);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activityOpen, setActivityOpen] = useState(false);
  const isChatTab = activeTab !== 'jobs' && activeTab !== 'artifacts';

  const handleSelectQuickAction = (prompt: string) => {
    const action = quickActions.find((a) => a.prompt === prompt);
    if (action?.target_agent_id) {
      setSelectedAgentId(action.target_agent_id);
    }
    sendMessage(prompt);
  };

  const composer = (
    <ChatInputBar
      onSendMessage={(text, attached) => {
        const artIds = attached && attached.length > 0 ? attached.map((a) => a.id) : undefined;
        sendMessage(text, artIds);
      }}
      disabled={isThinking || isWaitingForHuman}
      isRunning={isThinking || isWaitingForHuman}
      onStop={() => {
        if (activeSessionId) void stopRun(activeSessionId);
      }}
      sessionId={activeSessionId}
    />
  );

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        onCollapse={() => setSidebarOpen(false)}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        agents={availableAgents}
        selectedAgent={selectedAgentId}
        onSelectAgent={setSelectedAgentId}
        backendOnline={backendOnline}
        onNewChat={createNewChat}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={selectSession}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onRenameSession={renameSession}
        onDeleteSession={deleteSession}
      />

      <div className="app-body">
        <main className="chat-center-panel">
          {!sidebarOpen && (
            <button type="button" className="panel-toggle float-left" onClick={() => setSidebarOpen(true)} title="Show sidebar" aria-label="Show sidebar">
              <PanelLeftIcon size={16} />
            </button>
          )}
          {isChatTab && (
            <button
              type="button"
              className={`panel-toggle float-right ${activityOpen ? 'is-active' : ''}`}
              onClick={() => setActivityOpen((o) => !o)}
              title={activityOpen ? 'Hide activity' : 'Show activity'}
              aria-label="Toggle activity panel"
            >
              <ActivityIcon size={16} />
              {(isThinking || activeRuns.length > 0) && <span className="panel-toggle-dot" />}
            </button>
          )}
          {activeTab === 'jobs' ? (
            <JobHuntView />
          ) : activeTab === 'artifacts' ? (
            <ArtifactsView />
          ) : (
            <>
              {uiPanels.length > 0 && !panelOpen && (
                <button className="ui-panel-toggle" onClick={() => openPanel()}>
                  Views ({uiPanels.length})
                </button>
              )}

              <div className="chat-center-content">
                {messages.length === 0 ? (
                  <WelcomeHero actions={quickActions} onSelectAction={handleSelectQuickAction}>
                    {composer}
                  </WelcomeHero>
                ) : (
                  <MessageList messages={messages} isThinking={isThinking} onDeleteMessage={deleteMessage} />
                )}
              </div>

              {pendingHumanInput && (
                <div className="hitl-dock">
                  <HumanInputCard
                    key={pendingHumanInput.question_id}
                    request={pendingHumanInput}
                    isSubmitting={isSubmittingAnswer}
                    error={error}
                    onSubmit={submitHumanAnswer}
                  />
                </div>
              )}

              {messages.length > 0 && composer}
            </>
          )}
        </main>

        {isChatTab && (
          <aside
            className={`activity-panel ${activityOpen ? 'is-open' : ''}`}
            aria-hidden={!activityOpen}
            inert={!activityOpen}
          >
            <div className="activity-panel-inner">
            <div className="activity-panel-title">Activity</div>

            <ActivitySection
              title="Steps"
              defaultOpen
              summary={
                isWaitingForHuman
                  ? 'Waiting for you'
                  : isThinking
                    ? `${runSteps.filter((st) => st.status === 'running').length} running`
                    : runSteps.length > 0
                      ? `${runSteps.length} done`
                      : 'None'
              }
            >
              <RunStepsPanel
                steps={runSteps}
                expanded
                isRunning={isThinking}
                isWaitingForHuman={isWaitingForHuman}
                startedAt={runStartedAt}
                hasError={Boolean(error) && !pendingHumanInput}
                onToggleExpanded={() => undefined}
                onToggleStep={toggleStep}
              />
              {runSteps.length === 0 && !isThinking && <p className="act-empty">No steps in this conversation yet.</p>}
            </ActivitySection>

            <ActivitySection
              title="Running agents"
              defaultOpen={activeRuns.length > 0}
              summary={activeRuns.length > 0 ? `${activeRuns.length}${activeRunLimit > 0 ? ` / ${activeRunLimit}` : ''}` : 'None'}
            >
              <RunningAgentsPanel
                runs={activeRuns}
                sessions={sessions}
                activeSessionId={activeSessionId}
                stoppingRunIds={stoppingRunIds}
                activeCount={activeRuns.length}
                limit={activeRunLimit}
                onOpenSession={selectSession}
                onStopRun={(runId) => stopRun(runId)}
                onRefresh={loadActiveRuns}
              />
              {activeRuns.length === 0 && <p className="act-empty">No agents running.</p>}
            </ActivitySection>

            <ActivitySection
              title="Session"
              summary={availableAgents.find((a) => a.id === selectedAgentId)?.name ?? selectedAgentId}
            >
              <dl className="act-facts">
                <dt>Agent</dt>
                <dd>{availableAgents.find((a) => a.id === selectedAgentId)?.name ?? selectedAgentId}</dd>
                <dt>Conversation</dt>
                <dd>{sessions.find((x) => x.id === activeSessionId)?.title || 'New conversation'}</dd>
                <dt>Backend</dt>
                <dd>{backendOnline === false ? 'Offline' : 'Online'}</dd>
              </dl>
            </ActivitySection>
            </div>
          </aside>
        )}

        {isChatTab && panelOpen && uiPanels.length > 0 && (
          <UiPanel
            panels={uiPanels}
            activeId={activePanelId}
            onSelect={openPanel}
            onClose={closePanel}
            onDelete={(id) => void removePanel(id)}
          />
        )}
      </div>

    </div>
  );
};
