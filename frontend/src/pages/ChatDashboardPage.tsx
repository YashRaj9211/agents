import React, { useEffect } from 'react';
import { useChatStore } from '../store';
import { Sidebar } from '../components/layout/Sidebar';
import { ChatHistorySidebar } from '../components/chat/ChatHistorySidebar';
import { ChatHeader } from '../components/chat/ChatHeader';
import { WelcomeHero } from '../components/chat/WelcomeHero';
import { MessageList } from '../components/chat/MessageList';
import { ChatInputBar } from '../components/chat/ChatInputBar';
import { AgentExecutionTimeline } from '../components/chat/AgentExecutionTimeline';
import { RunStepsPanel } from '../components/chat/RunStepsPanel';
import { HumanInputCard } from '../components/chat/HumanInputCard';
import { RunningAgentsPanel } from '../components/runs/RunningAgentsPanel';
import { ArtifactsView } from '../components/artifacts/ArtifactsView';
import { JobHuntView } from '../components/jobs/JobHuntView';

export const ChatDashboardPage: React.FC = () => {
  // Store subscriptions
  const activeTab = useChatStore((s) => s.activeTab);
  const setActiveTab = useChatStore((s) => s.setActiveTab);

  const selectedAgentId = useChatStore((s) => s.selectedAgentId);
  const setSelectedAgentId = useChatStore((s) => s.setSelectedAgentId);

  const availableAgents = useChatStore((s) => s.availableAgents);
  const loadAgents = useChatStore((s) => s.loadAgents);
  const loadSessions = useChatStore((s) => s.loadSessions);

  const user = useChatStore((s) => s.user);

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
  const clearSessionMessages = useChatStore((s) => s.clearSessionMessages);

  const quickActions = useChatStore((s) => s.quickActions);
  const checkHealth = useChatStore((s) => s.checkHealth);
  const backendOnline = useChatStore((s) => s.backendOnline);

  const activeTimeline = useChatStore((s) => s.activeTimeline);
  const showTimelineDrawer = useChatStore((s) => s.showTimelineDrawer);
  const toggleTimelineDrawer = useChatStore((s) => s.toggleTimelineDrawer);

  const runSteps = useChatStore((s) => s.runSteps);
  const runStartedAt = useChatStore((s) => s.runStartedAt);
  const stepsExpanded = useChatStore((s) => s.stepsExpanded);
  const toggleSteps = useChatStore((s) => s.toggleSteps);
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
  const sessionRunId = useChatStore((s) => s.sessionRunId);
  const stoppingRunIds = useChatStore((s) => s.stoppingRunIds);

  useEffect(() => {
    checkHealth();
    loadAgents();
  }, [checkHealth, loadAgents]);

  // Runs continue in the backend while the user reads another conversation, so
  // the panel polls rather than relying only on the stream this tab started.
  useEffect(() => {
    loadActiveRuns();
    const timer = window.setInterval(() => {
      loadActiveRuns();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadActiveRuns]);

  const activeSessionRunId = sessionRunId[activeSessionId];

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const activeAgent = availableAgents.find((a) => a.id === selectedAgentId);

  const handleSelectQuickAction = (prompt: string) => {
    const action = quickActions.find((a) => a.prompt === prompt);
    if (action?.target_agent_id) {
      setSelectedAgentId(action.target_agent_id);
    }
    sendMessage(prompt);
  };

  return (
    <div className="app-shell">
      {/* 1. Left Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        selectedAgent={selectedAgentId}
        onSelectAgent={setSelectedAgentId}
        agents={availableAgents}
        user={user}
      />

      {/* 2. Main Center Panel */}
      <main className="chat-center-panel">
        {activeTab === 'jobs' ? (
          <JobHuntView />
        ) : activeTab === 'artifacts' ? (
          <ArtifactsView />
        ) : (
          <>
            {/* Chat Header with Session Details & Actions */}
            <ChatHeader
              sessionTitle={activeSession?.title || (messages.length > 0 ? 'Conversation' : 'New Conversation')}
              agentName={activeAgent?.name || 'Root Orchestrator'}
              isBackendOnline={backendOnline}
              timelineCount={activeTimeline.length}
              showTimeline={showTimelineDrawer}
              onToggleTimeline={toggleTimelineDrawer}
              onRenameSession={activeSessionId ? (newTitle) => renameSession(activeSessionId, newTitle) : undefined}
              onClearChat={() => clearSessionMessages(activeSessionId)}
              onNewChat={createNewChat}
              hasMessages={messages.length > 0}
              runId={activeSessionRunId}
              isStoppingRun={Boolean(activeSessionRunId) && stoppingRunIds.includes(activeSessionRunId)}
              onStopRun={() => {
                if (activeSessionRunId) stopRun(activeSessionRunId);
              }}
            />

            {/* Parallel agents: every run in flight, with Open / Stop controls */}
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

            {/* Optional Execution Timeline Drawer */}
            {showTimelineDrawer && (
              <div className="timeline-drawer-banner">
                <div className="timeline-drawer-header">
                  <span className="drawer-title">Active Session Trace & Execution Flow</span>
                  <span className="drawer-subtitle">{activeTimeline.length} events logged</span>
                </div>
                {activeTimeline.length > 0 ? (
                  <AgentExecutionTimeline events={activeTimeline} />
                ) : (
                  <p className="timeline-drawer-empty">No execution events logged yet for this session.</p>
                )}
              </div>
            )}

            <div className="chat-center-content">
              {messages.length === 0 ? (
                <WelcomeHero
                  userName={user.name}
                  actions={quickActions}
                  onSelectAction={handleSelectQuickAction}
                />
              ) : (
                <MessageList
                  messages={messages}
                  isThinking={isThinking}
                  onDeleteMessage={deleteMessage}
                />
              )}
            </div>

            {/* 3. Steps panel + HITL card, docked directly above the input bar */}
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

            <RunStepsPanel
              steps={runSteps}
              expanded={stepsExpanded}
              isRunning={isThinking}
              isWaitingForHuman={isWaitingForHuman}
              startedAt={runStartedAt}
              hasError={Boolean(error) && !pendingHumanInput}
              onToggleExpanded={toggleSteps}
              onToggleStep={toggleStep}
            />

            {/* 4. Bottom Chat Input Bar */}
            <ChatInputBar
              onSendMessage={(text, attached) => {
                const artIds = attached && attached.length > 0 ? attached.map((a) => a.id) : undefined;
                sendMessage(text, artIds);
              }}
              disabled={isThinking || isWaitingForHuman}
              activeAgent={selectedAgentId}
              sessionId={activeSessionId}
            />
          </>
        )}
      </main>


      {/* 4. Right Chat History Sidebar */}
      {activeTab !== 'jobs' && (
        <ChatHistorySidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={selectSession}
          onNewChat={createNewChat}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onRenameSession={renameSession}
          onDeleteSession={deleteSession}
          onRefresh={loadSessions}
        />
      )}
    </div>
  );
};
