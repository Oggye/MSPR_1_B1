import React from "react";

const renderReportValue = (value) => {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "N/A");
};

const getLineClass = (line = "") => {
  const upper = line.toUpperCase();
  if (upper.includes("FAILED")) return "log-line failed";
  if (upper.includes("PASSED")) return "log-line passed";
  if (upper.includes("WARNING")) return "log-line warning";
  if (upper.includes("ERROR")) return "log-line failed";
  return "log-line";
};

const getStatusClass = (status) => {
  if (status === "passed") return "pill ok";
  if (status === "failed") return "pill danger";
  if (status === "running") return "pill warning";
  return "pill neutral";
};

const getStatusLabel = (status) => {
  if (status === "passed") return "Termine (OK)";
  if (status === "failed") return "Termine (KO)";
  if (status === "running") return "En cours";
  return "Idle";
};

const summarizeReportStage = (stage = {}) => Object.values(stage).reduce(
  (total, value) => {
    const rows = Array.isArray(value) ? value : [value];
    return rows.reduce((subtotal, item) => ({
      files: subtotal.files + (Array.isArray(value) ? 1 : Number(item?.fichiers || 0)),
      lines: subtotal.lines + Number(item?.lignes || 0),
    }), total);
  },
  { files: 0, lines: 0 }
);

const formatNumber = (value) => Number(value || 0).toLocaleString("fr-FR");

const formatDate = (value) => {
  if (!value) return "Jamais";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("fr-FR");
};

