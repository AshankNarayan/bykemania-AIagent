import { useEffect, useMemo, useRef, useState } from "react";
import { apiGet, apiPost, getApiBaseUrl } from "./api.js";

const STORAGE_KEY = "bykemania_dashboard_api_key";

function JsonBlock({ data }) {
  return <pre className="json-block">{JSON.stringify(data, null, 2)}</pre>;
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
  if (!error) return null;

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
      <h2>{formatValue(value)}</h2>
      {subtitle ? <span>{subtitle}</span> : null}
    </div>
  );
}

function formatValue(value) {
  if (value === undefined || value === null || value === "") return "-";

  if (typeof value === "boolean") return value ? "true" : "false";

  if (typeof value === "number") return value.toLocaleString("en-IN");

  if (typeof value === "object") {
    if (Array.isArray(value)) return value.length.toLocaleString("en-IN");

    if ("total_alerts" in value) return formatValue(value.total_alerts);
    if ("total" in value) return formatValue(value.total);
    if ("count" in value) return formatValue(value.count);

    return "-";
  }

  return String(value);
}

function formatLabel(value) {
  return String(value || "-")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function compactText(value, maxLength = 30) {
  const text = formatValue(value);

  if (text.length <= maxLength) return text;

  return `${text.slice(0, maxLength)}...`;
}

function pick(source, keys, fallback = undefined) {
  if (!source || typeof source !== "object") return fallback;

  for (const key of keys) {
    if (key.includes(".")) {
      const parts = key.split(".");
      let current = source;

      for (const part of parts) {
        if (!current || typeof current !== "object" || !(part in current)) {
          current = undefined;
          break;
        }

        current = current[part];
      }

      if (current !== undefined && current !== null && current !== "") {
        return current;
      }
    } else if (
      source[key] !== undefined &&
      source[key] !== null &&
      source[key] !== ""
    ) {
      return source[key];
    }
  }

  return fallback;
}

function getResponsePayload(raw) {
  if (!raw) return null;

  return raw.response || raw.data?.response || raw;
}

function getDashboardPayload(dashboardSummary) {
  if (!dashboardSummary) return null;

  return (
    dashboardSummary.dashboard ||
    dashboardSummary.data ||
    dashboardSummary.summary ||
    dashboardSummary
  );
}

function getSummaryObject(source) {
  if (!source) return {};

  return (
    source.summary ||
    source.latest_alert_run?.summary ||
    source.latest_alert_run ||
    source
  );
}

function getDepartmentName(card) {
  return (
    pick(card, [
      "department",
      "department_name",
      "name",
      "title",
      "departmentTitle",
    ]) || "Unknown Department"
  );
}

function getDepartmentSummary(card) {
  return card?.summary || card || {};
}

function getDepartmentCount(card) {
  const summary = getDepartmentSummary(card);

  return (
    Number(
      pick(
        summary,
        ["total_alerts", "alert_count", "count", "total", "total_items"],
        0
      )
    ) || 0
  );
}

function getSeverityCount(source, severity) {
  const lower = severity.toLowerCase();
  const upper = severity.toUpperCase();

  const summary = getDepartmentSummary(source);

  return pick(
    summary,
    [
      lower,
      upper,
      `${lower}_count`,
      `${upper}_count`,
      `severity.${lower}`,
      `severity.${upper}`,
      `summary.${lower}`,
      `summary.${upper}`,
      `summary.${lower}_count`,
      `summary.${upper}_count`,
    ],
    0
  );
}

function getAlertTypeCount(source) {
  if (!source) return {};

  return (
    source.alert_type_count ||
    source.alertTypeCount ||
    source.type_count ||
    source.types ||
    source.summary?.alert_type_count ||
    {}
  );
}

function getAlertItems(source) {
  if (!source) return [];

  const items =
    source.items ||
    source.alerts ||
    source.alert_items ||
    source.data ||
    source.dashboard?.items ||
    source.dashboard?.alerts ||
    [];

  return Array.isArray(items) ? items : [];
}

function extractVehicleFromMessage(message) {
  const text = String(message || "").trim();

  if (!text) return "-";

  const match = text.match(/\b[A-Z]{2}\d{2}[A-Z]{1,3}\d{3,5}\b/i);

  if (match) {
    return match[0].toUpperCase();
  }

  const firstWord = text.split(" ")[0];

  if (/^[A-Z0-9]{6,12}$/i.test(firstWord)) {
    return firstWord.toUpperCase();
  }

  return "-";
}


function parsePossibleDate(value) {
  if (!value) return null;

  const text = String(value).trim();

  if (!text) return null;

  const directDate = new Date(text);

  if (!Number.isNaN(directDate.getTime())) {
    return directDate.getTime();
  }

  return null;
}

function extractDateFromText(text) {
  const value = String(text || "");

  if (!value.trim()) return null;

  const patterns = [
    /\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b/g,
    /\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b/g,
    /\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(20\d{2})\b/gi,
    /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(20\d{2})\b/gi,
  ];

  const dates = [];

  for (const pattern of patterns) {
    let match;

    while ((match = pattern.exec(value)) !== null) {
      let dateValue = null;

      if (pattern === patterns[0]) {
        dateValue = new Date(
          Number(match[1]),
          Number(match[2]) - 1,
          Number(match[3])
        ).getTime();
      } else if (pattern === patterns[1]) {
        dateValue = new Date(
          Number(match[3]),
          Number(match[2]) - 1,
          Number(match[1])
        ).getTime();
      } else {
        dateValue = new Date(match[0]).getTime();
      }

      if (!Number.isNaN(dateValue)) {
        dates.push(dateValue);
      }
    }
  }

  if (!dates.length) return null;

  return Math.min(...dates);
}

function getAlertMessage(item) {
  return pick(
    item,
    ["message", "description", "reason", "title", "alert_message"],
    ""
  );
}

function getAlertSeverity(item) {
  return String(pick(item, ["severity"], "unknown")).toLowerCase();
}

function getAlertType(item) {
  return String(
    pick(item, ["alert_type", "type", "category"], "unknown")
  ).toLowerCase();
}

function getAlertVehicle(item) {
  const message = getAlertMessage(item);

  return (
    pick(
      item,
      [
        "vehicle_number",
        "vehicle_no",
        "registration_number",
        "registration_no",
        "reg_no",
        "reg_number",
        "vehicle_reg_no",
        "bike_number",
        "bike_no",
        "number_plate",
        "vehicle_id",
        "bike_id",
        "metadata.vehicle_number",
        "metadata.registration_number",
        "metadata.reg_no",
      ],
      ""
    ) || extractVehicleFromMessage(message)
  );
}

function getAlertLocation(item) {
  return pick(item, ["location", "location_name", "branch", "station"], "-");
}

function getAlertDateValue(item) {
  const directDate = pick(
    item,
    [
      "alert_date",
      "created_at",
      "timestamp_utc",
      "generated_at",
      "due_date",
      "expiry_date",
      "expired_at",
      "insurance_expiry",
      "insurance_expiry_date",
      "service_due_date",
      "last_service_date",
      "next_service_date",
      "metadata.due_date",
      "metadata.expiry_date",
      "metadata.insurance_expiry",
      "metadata.service_due_date",
    ],
    null
  );

  const parsedDirectDate = parsePossibleDate(directDate);

  if (parsedDirectDate) return parsedDirectDate;

  return extractDateFromText(getAlertMessage(item));
}

function formatAlertDate(dateValue) {
  if (!dateValue) return "-";

  return new Date(dateValue).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

function getSeverityRank(severity) {
  const value = String(severity || "").toLowerCase();

  if (value === "critical") return 4;
  if (value === "high") return 3;
  if (value === "medium") return 2;
  if (value === "low") return 1;

  return 0;
}

function sortAlertItems(items, sortBy) {
  const safeItems = [...items];

  return safeItems.sort((a, b) => {
    const severityA = getSeverityRank(getAlertSeverity(a));
    const severityB = getSeverityRank(getAlertSeverity(b));

    const dateA = getAlertDateValue(a) || 0;
    const dateB = getAlertDateValue(b) || 0;

    const vehicleA = String(getAlertVehicle(a) || "").toLowerCase();
    const vehicleB = String(getAlertVehicle(b) || "").toLowerCase();

    const locationA = String(getAlertLocation(a) || "").toLowerCase();
    const locationB = String(getAlertLocation(b) || "").toLowerCase();

    const typeA = String(getAlertType(a) || "").toLowerCase();
    const typeB = String(getAlertType(b) || "").toLowerCase();

    if (sortBy === "critical_first") {
      if (severityB !== severityA) return severityB - severityA;
      return dateA - dateB;
    }

    if (sortBy === "most_overdue") {
      if (!dateA && !dateB) return severityB - severityA;
      if (!dateA) return 1;
      if (!dateB) return -1;
      return dateA - dateB;
    }

    if (sortBy === "newest_date") {
      return dateB - dateA;
    }

    if (sortBy === "oldest_date") {
      return dateA - dateB;
    }

    if (sortBy === "vehicle") {
      return vehicleA.localeCompare(vehicleB);
    }

    if (sortBy === "location") {
      return locationA.localeCompare(locationB);
    }

    if (sortBy === "alert_type") {
      return typeA.localeCompare(typeB);
    }

    return 0;
  });
}

function getDepartmentDetailPayload(departmentDetail) {
  if (!departmentDetail) return null;

  return (
    departmentDetail.dashboard ||
    departmentDetail.alert_run ||
    departmentDetail.data ||
    departmentDetail
  );
}

function MessageText({ text }) {
  const parts = String(text || "").split(/(\*\*.*?\*\*)/g);

  return (
    <p>
      {parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        }

        return <span key={index}>{part}</span>;
      })}
    </p>
  );
}

