import React, { useState, useEffect, useRef } from 'react';
import { marked } from 'marked';
import './App.css';

// Configure marked options
marked.setOptions({
  breaks: true,
  gfm: true
});

function App() {
  const [goal, setGoal] = useState("Open example.com and print the page heading");
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState(null);
  const [taskId, setTaskId] = useState(null);
  
  const logsEndRef = useRef(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleStart = () => {
    if (!goal.trim()) return;
    
    setIsRunning(true);
    setLogs([]);
    setCurrentStep(0);
    setError(null);
    setTaskId(null);

    const eventSource = new EventSource(`http://localhost:3000/api/run?goal=${encodeURIComponent(goal)}`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'started':
            setTaskId(data.task_id);
            setLogs((prev) => [...prev, { type: 'info', text: `Session started (ID: ${data.task_id})`, time: new Date().toLocaleTimeString() }]);
            break;
          case 'info':
            setLogs((prev) => [...prev, { type: 'info', text: data.message, time: new Date().toLocaleTimeString() }]);
            break;
          case 'step_start':
            setCurrentStep(data.step);
            setLogs((prev) => [...prev, { type: 'step_start', text: `Starting Step ${data.step}...`, time: new Date().toLocaleTimeString() }]);
            break;
          case 'tool_start':
            setLogs((prev) => [
              ...prev,
              { 
                type: 'tool_start', 
                text: `Calling tool: ${data.tool}`, 
                details: JSON.stringify(data.arguments, null, 2),
                time: new Date().toLocaleTimeString() 
              }
            ]);
            break;
          case 'tool_end':
            setLogs((prev) => [
              ...prev,
              { 
                type: 'tool_end', 
                text: `Finished tool: ${data.tool}`, 
                details: typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2),
                time: new Date().toLocaleTimeString() 
              }
            ]);
            break;
          case 'step_end':
            setLogs((prev) => [...prev, { type: 'step_end', text: `Step ${data.step} complete. Result: ${data.result}`, time: new Date().toLocaleTimeString() }]);
            break;
          case 'done':
            setLogs((prev) => [...prev, { type: 'success', text: `SUCCESS: ${data.result}`, time: new Date().toLocaleTimeString() }]);
            eventSource.close();
            eventSourceRef.current = null;
            setIsRunning(false);
            break;
          case 'blocked':
            setLogs((prev) => [...prev, { type: 'error', text: `BLOCKED: ${data.result}`, time: new Date().toLocaleTimeString() }]);
            eventSource.close();
            eventSourceRef.current = null;
            setIsRunning(false);
            break;
          case 'error':
            setError(data.message);
            setLogs((prev) => [...prev, { type: 'error', text: `ERROR: ${data.message}`, time: new Date().toLocaleTimeString() }]);
            eventSource.close();
            eventSourceRef.current = null;
            setIsRunning(false);
            break;
          default:
            break;
        }
      } catch (err) {
        console.error('Error parsing SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource error:', err);
      setError('Connection to agent server lost or failed.');
      setIsRunning(false);
      eventSource.close();
      eventSourceRef.current = null;
    };
  };

  const handleStop = async () => {
    if (!taskId) return;
    try {
      setLogs((prev) => [...prev, { type: 'info', text: 'Stopping agent...', time: new Date().toLocaleTimeString() }]);
      const response = await fetch(`http://localhost:3000/api/stop?task_id=${encodeURIComponent(taskId)}`, {
        method: 'POST'
      });
      const resData = await response.json();
      if (resData.status === 'success') {
        setLogs((prev) => [...prev, { type: 'info', text: 'Agent stop request received by server.', time: new Date().toLocaleTimeString() }]);
      } else {
        setLogs((prev) => [...prev, { type: 'error', text: `Failed to stop agent: ${resData.message}`, time: new Date().toLocaleTimeString() }]);
      }
    } catch (err) {
      console.error('Error stopping agent:', err);
      setLogs((prev) => [...prev, { type: 'error', text: 'Network error stopping agent.', time: new Date().toLocaleTimeString() }]);
    } finally {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsRunning(false);
    }
  };

  return (
    <div className="container">
      <header className="app-header">
        <div className="header-content">
          <span className="badge">Agent Active</span>
          <h1>Web Automation Console</h1>
          <p className="subtitle">Execute model-driven browser tasks with real-time feedback</p>
        </div>
      </header>

      <main className="app-content">
        <section className="config-card">
          <h2>Configure Run</h2>
          <div className="input-group">
            <label htmlFor="goal-input">Task Goal / Prompt</label>
            <textarea
              id="goal-input"
              rows={3}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="What should the browser agent do? (e.g. Go to google.com and find the best AI model)"
              disabled={isRunning}
            />
          </div>

          <div className="action-row">
            <button 
              className={`btn-primary ${isRunning ? 'running' : ''}`}
              onClick={handleStart}
              disabled={isRunning || !goal.trim()}
            >
              {isRunning ? (
                <>
                  <span className="spinner"></span>
                  Agent Running (Step {currentStep})...
                </>
              ) : 'Run Agent Task'}
            </button>
            {isRunning && (
              <button 
                className="btn-danger"
                onClick={handleStop}
              >
                Stop Agent
              </button>
            )}
          </div>
        </section>

        <section className="terminal-card">
          <div className="terminal-header">
            <div className="terminal-buttons">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <span className="terminal-title">Execution Logs</span>
          </div>

          <div className="terminal-body">
            {logs.length === 0 && !error ? (
              <div className="terminal-placeholder">
                <p>Click "Run Agent Task" above to start execution.</p>
                <p className="hint">Make sure you have launched the FastAPI server on port 3000.</p>
              </div>
            ) : (
              <div className="log-list">
                {logs.map((log, index) => (
                  <div key={index} className={`log-item ${log.type}`}>
                    <div className="log-meta">
                      <span className="log-time">[{log.time}]</span>
                      <span className="log-badge">{log.type.toUpperCase()}</span>
                    </div>
                     <div 
                       className="log-text markdown-body" 
                       dangerouslySetInnerHTML={{ __html: marked.parse(log.text) }} 
                     />
                    {log.details && (
                      <pre className="log-details">
                        <code>{log.details}</code>
                      </pre>
                    )}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </section>
      </main>

      <footer className="app-footer">
        <p>Uses persistent profile located at <code>backend/storage/browser-profile</code></p>
      </footer>
    </div>
  );
}

export default App;
