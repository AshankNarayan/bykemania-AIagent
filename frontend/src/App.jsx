import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, getApiBaseUrl } from "./api.js";

const STORAGE_KEY = "bykemania_dashboard_api_key";

function JsonBlock({ data }) {
  return (
    <pre className="json-block">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function StatusPill({ status }) {
  const normalized = String(status || "unknown").toLowerCase();

  return (
    <span className={`status-pill status-${normalized}`}>
      {status || "unknown"}
    </span>
  );
}

function EmptyState({ title, message }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

function ErrorBox({ error }) {
  if (!error) {
    return null;
  }

  return (
    <div className="error-box">
      <strong>Error:</strong> {error}
    </div>
  );
}

function MetricCard({ title, value, subtitle }) {
  return (
    <div className="metric-card">
      <p>{title}</p>
      <h2>{value}</h2>
      {subtitle ? <span>{subtitle}</span> : null}
    </div>
  );
}

function getDepartmentName(card) {
  return (
    card.department_name ||
    card.department ||
    card.name ||
    card.title ||
    "Unknown Department"
  );
}

function getDepartmentCount(card) {
  return (
    card.total_alerts ??
    card.alert_count ??
    card.count ??
    card.total ??
    "-"
  );
}

function getSeverityText(card) {
  const high = card.high_count ?? card.high ?? card.HIGH;
  const medium = card.medium_count ?? card.medium ?? card.MEDIUM;
  const low = card.low_count ?? card.low ?? card.LOW;

  const parts = [];

  if (high !== undefined) parts.push(`High: ${high}`);
  if (medium !== undefined) parts.push(`Medium: ${medium}`);
  if (low !== undefined) parts.push(`Low: ${low}`);

  return parts.length ? parts.join(" • ") : "Severity details available in raw data";
}

function App() {
  const [apiKey, setApiKey] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) || "";
  });

  const [savedApiKey, setSavedApiKey] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) || "";
  });

  const [rootInfo, setRootInfo] = useState(null);
  const [health, setHealth] = useState(null);
  const [ready, setReady] = useState(null);
  const [scheduler, setScheduler] = useState(null);

  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [selectedDepartment, setSelectedDepartment] = useState("");
  const [departmentDetail, setDepartmentDetail] = useState(null);

  const [logs, setLogs] = useState([]);

  const [chatInput, setChatInput] = useState("hello");
  const [chatMessages, setChatMessages] = useState([]);

  const [loading, setLoading] = useState({
    status: false,
    dashboard: false,
    chat: false,
    department: false,
    logs: false,
  });

  const [error, setError] = useState("");

  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);

  function saveApiKey() {
    const cleanKey = apiKey.trim();

    localStorage.setItem(STORAGE_KEY, cleanKey);
    setSavedApiKey(cleanKey);
    setError("");
  }

  function clearApiKey() {
    localStorage.removeItem(STORAGE_KEY);
    setApiKey("");
    setSavedApiKey("");
    setError("");
  }

  function requireApiKey() {
    if (!savedApiKey) {
      setError("Please save your API key first.");
      return false;
    }

    return true;
  }

  async function loadStatus() {
    setLoading((prev) => ({ ...prev, status: true }));
    setError("");

    try {
      const [rootData, healthData, readyData] = await Promise.all([
        apiGet("/"),
        apiGet("/health"),
        apiGet("/ready"),
      ]);

      setRootInfo(rootData);
      setHealth(healthData);
      setReady(readyData);

      if (savedApiKey) {
        const schedulerData = await apiGet("/scheduler/status", savedApiKey);
        setScheduler(schedulerData);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, status: false }));
    }
  }

  async function loadDashboard() {
    if (!requireApiKey()) {
      return;
    }

    setLoading((prev) => ({ ...prev, dashboard: true }));
    setError("");

    try {
      const [summaryData, departmentsData] = await Promise.all([
        apiGet("/dashboard/summary", savedApiKey),
        apiGet("/dashboard/departments", savedApiKey),
      ]);

      setDashboardSummary(summaryData);
      setDepartments(departmentsData.departments || []);

      if (!selectedDepartment && departmentsData.departments?.length) {
        setSelectedDepartment(getDepartmentName(departmentsData.departments[0]));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, dashboard: false }));
    }
  }

  async function loadLogs() {
    if (!requireApiKey()) {
      return;
    }

    setLoading((prev) => ({ ...prev, logs: true }));
    setError("");

    try {
      const data = await apiGet("/logs/recent?limit=5", savedApiKey);
      setLogs(data.logs || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, logs: false }));
    }
  }

  async function loadDepartmentDetail(departmentName) {
    if (!requireApiKey()) {
      return;
    }

    if (!departmentName) {
      return;
    }

    setLoading((prev) => ({ ...prev, department: true }));
    setError("");

    try {
      const encodedDepartment = encodeURIComponent(departmentName);
      const data = await apiGet(
        `/dashboard/department/${encodedDepartment}?limit=25`,
        savedApiKey
      );

      setDepartmentDetail(data);
    } catch (err) {
      setDepartmentDetail(null);
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, department: false }));
    }
  }

  async function sendChatMessage(event) {
    event.preventDefault();

    if (!requireApiKey()) {
      return;
    }

    const cleanMessage = chatInput.trim();

    if (!cleanMessage) {
      setError("Chat message cannot be empty.");
      return;
    }

    setLoading((prev) => ({ ...prev, chat: true }));
    setError("");

    const userMessage = {
      role: "user",
      text: cleanMessage,
      timestamp: new Date().toLocaleTimeString(),
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");

    try {
      const data = await apiPost(
        "/chat",
        {
          query: cleanMessage,
        },
        savedApiKey
      );

      const responseText =
        data?.response?.summary ||
        data?.response?.message ||
        JSON.stringify(data?.response || data, null, 2);

      const assistantMessage = {
        role: "assistant",
        text: responseText,
        raw: data,
        timestamp: new Date().toLocaleTimeString(),
      };

      setChatMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = {
        role: "assistant",
        text: `Error: ${err.message}`,
        raw: err.data || null,
        timestamp: new Date().toLocaleTimeString(),
      };

      setChatMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading((prev) => ({ ...prev, chat: false }));
    }
  }

  useEffect(() => {
    loadStatus();
  }, [savedApiKey]);

  useEffect(() => {
    if (selectedDepartment) {
      loadDepartmentDetail(selectedDepartment);
    }
  }, [selectedDepartment]);

  const schedulerEnabled = scheduler?.scheduler?.enabled;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">BM</div>
          <div>
            <h1>BykeMania</h1>
            <p>AI Operations Dashboard</p>
          </div>
        </div>

        <div className="api-panel">
          <label>Backend URL</label>
          <div className="backend-url">{apiBaseUrl}</div>

          <label>API Key</label>
          <input
            type="password"
            placeholder="Paste x-api-key"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />

          <div className="button-row">
            <button onClick={saveApiKey}>Save Key</button>
            <button className="ghost-button" onClick={clearApiKey}>
              Clear
            </button>
          </div>

          <p className="hint">
            API key is stored only in your browser localStorage.
          </p>
        </div>

        <nav className="nav-list">
          <a href="#overview">Overview</a>
          <a href="#dashboard">Dashboard</a>
          <a href="#departments">Departments</a>
          <a href="#chat">Chat</a>
          <a href="#logs">Logs</a>
        </nav>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Production MVP</p>
            <h1>Operations Command Center</h1>
          </div>

          <button onClick={loadStatus} disabled={loading.status}>
            {loading.status ? "Refreshing..." : "Refresh Status"}
          </button>
        </header>

        <ErrorBox error={error} />

        <section id="overview" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">System</p>
              <h2>Backend Status</h2>
            </div>
          </div>

          <div className="metric-grid">
            <MetricCard
              title="API Version"
              value={rootInfo?.version || "-"}
              subtitle={rootInfo?.environment || "environment unknown"}
            />

            <MetricCard
              title="Health"
              value={health?.status || "-"}
              subtitle={health?.service || ""}
            />

            <MetricCard
              title="Readiness"
              value={ready?.status || "-"}
              subtitle={ready?.database || ""}
            />

            <MetricCard
              title="Scheduler"
              value={schedulerEnabled === undefined ? "-" : String(schedulerEnabled)}
              subtitle="Enabled status"
            />
          </div>
        </section>

        <section id="dashboard" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">Alerts</p>
              <h2>Dashboard Summary</h2>
            </div>

            <button onClick={loadDashboard} disabled={loading.dashboard}>
              {loading.dashboard ? "Loading..." : "Load Dashboard"}
            </button>
          </div>

          {dashboardSummary ? (
            <JsonBlock data={dashboardSummary.dashboard || dashboardSummary} />
          ) : (
            <EmptyState
              title="No dashboard data loaded"
              message="Click Load Dashboard after saving your API key."
            />
          )}
        </section>

        <section id="departments" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">Departments</p>
              <h2>Department Alert Cards</h2>
            </div>
          </div>

          {departments.length ? (
            <div className="department-grid">
              {departments.map((department, index) => {
                const departmentName = getDepartmentName(department);
                const isActive = departmentName === selectedDepartment;

                return (
                  <button
                    key={`${departmentName}-${index}`}
                    className={`department-card ${isActive ? "active" : ""}`}
                    onClick={() => setSelectedDepartment(departmentName)}
                  >
                    <div>
                      <h3>{departmentName}</h3>
                      <p>{getSeverityText(department)}</p>
                    </div>

                    <strong>{getDepartmentCount(department)}</strong>
                  </button>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No departments loaded"
              message="Load dashboard data to see department cards."
            />
          )}

          <div className="detail-panel">
            <div className="section-header">
              <div>
                <p className="eyebrow">Selected Department</p>
                <h2>{selectedDepartment || "None selected"}</h2>
              </div>

              {selectedDepartment ? (
                <button
                  onClick={() => loadDepartmentDetail(selectedDepartment)}
                  disabled={loading.department}
                >
                  {loading.department ? "Loading..." : "Refresh Detail"}
                </button>
              ) : null}
            </div>

            {departmentDetail ? (
              <JsonBlock data={departmentDetail.dashboard || departmentDetail} />
            ) : (
              <EmptyState
                title="No department detail loaded"
                message="Select a department card to view details."
              />
            )}
          </div>
        </section>

        <section id="chat" className="section chat-section">
          <div className="section-header">
            <div>
              <p className="eyebrow">AI Assistant</p>
              <h2>Operations Chat</h2>
            </div>
          </div>

          <div className="chat-window">
            {chatMessages.length ? (
              chatMessages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`chat-message ${message.role}`}
                >
                  <div className="chat-meta">
                    <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
                    <span>{message.timestamp}</span>
                  </div>

                  <p>{message.text}</p>

                  {message.raw ? (
                    <details>
                      <summary>Raw response</summary>
                      <JsonBlock data={message.raw} />
                    </details>
                  ) : null}
                </div>
              ))
            ) : (
              <EmptyState
                title="No chat yet"
                message="Ask something like: Tell me all the active locations."
              />
            )}
          </div>

          <form className="chat-form" onSubmit={sendChatMessage}>
            <input
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Ask BykeMania AI..."
            />

            <button type="submit" disabled={loading.chat}>
              {loading.chat ? "Sending..." : "Send"}
            </button>
          </form>
        </section>

        <section id="logs" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">Observability</p>
              <h2>Recent Logs</h2>
            </div>

            <button onClick={loadLogs} disabled={loading.logs}>
              {loading.logs ? "Loading..." : "Load Logs"}
            </button>
          </div>

          {logs.length ? (
            <div className="logs-list">
              {logs.map((log, index) => (
                <div className="log-card" key={log.request_id || index}>
                  <div>
                    <h3>{log.user_query || "Unknown query"}</h3>
                    <p>{log.timestamp_utc || "No timestamp"}</p>
                  </div>

                  <StatusPill status={log.status} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No logs loaded"
              message="Click Load Logs after using the chat endpoint."
            />
          )}
        </section>
      </main>
    </div>
  );
}

export default App;