function SmallList({ title, items, emptyText = "No items returned." }) {
  const safeItems = Array.isArray(items) ? items : [];

  return (
    <div className="requirement-list-card">
      <h4>{title}</h4>

      {safeItems.length ? (
        <ul>
          {safeItems.map((item, index) => (
            <li key={`${title}-${index}`}>{formatValue(item)}</li>
          ))}
        </ul>
      ) : (
        <p>{emptyText}</p>
      )}
    </div>
  );
}

function SourceBadge({ source, variant = "neutral" }) {
  return (
    <span className={`source-badge source-${variant}`}>
      {formatLabel(source)}
    </span>
  );
}

function RequiredDataCard({ data }) {
  const fields = Array.isArray(data?.minimum_fields) ? data.minimum_fields : [];

  return (
    <div className="required-data-card">
      <div>
        <h4>{data?.name || "Required Data"}</h4>
        <p>{data?.description || "No description provided."}</p>
      </div>

      {data?.source_key ? (
        <SourceBadge source={data.source_key} variant="required" />
      ) : null}

      <div className="field-chip-row">
        {fields.length ? (
          fields.map((field, index) => (
            <span className="field-chip" key={`${data?.name}-${field}-${index}`}>
              {field}
            </span>
          ))
        ) : (
          <span className="field-chip">No field list returned</span>
        )}
      </div>
    </div>
  );
}

