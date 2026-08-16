import React from "react";
import GrafanaPanel from "./GrafanaPanel";

const formatMs = (seconds) => {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "N/A";
  return `${(Number(seconds) * 1000).toFixed(1)} ms`;
};

const formatMetric = (value, digits = 3) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toFixed(digits);
};

const formatDate = (value) => {
  if (!value) return "N/A";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "N/A"
    : date.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
};

const iaStatusLabels = {
  healthy: "Opérationnel",
  degraded: "Dégradé",
  unavailable: "Indisponible",
  error: "Erreur",
};

export default function MonitoringTab({ data }) {
  const metrics = data?.metrics || {};
  const targets = data?.prometheus?.targets || [];
  const ia = data?.ia || {};
  const iaStatusClass =
    ia.status === "healthy" ? "pill ok" : ia.status === "degraded" ? "pill warning" : "pill danger";
  const horizons = Array.isArray(ia.horizons) && ia.horizons.length
    ? ia.horizons.map((horizon) => `N+${horizon}`).join(" · ")
    : "N/A";
  const regressionUnit = ia.regression?.unit ? ` ${ia.regression.unit}` : "";
  const artifacts = [
    ["Manifest", ia.artifacts?.manifest],
    ["Classifier", ia.artifacts?.classifier],
    ["Regressor", ia.artifacts?.regressor],
  ];

  return (
    <div className="tab-content">
      <GrafanaPanel data={data} />

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Prometheus</h2>
            <p>Etat des targets scrapees par Prometheus.</p>
          </div>
          <span className={data?.prometheus?.available ? "pill ok" : "pill warning"}>
            {data?.prometheus?.available ? "Disponible" : "Indisponible"}
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Instance</th>
                <th>Etat</th>
                <th>Dernier scrape</th>
                <th>Duree</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((target) => (
                <tr key={target.scrapeUrl}>
                  <td>{target.labels?.job}</td>
                  <td>{target.labels?.instance}</td>
                  <td>
                    <span className={target.health === "up" ? "pill ok" : "pill danger"}>
                      {target.health}
                    </span>
                  </td>
                  <td>{target.lastScrape || "N/A"}</td>
                  <td>{target.lastScrapeDuration ? `${target.lastScrapeDuration.toFixed(4)} s` : "N/A"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel two-columns">
        <div>
          <h2>Requetes suivies</h2>
          <dl className="definition-list">
            <dt>Trafic API</dt>
            <dd>sum(rate(http_requests_total[1m])) * 60 = {(metrics.requests_per_minute || 0).toFixed(2)} / min</dd>
            <dt>Erreurs API</dt>
            <dd>status=~"5..|5xx" = {(metrics.errors_5xx_per_second || 0).toFixed(4)} / s</dd>
            <dt>Latence moyenne</dt>
            <dd>{formatMs(metrics.latency_avg_seconds)}</dd>
            <dt>Latence P95</dt>
            <dd>{formatMs(metrics.latency_p95_seconds)}</dd>
          </dl>
        </div>
        <div>
          <h2>Lecture rapide</h2>
          <p className="text-block">
            Le trafic, les erreurs et les latences viennent directement de Prometheus.
            Grafana affiche le detail visuel avec les memes metriques, ce qui evite les valeurs statiques dans le front.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Supervision IA</h2>
            <p>Disponibilité et validation des artefacts de prévision déployés.</p>
          </div>
          <span className={iaStatusClass}>{iaStatusLabels[ia.status] || "Indisponible"}</span>
        </div>

        {!ia.available ? (
          <p className="text-block">{ia.error || "Les artefacts IA ne sont pas disponibles."}</p>
        ) : (
          <>
            <div>
              <h3>Déploiement</h3>
              <dl className="definition-list">
                <dt>Architecture</dt>
                <dd>{ia.architecture || "N/A"}</dd>
                <dt>Version</dt>
                <dd>{ia.version ?? "N/A"}</dd>
                <dt>Horizons</dt>
                <dd>{horizons}</dd>
                <dt>Dernière génération</dt>
                <dd>{formatDate(ia.last_updated)}</dd>
              </dl>
            </div>

            <div className="two-columns">
              <div>
                <h3>Classification</h3>
                <dl className="definition-list">
                  <dt>Modèle</dt>
                  <dd>{ia.classification?.model || "N/A"}</dd>
                  <dt>F1</dt>
                  <dd>{formatMetric(ia.classification?.overall?.f1)}</dd>
                  <dt>ROC-AUC</dt>
                  <dd>{formatMetric(ia.classification?.overall?.roc_auc)}</dd>
                  <dt>Accuracy</dt>
                  <dd>{formatMetric(ia.classification?.overall?.accuracy)}</dd>
                </dl>
              </div>
              <div>
                <h3>Régression</h3>
                <dl className="definition-list">
                  <dt>Modèle</dt>
                  <dd>{ia.regression?.model || "N/A"}</dd>
                  <dt>MAE</dt>
                  <dd>{formatMetric(ia.regression?.overall?.mae, 2)}{regressionUnit}</dd>
                  <dt>RMSE</dt>
                  <dd>{formatMetric(ia.regression?.overall?.rmse, 2)}{regressionUnit}</dd>
                  <dt>R²</dt>
                  <dd>{formatMetric(ia.regression?.overall?.r2)}</dd>
                  <dt>Baseline</dt>
                  <dd>{ia.regression?.baseline || "N/A"}</dd>
                </dl>
              </div>
            </div>
          </>
        )}

        <h3>Artefacts</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Artefact</th>
                <th>État</th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map(([label, available]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td>
                    <span className={available ? "pill ok" : "pill danger"}>
                      {available ? "Disponible" : "Indisponible"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
