import React from "react";
import GrafanaPanel from "./GrafanaPanel";

const formatMs = (seconds) => {
  const value = Number(seconds);
  if (seconds === null || seconds === undefined || !Number.isFinite(value)) return "N/A";
  return `${(value * 1000).toFixed(1)} ms`;
};

const formatMetric = (value, digits = 3) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return Number(value).toFixed(digits);
};

const formatCount = (value) => {
  const count = Number(value);
  if (value === null || value === undefined || !Number.isFinite(count)) return "N/A";
  return count.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
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

const runtimeStatusLabels = {
  healthy: "Sain",
  warning: "Attention",
  incident: "Incident",
  no_data: "Aucune donnée",
  unavailable: "Indisponible",
};

function RuntimeDistribution({ title, data }) {
  const total = Number(data?.total) || 0;
  const distribution = Object.entries(data?.distribution || {});

  return (
    <div>
      <h4>{title}</h4>
      {total > 0 && distribution.length ? (
        <dl className="definition-list">
          {distribution.map(([label, value]) => (
            <React.Fragment key={label}>
              <dt>{label}</dt>
              <dd>{Math.round((Number(value) / total) * 100)} %</dd>
            </React.Fragment>
          ))}
        </dl>
      ) : (
        <p className="text-block">Aucune prédiction disponible.</p>
      )}
    </div>
  );
}

export default function MonitoringTab({ data }) {
  const metrics = data?.metrics || {};
  const targets = data?.prometheus?.targets || [];
  const ia = data?.ia || {};
  const runtime = ia.runtime || {};
  const iaStatusClass =
    ia.status === "healthy" ? "pill ok" : ia.status === "degraded" ? "pill warning" : "pill danger";
  const runtimeStatusClass =
    runtime.status === "healthy"
      ? "pill ok"
      : runtime.status === "incident"
        ? "pill danger"
        : runtime.status === "warning"
          ? "pill warning"
          : "pill neutral";
  const runtimeAvailable = runtime.available === true;
  const runtimeHasActivity =
    Number(runtime.predictions_success || 0) + Number(runtime.predictions_error || 0) > 0;
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
            <p>État, performances et activité des modèles de prévision déployés.</p>
          </div>
          <span className={iaStatusClass}>{iaStatusLabels[ia.status] || "Indisponible"}</span>
        </div>

        {!ia.available ? (
          <p className="text-block">{ia.error || "Les artefacts IA ne sont pas disponibles."}</p>
        ) : (
          <>
            <section className="ia-section">
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
            </section>

            <section className="ia-section">
              <h3>Performances de validation</h3>
              <div className="two-columns">
                <div>
                  <h4>Classification</h4>
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
                  <h4>Régression</h4>
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
            </section>
          </>
        )}

        <section className="ia-section">
          <div className="panel-heading">
            <div>
              <h3>Activité IA en fonctionnement</h3>
              <p>Données collectées automatiquement par Prometheus lors des inférences.</p>
            </div>
            <span className={runtimeStatusClass}>
              {runtimeStatusLabels[runtime.status] || "Indisponible"}
            </span>
          </div>

          {!runtimeAvailable ? (
            <p className="text-block">Données runtime indisponibles. La supervision du modèle déployé reste accessible.</p>
          ) : (
            <>
              <div className="metric-grid">
                <article className="metric-card">
                  <strong>{formatCount(runtime.predictions_success)}</strong>
                  <span>Prédictions réussies</span>
                  <p>Observées depuis le démarrage du processus API courant.</p>
                </article>
                <article className="metric-card">
                  <strong>{formatCount(runtime.predictions_error)}</strong>
                  <span>Erreurs d’inférence</span>
                  <p>Échecs remontés par le modèle déployé.</p>
                </article>
                <article className="metric-card">
                  <strong>{formatMs(runtime.latency_p95_seconds)}</strong>
                  <span>Latence P95</span>
                  <p>Calculée sur les cinq dernières minutes.</p>
                </article>
                <article className="metric-card">
                  <strong>{runtimeStatusLabels[runtime.status] || "Indisponible"}</strong>
                  <span>État runtime</span>
                  <p>Synthèse opérationnelle des métriques disponibles.</p>
                </article>
              </div>

              {!runtimeHasActivity ? (
                <p className="text-block">
                  Aucune activité IA observée depuis le démarrage. Effectuez une prédiction pour alimenter les métriques runtime.
                </p>
              ) : (
                <div className="two-columns ia-runtime-distributions">
                  <RuntimeDistribution title="Classification runtime" data={runtime.classification} />
                  <RuntimeDistribution title="Régression runtime" data={runtime.regression} />
                </div>
              )}

              {data?.grafana?.ia_dashboard_url && (
                <a
                  href={data.grafana.ia_dashboard_url}
                  target="_blank"
                  rel="noreferrer"
                  className="secondary-button"
                >
                  Voir le détail dans Grafana
                </a>
              )}
            </>
          )}
        </section>

        <section className="ia-section">
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
      </section>
    </div>
  );
}