export default function TestsTab({ data, actionState, testCategories, onRunDiagnostic, onRunTestsByCategory }) {
  const quality = data?.reports?.quality || {};
  const hasDiagnosticAction = actionState?.diagnostic !== null;
  const diagnostic = hasDiagnosticAction ? actionState?.diagnostic?.report : data?.reports?.diagnostic;
  const diagnosticMeta = actionState?.diagnostic?.report_meta || data?.reports?.diagnostic_meta || {};
  const qualitySummary = quality.summary || {};
  const dataQuality = quality.traceability?.data_quality || {};
  const totals = data?.db_totals || {};
  const tests = actionState?.tests || {};
  const rawSummary = summarizeReportStage(diagnostic?.raw);
  const processedSummary = summarizeReportStage(diagnostic?.processed);
  const warehouseSummary = summarizeReportStage(diagnostic?.warehouse);
  const diagnosticFiles = rawSummary.files + processedSummary.files + warehouseSummary.files;
  const diagnosticLines = rawSummary.lines + processedSummary.lines + warehouseSummary.lines;
  const diagnosticOk = diagnostic?.statut === "OK" && !diagnosticMeta.stale;

  return (
    <div className="tab-content">
      <section className="metric-grid">
        <article className="metric-card">
          <span>Sources traitees</span>
          <strong>{qualitySummary.total_sources_processed || 0}</strong>
          <p>Dernier rapport genere par l'ETL.</p>
        </article>
        <article className="metric-card">
          <span>Lignes estimees</span>
          <strong>{qualitySummary.total_records_estimated || 0}</strong>
          <p>Total estime dans le rapport qualite.</p>
        </article>
        <article className="metric-card">
          <span>Pays</span>
          <strong>{dataQuality.total_countries || 0}</strong>
          <p>{dataQuality.unknown_countries || 0} pays inconnus.</p>
        </article>
        <article className="metric-card">
          <span>Total trains</span>
          <strong>{totals.total_trains ?? 0}</strong>
          <p>Nuit: {totals.total_night_trains ?? 0} | Jour: {totals.total_day_trains ?? 0}</p>
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Rapport de qualite</h2>
            <p>Valeurs du dernier rapport produit dans le warehouse.</p>
          </div>
          <span className={qualitySummary.success ? "pill ok" : "pill warning"}>
            {qualitySummary.success ? "OK" : "A verifier"}
          </span>
        </div>
        <div className="report-grid">
          {(quality.reports || []).map((report) => (
            <article className="report-item" key={report.source}>
              <h3>{report.source}</h3>
              {Object.entries(report)
                .filter(([key]) => key !== "source")
                .slice(0, 6)
                .map(([key, value]) => (
                  <p key={key}>
                    <span>{key}</span>
                    <strong>{renderReportValue(value)}</strong>
                  </p>
                ))}
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Diagnostic ETL</h2>
            <p>Controle les donnees RAW, PROCESSED et WAREHOUSE actuellement presentes.</p>
          </div>
          <button type="button" className="primary-button" onClick={onRunDiagnostic} disabled={actionState?.runningDiagnostic}>
            {actionState?.runningDiagnostic ? "Diagnostic en cours" : (diagnostic ? "Relancer le diagnostic" : "Lancer le diagnostic")}
          </button>
        </div>
        {actionState?.diagnostic?.error && <pre className="console-output danger">{actionState.diagnostic.error}</pre>}
        {actionState?.diagnostic?.stderr && <pre className="console-output danger">{actionState.diagnostic.stderr}</pre>}
        {diagnostic ? (
          <>
            <div className="metric-grid">
              <article className="metric-card">
                <span>Statut global</span>
                <strong>{diagnosticOk ? "OK" : "A verifier"}</strong>
                <p>{formatDate(diagnostic.date_diagnostic || diagnosticMeta.report_modified_at)}</p>
              </article>
              <article className="metric-card">
                <span>Fichiers analyses</span>
                <strong>{formatNumber(diagnosticFiles)}</strong>
                <p>{formatNumber(diagnosticLines)} lignes au total.</p>
              </article>
              {[
                ["RAW", rawSummary],
                ["PROCESSED", processedSummary],
                ["WAREHOUSE", warehouseSummary],
              ].map(([label, summary]) => (
                <article className="metric-card" key={label}>
                  <span>Etat {label}</span>
                  <strong>{summary.files > 0 ? "OK" : "A verifier"}</strong>
                  <p>{formatNumber(summary.files)} fichiers | {formatNumber(summary.lines)} lignes</p>
                </article>
              ))}
            </div>
            {diagnosticMeta.stale && (
              <p className="alert-banner warning">Le rapport est plus ancien que les donnees ETL. Un nouveau diagnostic est requis.</p>
            )}
            <details>
              <summary>Details techniques du diagnostic</summary>
              {actionState?.diagnostic?.stdout && <pre className="console-output">{actionState.diagnostic.stdout}</pre>}
              <pre className="console-output">{JSON.stringify(diagnostic, null, 2)}</pre>
            </details>
          </>
        ) : (
          <p className="muted">Aucun rapport diagnostic disponible pour le moment.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Tests backend</h2>
            <p>Execution detaillee en temps reel, par categorie independante.</p>
          </div>
        </div>
        <div className="tab-content">
          {(testCategories || []).map((category) => {
            const state = tests[category.key] || {};
            return (
              <article className="panel" key={category.key}>
                <div className="panel-heading">
                  <div>
                    <h3>{category.label}</h3>
                    <p>
                      Derniere execution : {formatDate(state.lastRun)}
                      {state.summary?.passed !== undefined ? ` | ${state.summary.passed} reussis` : ""}
                      {state.summary?.failed !== undefined ? ` | ${state.summary.failed} echoues` : ""}
                    </p>
                  </div>
                  <div className="header-actions">
                    <span className={getStatusClass(state.status)}>{getStatusLabel(state.status)}</span>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onRunTestsByCategory(category.key)}
                      disabled={state.running}
                    >
                      {state.running ? "Execution..." : "Lancer"}
                    </button>
                  </div>
                </div>
                {state.error && <pre className="console-output danger">{state.error}</pre>}
                {(state.lines || []).length === 0 ? (
                  <p className="muted">Aucun log pour cette categorie.</p>
                ) : (
                  <details>
                    <summary>Logs techniques ({state.count || 0})</summary>
                    <div className="console-output">
                      {(state.lines || []).map((line, idx) => (
                        <div key={`${category.key}-${idx}`} className={getLineClass(line)}>{line}</div>
                      ))}
                    </div>
                  </details>
                )}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