function DataRequirementCard({ payload }) {
  const requiredData = Array.isArray(payload?.required_data)
    ? payload.required_data
    : [];

  const missingSources = Array.isArray(payload?.missing_data_sources)
    ? payload.missing_data_sources
    : [];

  const availableSources = Array.isArray(payload?.available_data_sources)
    ? payload.available_data_sources
    : [];

  const requiredSources = Array.isArray(payload?.required_data_sources)
    ? payload.required_data_sources
    : [];

  return (
    <div className="data-requirement-card">
      <div className="requirement-header">
        <div>
          <p className="eyebrow">Advanced Task Detected</p>
          <h3>{formatLabel(payload?.task_type || "Advanced Analysis")}</h3>
        </div>

        <span className="requirement-pill">Needs More Data</span>
      </div>

      <p className="requirement-summary">
        {payload?.summary ||
          "This task needs additional historical or business data before it can be answered accurately."}
      </p>

      <div className="source-section">
        <div>
          <h4>Missing Data Sources</h4>

          <div className="source-badge-row">
            {missingSources.length ? (
              missingSources.map((source) => (
                <SourceBadge key={source} source={source} variant="missing" />
              ))
            ) : (
              <span className="source-muted">No missing source list returned.</span>
            )}
          </div>
        </div>

        <div>
          <h4>Available Data Sources</h4>

          <div className="source-badge-row">
            {availableSources.length ? (
              availableSources.map((source) => (
                <SourceBadge key={source} source={source} variant="available" />
              ))
            ) : (
              <span className="source-muted">No available source list returned.</span>
            )}
          </div>
        </div>

        <div>
          <h4>Required Data Sources</h4>

          <div className="source-badge-row">
            {requiredSources.length ? (
              requiredSources.map((source) => (
                <SourceBadge key={source} source={source} variant="required" />
              ))
            ) : (
              <span className="source-muted">No required source list returned.</span>
            )}
          </div>
        </div>
      </div>

      <div className="requirement-grid">
        <SmallList title="Can Answer Now" items={payload?.can_answer_now} />
        <SmallList title="Cannot Answer Yet" items={payload?.cannot_answer_yet} />
      </div>

      <div className="required-data-section">
        <h4>Required Fields From Sir / Backend</h4>

        {requiredData.length ? (
          <div className="required-data-grid">
            {requiredData.map((data, index) => (
              <RequiredDataCard
                key={`${data?.name || "required"}-${index}`}
                data={data}
              />
            ))}
          </div>
        ) : (
          <p className="source-muted">No required field contract returned.</p>
        )}
      </div>

      <SmallList title="Suggested Next Steps" items={payload?.suggested_next_steps} />

      {payload?.recommended_user_reply ? (
        <div className="recommended-reply-box">
          <h4>Message to Ask for Data</h4>
          <p>{payload.recommended_user_reply}</p>
        </div>
      ) : null}

      {payload?.capability ? (
        <details className="raw-details">
          <summary>View capability router output</summary>
          <JsonBlock data={payload.capability} />
        </details>
      ) : null}
    </div>
  );
}

function RecommendedActionsPanel({ data }) {
  if (!data) {
    return (
      <EmptyState
        title="No recommended actions loaded"
        message="Click Generate Actions to convert latest alerts into operational next steps."
      />
    );
  }

  const actions = Array.isArray(data.recommended_actions)
    ? data.recommended_actions
    : [];

  const owners = Array.isArray(data.owner_breakdown)
    ? data.owner_breakdown
    : [];

  const departments = Array.isArray(data.department_breakdown)
    ? data.department_breakdown
    : [];

  const actionTypes = Array.isArray(data.action_type_breakdown)
    ? data.action_type_breakdown
    : [];

  return (
    <div className="recommended-actions-panel">
      <div className="actions-hero">
        <div>
          <p className="eyebrow">Recommended Actions Engine</p>
          <h3>Operational Next Steps</h3>
          <p>{data.summary}</p>
        </div>

        <span className="actions-pill">
          {formatValue(data.total_actions)} Actions
        </span>
      </div>

      <div className="metric-grid">
        <MetricCard
          title="Total Actions"
          value={data.total_actions}
          subtitle="Generated from alerts"
        />

        <MetricCard
          title="Returned"
          value={data.returned_actions}
          subtitle="Shown below"
        />

        <MetricCard
          title="Owners"
          value={owners.length}
          subtitle="Responsible teams"
        />

        <MetricCard
          title="Action Types"
          value={actionTypes.length}
          subtitle="Work categories"
        />
      </div>

      <div className="insights-two-column">
        <div className="insight-card">
          <h4>Owner Breakdown</h4>

          {owners.length ? (
            <ul className="simple-list">
              {owners.slice(0, 6).map((item) => (
                <li key={item.owner}>
                  <span>{formatLabel(item.owner)}</span>
                  <strong>{formatValue(item.count)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No owner breakdown available.</p>
          )}
        </div>

        <div className="insight-card">
          <h4>Department Breakdown</h4>

          {departments.length ? (
            <ul className="simple-list">
              {departments.slice(0, 6).map((item) => (
                <li key={item.department}>
                  <span>{formatLabel(item.department)}</span>
                  <strong>{formatValue(item.count)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No department breakdown available.</p>
          )}
        </div>
      </div>

      <div className="insight-card">
        <h4>Action Type Breakdown</h4>

        {actionTypes.length ? (
          <ul className="simple-list">
            {actionTypes.slice(0, 8).map((item) => (
              <li key={item.action_type}>
                <span>{formatLabel(item.action_type)}</span>
                <strong>{formatValue(item.count)}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p>No action type breakdown available.</p>
        )}
      </div>

      <div className="recommended-actions-section">
        <h4>Action Cards</h4>

        {actions.length ? (
          <div className="recommended-actions-grid">
            {actions.map((action, index) => (
              <div
                className="recommended-action-card"
                key={`${action.vehicle}-${action.action_type}-${index}`}
              >
                <div className="action-card-header">
                  <span
                    className={`action-priority priority-${String(
                      action.priority || "medium"
                    ).toLowerCase()}`}
                  >
                    {formatLabel(action.priority || "medium")}
                  </span>
                </div>

                <h5>{action.title}</h5>

                <p>
                  <strong>Owner:</strong> {formatValue(action.owner)}
                </p>

                <p>
                  <strong>Vehicle:</strong> {formatValue(action.vehicle)} •{" "}
                  <strong>Location:</strong> {formatValue(action.location)}
                </p>

                <p>
                  <strong>Department:</strong> {formatValue(action.department)} •{" "}
                  <strong>Type:</strong> {formatLabel(action.alert_type)}
                </p>

                <p>
                  <strong>Reason:</strong> {formatValue(action.reason)}
                </p>

                <strong>{formatValue(action.suggested_action)}</strong>

                <div className="execution-note">
                  {action.can_execute_now
                    ? "Executable now"
                    : "Recommendation only — write APIs not connected"}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="source-muted">No action cards returned.</p>
        )}
      </div>

      {data.execution_mode ? (
        <div className="execution-mode-box">
          <h4>Execution Mode</h4>
          <p>{data.execution_mode.reason}</p>
        </div>
      ) : null}

      <details className="raw-details">
        <summary>View raw recommended actions response</summary>
        <JsonBlock data={data} />
      </details>
    </div>
  );
}

function CriticalAlertsPanel({ data }) {
  if (!data) {
    return (
      <EmptyState
        title="No critical alerts loaded"
        message="Click Load Critical Alerts to see urgent operational issues."
      />
    );
  }

  const alerts = Array.isArray(data.critical_alerts) ? data.critical_alerts : [];
  const departments = Array.isArray(data.department_breakdown)
    ? data.department_breakdown
    : [];
  const alertTypes = Array.isArray(data.alert_type_breakdown)
    ? data.alert_type_breakdown
    : [];
  const actions = Array.isArray(data.recommended_actions)
    ? data.recommended_actions
    : [];

  return (
    <div className="critical-alerts-panel">
      <div className="critical-hero">
        <div>
          <p className="eyebrow">Critical Alerts</p>
          <h3>Urgent Operations Review</h3>
          <p>{data.summary}</p>
        </div>

        <span className="critical-pill">
          {formatValue(data.total_critical_alerts)} Critical
        </span>
      </div>

      <div className="metric-grid">
        <MetricCard
          title="Critical Alerts"
          value={data.total_critical_alerts}
          subtitle="Latest saved run"
        />

        <MetricCard
          title="Returned"
          value={data.returned_alerts}
          subtitle="Shown in table"
        />

        <MetricCard
          title="Departments"
          value={departments.length}
          subtitle="Affected teams"
        />

        <MetricCard
          title="Alert Types"
          value={alertTypes.length}
          subtitle="Critical issue categories"
        />
      </div>

      <div className="insights-two-column">
        <div className="insight-card">
          <h4>Department Breakdown</h4>

          {departments.length ? (
            <ul className="simple-list">
              {departments.slice(0, 6).map((item) => (
                <li key={item.department}>
                  <span>{formatLabel(item.department)}</span>
                  <strong>{formatValue(item.count)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No department breakdown available.</p>
          )}
        </div>

        <div className="insight-card">
          <h4>Alert Type Breakdown</h4>

          {alertTypes.length ? (
            <ul className="simple-list">
              {alertTypes.slice(0, 6).map((item) => (
                <li key={item.alert_type}>
                  <span>{formatLabel(item.alert_type)}</span>
                  <strong>{formatValue(item.count)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No alert type breakdown available.</p>
          )}
        </div>
      </div>

      <div className="recommended-actions-section">
        <h4>Critical Recommended Actions</h4>

        {actions.length ? (
          <div className="recommended-actions-grid">
            {actions.map((action, index) => (
              <div className="recommended-action-card" key={`${action.title}-${index}`}>
                <div className="action-card-header">
                  <span
                    className={`action-priority priority-${String(
                      action.priority || "high"
                    ).toLowerCase()}`}
                  >
                    {formatLabel(action.priority || "high")}
                  </span>
                </div>

                <h5>{action.title}</h5>
                <strong>{action.action}</strong>
              </div>
            ))}
          </div>
        ) : (
          <p className="source-muted">No recommended actions returned.</p>
        )}
      </div>

      <div className="critical-alerts-section">
        <h4>Critical Alert Items</h4>

        {alerts.length ? (
          <div className="table-wrap">
            <table className="alert-table">
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Type</th>
                  <th>Vehicle</th>
                  <th>Location</th>
                  <th>Issue</th>
                  <th>Recommendation</th>
                </tr>
              </thead>

              <tbody>
                {alerts.map((alert, index) => (
                  <tr key={`${alert.vehicle}-${alert.alert_type}-${index}`}>
                    <td>{formatValue(alert.department)}</td>
                    <td>{formatLabel(alert.alert_type)}</td>
                    <td>{formatValue(alert.vehicle)}</td>
                    <td>{formatValue(alert.location)}</td>
                    <td>{formatValue(alert.message)}</td>
                    <td>{formatValue(alert.recommendation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No critical items returned"
            message="No critical rows were available in the latest saved run."
          />
        )}
      </div>

      <details className="raw-details">
        <summary>View raw critical alerts response</summary>
        <JsonBlock data={data} />
      </details>
    </div>
  );
}

function TodayInsightsPanel({ insights }) {
  if (!insights) {
    return (
      <EmptyState
        title="No AI insights loaded"
        message="Click Generate Insights after loading dashboard data."
      />
    );
  }

  const metrics = insights.metrics || {};
  const topDepartment = insights.top_risk_department;
  const topAlertType = insights.top_alert_type;

  const actions = Array.isArray(insights.recommended_actions)
    ? insights.recommended_actions
    : [];

  const criticalAlerts = Array.isArray(insights.critical_alerts)
    ? insights.critical_alerts
    : [];

  const topAlertTypes = Array.isArray(insights.top_alert_types)
    ? insights.top_alert_types
    : [];

  return (
    <div className="today-insights-panel">
      <div className="insights-hero">
        <div>
          <p className="eyebrow">Today’s AI Insights</p>
          <h3>Operations Snapshot</h3>
          <p>{insights.summary}</p>
        </div>

        <span className="insights-pill">AI Generated</span>
      </div>

      <div className="metric-grid">
        <MetricCard
          title="Total Alerts"
          value={metrics.total_alerts}
          subtitle="Current alert volume"
        />

        <MetricCard
          title="Critical Alerts"
          value={metrics.critical_alerts}
          subtitle="Highest priority"
        />

        <MetricCard
          title="High Alerts"
          value={metrics.high_alerts}
          subtitle="Needs attention"
        />

        <MetricCard
          title="Departments"
          value={metrics.departments}
          subtitle="Alert groups"
        />
      </div>

      <div className="insights-two-column">
        <div className="insight-card">
          <h4>Top Risk Department</h4>

          {topDepartment ? (
            <>
              <strong>{topDepartment.department}</strong>
              <p>
                {formatValue(topDepartment.total_alerts)} total alerts •{" "}
                {formatValue(topDepartment.critical)} critical •{" "}
                {formatValue(topDepartment.high)} high
              </p>
            </>
          ) : (
            <p>No department ranking available.</p>
          )}
        </div>

        <div className="insight-card">
          <h4>Top Alert Type</h4>

          {topAlertType ? (
            <>
              <strong>{formatLabel(topAlertType.alert_type)}</strong>
              <p>{formatValue(topAlertType.count)} cases detected.</p>
            </>
          ) : (
            <p>No alert type ranking available.</p>
          )}
        </div>
      </div>

      <div className="recommended-actions-section">
        <h4>Recommended Actions</h4>

        {actions.length ? (
          <div className="recommended-actions-grid">
            {actions.map((action, index) => (
              <div className="recommended-action-card" key={`${action.title}-${index}`}>
                <div className="action-card-header">
                  <span
                    className={`action-priority priority-${String(
                      action.priority || "medium"
                    ).toLowerCase()}`}
                  >
                    {formatLabel(action.priority || "medium")}
                  </span>
                </div>

                <h5>{action.title}</h5>
                <p>{action.reason}</p>
                <strong>{action.suggested_action}</strong>
              </div>
            ))}
          </div>
        ) : (
          <p className="source-muted">No recommended actions returned.</p>
        )}
      </div>

      <div className="insights-two-column">
        <div className="insight-card">
          <h4>Top Alert Types</h4>

          {topAlertTypes.length ? (
            <ul className="simple-list">
              {topAlertTypes.slice(0, 6).map((item) => (
                <li key={item.alert_type}>
                  <span>{formatLabel(item.alert_type)}</span>
                  <strong>{formatValue(item.count)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No alert type data available.</p>
          )}
        </div>

        <div className="insight-card">
          <h4>Data Limitations</h4>

          {Array.isArray(insights.data_limitations) &&
          insights.data_limitations.length ? (
            <ul>
              {insights.data_limitations.map((item, index) => (
                <li key={`limit-${index}`}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>No limitations returned.</p>
          )}
        </div>
      </div>

      <div className="critical-alerts-section">
        <h4>Critical Alerts Sample</h4>

        {criticalAlerts.length ? (
          <div className="table-wrap">
            <table className="alert-table">
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Vehicle</th>
                  <th>Location</th>
                  <th>Issue</th>
                  <th>Recommendation</th>
                </tr>
              </thead>

              <tbody>
                {criticalAlerts.map((alert, index) => (
                  <tr key={`${alert.vehicle}-${index}`}>
                    <td>{formatValue(alert.department)}</td>
                    <td>{formatValue(alert.vehicle)}</td>
                    <td>{formatValue(alert.location)}</td>
                    <td>{formatValue(alert.message)}</td>
                    <td>{formatValue(alert.recommendation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No critical alert sample"
            message="No critical alerts were returned in the latest sample."
          />
        )}
      </div>

      <details className="raw-details">
        <summary>View raw insights response</summary>
        <JsonBlock data={insights} />
      </details>
    </div>
  );
}

function DashboardSummaryCards({ dashboardSummary, departments }) {
  const payload = getDashboardPayload(dashboardSummary);

  if (!payload) {
    return (
      <EmptyState
        title="No dashboard data loaded"
        message="Click Load Dashboard after saving your API key."
      />
    );
  }

  const summary = getSummaryObject(payload);

  const departmentTotalAlerts = departments.reduce(
    (sum, department) => sum + getDepartmentCount(department),
    0
  );

  const departmentCriticalAlerts = departments.reduce(
    (sum, department) => sum + Number(getSeverityCount(department, "critical")),
    0
  );

  const departmentHighAlerts = departments.reduce(
    (sum, department) => sum + Number(getSeverityCount(department, "high")),
    0
  );

  const departmentMediumAlerts = departments.reduce(
    (sum, department) => sum + Number(getSeverityCount(department, "medium")),
    0
  );

  const departmentLowAlerts = departments.reduce(
    (sum, department) => sum + Number(getSeverityCount(department, "low")),
    0
  );

  const totalAlerts =
    Number(
      pick(summary, ["total_alerts", "alert_count", "alerts_count", "total"], 0)
    ) || departmentTotalAlerts;

  const criticalAlerts =
    Number(getSeverityCount(summary, "critical")) || departmentCriticalAlerts;

  const highAlerts =
    Number(getSeverityCount(summary, "high")) || departmentHighAlerts;

  const mediumAlerts =
    Number(getSeverityCount(summary, "medium")) || departmentMediumAlerts;

  const lowAlerts =
    Number(getSeverityCount(summary, "low")) || departmentLowAlerts;

  const latestRunId = pick(
    payload,
    ["run_id", "latest_run_id", "latest_alert_run.run_id", "summary.run_id"],
    "-"
  );

  const generatedAt = pick(
    payload,
    [
      "timestamp_utc",
      "generated_at",
      "created_at",
      "latest_alert_run.timestamp_utc",
      "latest_alert_run.created_at",
      "summary.timestamp_utc",
    ],
    "-"
  );

  return (
    <>
      <div className="metric-grid">
        <MetricCard
          title="Total Alerts"
          value={totalAlerts}
          subtitle="Across latest alert run"
        />

        <MetricCard
          title="Departments"
          value={departments.length}
          subtitle="Department alert groups"
        />

        <MetricCard
          title="Critical Alerts"
          value={criticalAlerts}
          subtitle="Highest priority"
        />

        <MetricCard
          title="High Alerts"
          value={highAlerts}
          subtitle="Needs attention"
        />
      </div>

      <div className="severity-strip">
        <div className="severity-item critical">
          <span>Critical</span>
          <strong>{formatValue(criticalAlerts)}</strong>
        </div>

        <div className="severity-item high">
          <span>High</span>
          <strong>{formatValue(highAlerts)}</strong>
        </div>

        <div className="severity-item medium">
          <span>Medium</span>
          <strong>{formatValue(mediumAlerts)}</strong>
        </div>

        <div className="severity-item low">
          <span>Low</span>
          <strong>{formatValue(lowAlerts)}</strong>
        </div>
      </div>

      <div className="info-grid">
        <div className="info-card">
          <span>Latest Run ID</span>
          <strong>{compactText(latestRunId, 42)}</strong>
        </div>

        <div className="info-card">
          <span>Generated At</span>
          <strong>{compactText(generatedAt, 42)}</strong>
        </div>
      </div>

      <details className="raw-details">
        <summary>View raw dashboard response</summary>
        <JsonBlock data={dashboardSummary} />
      </details>
    </>
  );
}

function DepartmentCard({ department, active, onClick }) {
  const departmentName = getDepartmentName(department);
  const total = getDepartmentCount(department);
  const critical = getSeverityCount(department, "critical");
  const high = getSeverityCount(department, "high");
  const medium = getSeverityCount(department, "medium");
  const low = getSeverityCount(department, "low");

  return (
    <button
      className={`department-card ${active ? "active" : ""}`}
      onClick={onClick}
    >
      <div className="department-card-main">
        <h3>{departmentName}</h3>

        <div className="mini-severity-row">
          <span className="mini critical">C: {formatValue(critical)}</span>
          <span className="mini high">H: {formatValue(high)}</span>
          <span className="mini medium">M: {formatValue(medium)}</span>
          <span className="mini low">L: {formatValue(low)}</span>
        </div>
      </div>

      <strong>{formatValue(total)}</strong>
    </button>
  );
}

function DepartmentDetailView({ departmentDetail }) {
  const [filters, setFilters] = useState({
    search: "",
    severity: "all",
    alertType: "all",
    location: "",
    sortBy: "critical_first",
    limit: "50",
  });

  const payload = getDepartmentDetailPayload(departmentDetail);

  if (!payload) {
    return (
      <EmptyState
        title="No department detail loaded"
        message="Select a department card to view details."
      />
    );
  }

  const summary = getSummaryObject(payload);
  const alertTypeCount = getAlertTypeCount(payload);
  const items = getAlertItems(payload);

  const total = pick(summary, ["total_alerts", "total", "count"], 0);
  const critical = getSeverityCount(summary, "critical");
  const high = getSeverityCount(summary, "high");
  const medium = getSeverityCount(summary, "medium");
  const low = getSeverityCount(summary, "low");

  const alertTypeEntries = Object.entries(alertTypeCount || {});

  const alertTypeOptions = Array.from(
    new Set(items.map((item) => getAlertType(item)).filter(Boolean))
  ).sort();

  const locationOptions = Array.from(
    new Set(items.map((item) => getAlertLocation(item)).filter(Boolean))
  ).sort();

  const filteredItems = sortAlertItems(
    items.filter((item) => {
      const severity = getAlertSeverity(item);
      const alertType = getAlertType(item);
      const vehicle = getAlertVehicle(item);
      const location = getAlertLocation(item);
      const message = getAlertMessage(item);
      const dateDisplay = formatAlertDate(getAlertDateValue(item));

      const searchText = [
        severity,
        alertType,
        vehicle,
        location,
        message,
        dateDisplay,
      ]
        .join(" ")
        .toLowerCase();

      const searchNeedle = filters.search.trim().toLowerCase();
      const locationNeedle = filters.location.trim().toLowerCase();

      if (filters.severity !== "all" && severity !== filters.severity) {
        return false;
      }

      if (filters.alertType !== "all" && alertType !== filters.alertType) {
        return false;
      }

      if (
        locationNeedle &&
        !String(location || "").toLowerCase().includes(locationNeedle)
      ) {
        return false;
      }

      if (searchNeedle && !searchText.includes(searchNeedle)) {
        return false;
      }

      return true;
    }),
    filters.sortBy
  );

  const visibleItems = filteredItems.slice(0, Number(filters.limit));

  function updateFilter(key, value) {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
    }));
  }

  function resetFilters() {
    setFilters({
      search: "",
      severity: "all",
      alertType: "all",
      location: "",
      sortBy: "critical_first",
      limit: "50",
    });
  }

  return (
    <div className="department-detail-view">
      <div className="metric-grid">
        <MetricCard
          title="Total Alerts"
          value={total}
          subtitle="Selected department"
        />

        <MetricCard
          title="Critical"
          value={critical}
          subtitle="Highest priority"
        />

        <MetricCard title="High" value={high} subtitle="Needs attention" />

        <MetricCard
          title="Medium / Low"
          value={`${formatValue(medium)} / ${formatValue(low)}`}
          subtitle="Remaining alerts"
        />
      </div>

      {alertTypeEntries.length ? (
        <div className="alert-type-section">
          <h3>Alert Type Breakdown</h3>

          <div className="alert-type-grid">
            {alertTypeEntries.map(([type, count]) => (
              <div className="alert-type-card" key={type}>
                <span>{type.replaceAll("_", " ")}</span>
                <strong>{formatValue(count)}</strong>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="alert-filter-panel">
        <div className="filter-header">
          <div>
            <p className="eyebrow">Department Filters</p>
            <h3>Filter & Sort Alerts</h3>
          </div>

          <button className="ghost-button" onClick={resetFilters}>
            Reset Filters
          </button>
        </div>

        <div className="filter-grid">
          <label>
            Search vehicle/message
            <input
              value={filters.search}
              onChange={(event) => updateFilter("search", event.target.value)}
              placeholder="KA05 / insurance / service..."
            />
          </label>

          <label>
            Severity
            <select
              value={filters.severity}
              onChange={(event) => updateFilter("severity", event.target.value)}
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>

          <label>
            Alert Type
            <select
              value={filters.alertType}
              onChange={(event) => updateFilter("alertType", event.target.value)}
            >
              <option value="all">All Alert Types</option>
              {alertTypeOptions.map((type) => (
                <option value={type} key={type}>
                  {formatLabel(type)}
                </option>
              ))}
            </select>
          </label>

          <label>
            Location
            <input
              list="department-location-options"
              value={filters.location}
              onChange={(event) => updateFilter("location", event.target.value)}
              placeholder="Search location..."
            />

            <datalist id="department-location-options">
              {locationOptions.map((location) => (
                <option value={location} key={location} />
              ))}
            </datalist>
          </label>

          <label>
            Sort By
            <select
              value={filters.sortBy}
              onChange={(event) => updateFilter("sortBy", event.target.value)}
            >
              <option value="critical_first">Critical First</option>
              <option value="most_overdue">Most Overdue First</option>
              <option value="newest_date">Newest Date First</option>
              <option value="oldest_date">Oldest Date First</option>
              <option value="vehicle">Vehicle Number</option>
              <option value="location">Location</option>
              <option value="alert_type">Alert Type</option>
            </select>
          </label>

          <label>
            Show Limit
            <select
              value={filters.limit}
              onChange={(event) => updateFilter("limit", event.target.value)}
            >
              <option value="25">25 alerts</option>
              <option value="50">50 alerts</option>
              <option value="100">100 alerts</option>
              <option value="250">250 alerts</option>
            </select>
          </label>
        </div>

        <div className="filter-result-bar">
          Showing <strong>{formatValue(visibleItems.length)}</strong> of{" "}
          <strong>{formatValue(filteredItems.length)}</strong> filtered alerts from{" "}
          <strong>{formatValue(items.length)}</strong> loaded alerts.
        </div>
      </div>

      <div className="alert-table-section">
        <h3>Filtered Alert Items</h3>

        {visibleItems.length ? (
          <div className="table-wrap">
            <table className="alert-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Alert Date</th>
                  <th>Type</th>
                  <th>Vehicle</th>
                  <th>Location</th>
                  <th>Message</th>
                </tr>
              </thead>

              <tbody>
                {visibleItems.map((item, index) => {
                  const severity = getAlertSeverity(item);
                  const type = getAlertType(item);
                  const message = getAlertMessage(item);
                  const vehicle = getAlertVehicle(item);
                  const location = getAlertLocation(item);
                  const dateValue = getAlertDateValue(item);

                  return (
                    <tr key={`${vehicle}-${type}-${index}`}>
                      <td>
                        <StatusPill status={severity} />
                      </td>
                      <td>{formatAlertDate(dateValue)}</td>
                      <td>{formatLabel(type)}</td>
                      <td>{formatValue(vehicle)}</td>
                      <td>{formatValue(location)}</td>
                      <td>{formatValue(message)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No alerts match these filters"
            message="Try changing severity, alert type, location, search text, or sorting."
          />
        )}
      </div>

      <details className="raw-details">
        <summary>View raw department response</summary>
        <JsonBlock data={departmentDetail} />
      </details>
    </div>
  );
}


function App() {
  const chatBottomRef = useRef(null);

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
  const [todayInsights, setTodayInsights] = useState(null);
  const [criticalAlerts, setCriticalAlerts] = useState(null);
  const [recommendedActions, setRecommendedActions] = useState(null);

  const [selectedDepartment, setSelectedDepartment] = useState("");
  const [departmentDetail, setDepartmentDetail] = useState(null);

  const [logs, setLogs] = useState([]);

  const [chatInput, setChatInput] = useState("hello");
  const [chatMessages, setChatMessages] = useState([]);

  const [loading, setLoading] = useState({
    status: false,
    dashboard: false,
    insights: false,
    criticalAlerts: false,
    recommendedActions: false,
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

    // Status checks are optional health indicators.
    // Brave and some privacy-focused browsers may fail one of these small checks,
    // while the main dashboard/chat/action endpoints still work.
    setError("");

    const statusErrors = [];

    try {
      const [rootResult, healthResult, readyResult] = await Promise.allSettled([
        apiGet("/"),
        apiGet("/health"),
        apiGet("/ready"),
      ]);

      if (rootResult.status === "fulfilled") {
        setRootInfo(rootResult.value);
      } else {
        setRootInfo({
          version: "-",
          environment: "status unavailable",
        });

        statusErrors.push(`Root: ${rootResult.reason?.message || "failed"}`);
      }

      if (healthResult.status === "fulfilled") {
        setHealth(healthResult.value);
      } else {
        setHealth({
          status: "unavailable",
          service: "health check failed",
        });

        statusErrors.push(`Health: ${healthResult.reason?.message || "failed"}`);
      }

      if (readyResult.status === "fulfilled") {
        setReady(readyResult.value);
      } else {
        setReady({
          status: "unavailable",
          database: "readiness check failed",
        });

        statusErrors.push(`Ready: ${readyResult.reason?.message || "failed"}`);
      }

      if (savedApiKey) {
        const [schedulerResult] = await Promise.allSettled([
          apiGet("/scheduler/status", savedApiKey),
        ]);

        if (schedulerResult.status === "fulfilled") {
          setScheduler(schedulerResult.value);
        } else {
          setScheduler({
            scheduler: {
              enabled: "unavailable",
            },
          });

          statusErrors.push(
            `Scheduler: ${schedulerResult.reason?.message || "failed"}`
          );
        }
      } else {
        setScheduler(null);
      }

      if (statusErrors.length) {
        console.warn("Partial status load issue:", statusErrors);
      }
    } catch (err) {
      console.error("Unexpected status load error:", err);

      setRootInfo({
        version: "-",
        environment: "status unavailable",
      });

      setHealth({
        status: "unavailable",
        service: "health check failed",
      });

      setReady({
        status: "unavailable",
        database: "readiness check failed",
      });

      setScheduler({
        scheduler: {
          enabled: "unavailable",
        },
      });
    } finally {
      setLoading((prev) => ({ ...prev, status: false }));
    }
  }

  async function loadDashboard() {
    if (!requireApiKey()) return;

    setLoading((prev) => ({ ...prev, dashboard: true }));
    setError("");

    try {
      const [summaryData, departmentsData] = await Promise.all([
        apiGet("/dashboard/summary", savedApiKey),
        apiGet("/dashboard/departments", savedApiKey),
      ]);

      const departmentCards = departmentsData.departments || [];

      setDashboardSummary(summaryData);
      setDepartments(departmentCards);

      if (!selectedDepartment && departmentCards.length) {
        setSelectedDepartment(getDepartmentName(departmentCards[0]));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, dashboard: false }));
    }
  }

  async function loadTodayInsights() {
    if (!requireApiKey()) return;

    setLoading((prev) => ({ ...prev, insights: true }));
    setError("");

    try {
      const data = await apiGet("/insights/today?limit=10", savedApiKey);
      setTodayInsights(data.insights || data);
    } catch (err) {
      setTodayInsights(null);
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, insights: false }));
    }
  }

  async function loadCriticalAlerts() {
    if (!requireApiKey()) return;

    setLoading((prev) => ({ ...prev, criticalAlerts: true }));
    setError("");

    try {
      const data = await apiGet("/insights/critical-alerts?limit=25", savedApiKey);
      setCriticalAlerts(data.critical_alerts || data);
    } catch (err) {
      setCriticalAlerts(null);
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, criticalAlerts: false }));
    }
  }

  async function loadRecommendedActions() {
    if (!requireApiKey()) return;

    setLoading((prev) => ({ ...prev, recommendedActions: true }));
    setError("");

    try {
      const data = await apiGet("/insights/recommended-actions?limit=25", savedApiKey);
      setRecommendedActions(data.recommended_actions || data);
    } catch (err) {
      setRecommendedActions(null);
      setError(err.message);
    } finally {
      setLoading((prev) => ({ ...prev, recommendedActions: false }));
    }
  }

  async function loadLogs() {
    if (!requireApiKey()) return;

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
    if (!requireApiKey()) return;
    if (!departmentName) return;

    setLoading((prev) => ({ ...prev, department: true }));
    setError("");

    try {
      const encodedDepartment = encodeURIComponent(departmentName);
      const data = await apiGet(
        `/dashboard/department/${encodedDepartment}?limit=250`,
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

    if (!requireApiKey()) return;

    const cleanMessage = chatInput.trim();

    if (!cleanMessage) {
      setError("Chat message cannot be empty.");
      return;
    }

    setLoading((prev) => ({ ...prev, chat: true }));
    setError("");

    setChatMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: cleanMessage,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);

    setChatInput("");

    try {
      const data = await apiPost(
        "/chat",
        {
          query: cleanMessage,
        },
        savedApiKey
      );

      const payload = getResponsePayload(data);

      const responseText =
        payload?.summary ||
        data?.response?.summary ||
        data?.response?.message ||
        JSON.stringify(data?.response || data, null, 2);

      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: responseText,
          raw: data,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Error: ${err.message}`,
          raw: err.data || null,
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
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

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [chatMessages]);

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
          <a href="#insights">AI Insights</a>
          <a href="#critical-alerts">Critical Alerts</a>
          <a href="#recommended-actions">Recommended Actions</a>
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

        <section id="insights" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">Agentic Layer</p>
              <h2>Today’s AI Insights</h2>
            </div>

            <button onClick={loadTodayInsights} disabled={loading.insights}>
              {loading.insights ? "Generating..." : "Generate Insights"}
            </button>
          </div>

          <TodayInsightsPanel insights={todayInsights} />
        </section>

        <section id="critical-alerts" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">Priority Review</p>
              <h2>Critical Alerts</h2>
            </div>

            <button onClick={loadCriticalAlerts} disabled={loading.criticalAlerts}>
              {loading.criticalAlerts ? "Loading..." : "Load Critical Alerts"}
            </button>
          </div>

          <CriticalAlertsPanel data={criticalAlerts} />
        </section>

        <section id="recommended-actions" className="section">
          <div className="section-header">
            <div>
              <p className="eyebrow">Agentic Recommendations</p>
              <h2>Recommended Actions</h2>
            </div>

            <button
              onClick={loadRecommendedActions}
              disabled={loading.recommendedActions}
            >
              {loading.recommendedActions ? "Generating..." : "Generate Actions"}
            </button>
          </div>

          <RecommendedActionsPanel data={recommendedActions} />
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

          <DashboardSummaryCards
            dashboardSummary={dashboardSummary}
            departments={departments}
          />
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

                return (
                  <DepartmentCard
                    key={`${departmentName}-${index}`}
                    department={department}
                    active={departmentName === selectedDepartment}
                    onClick={() => setSelectedDepartment(departmentName)}
                  />
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

            <DepartmentDetailView departmentDetail={departmentDetail} />
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
              chatMessages.map((message, index) => {
                const payload = getResponsePayload(message.raw);
                const isDataRequirement =
                  message.role === "assistant" &&
                  payload?.answer_type === "data_requirement";

                return (
                  <div
                    key={`${message.role}-${index}`}
                    className={`chat-message ${message.role}`}
                  >
                    <div className="chat-meta">
                      <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
                      <span>{message.timestamp}</span>
                    </div>

                    {isDataRequirement ? (
                      <DataRequirementCard payload={payload} />
                    ) : (
                      <MessageText text={message.text} />
                    )}

                    {message.raw ? (
                      <details>
                        <summary>Raw response</summary>
                        <JsonBlock data={message.raw} />
                      </details>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <EmptyState
                title="No chat yet"
                message="Ask something like: Tell me all the active locations."
              />
            )}

            <div ref={chatBottomRef} />
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