import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  getPredictionContext,
  predictClassification,
  predictRegression,
} from '../../services/api';

import './IaPage.css';


function Badge({ label, variant }) {
  return (
    <span className={`ia-badge ia-badge--${variant}`}>
      {label}
    </span>
  );
}


function riskVariant(level) {
  if (level === 'Faible') return 'success';
  if (level === 'Modéré') return 'warning';
  if (level === 'Élevé') return 'danger';
  if (level === 'Critique') return 'critical';
  return 'neutral';
}


function trendVariant(label) {
  if (label === 'Croissance') return 'success';
  if (label === 'Déclin') return 'danger';
  return 'neutral';
}


function formatValue(value, digits = 2) {
  return Number(value || 0).toLocaleString('fr-FR', {
    maximumFractionDigits: digits,
  });
}


function ForecastContextCard({ context }) {
  if (!context) return null;

  return (
    <div className="ia-result__section ia-anim">
      <h4>Base historique de la prévision</h4>

      <div className="ia-drivers">
        <div className="ia-driver">
          <div className="ia-driver__name">
            Activité voyageurs {context.origin_year - 1}
          </div>
          <div className="ia-driver__value">
            {formatValue(context.passengers_previous)}{' '}
            {context.passenger_unit}
          </div>
          <div className="ia-driver__expl">
            Avant-dernière valeur disponible.
          </div>
        </div>

        <div className="ia-driver">
          <div className="ia-driver__name">
            Activité voyageurs {context.origin_year}
          </div>
          <div className="ia-driver__value">
            {formatValue(context.passengers_current)}{' '}
            {context.passenger_unit}
          </div>
          <div className="ia-driver__dir ia-driver__dir--neutral">
            {context.passenger_growth_1y_pct >= 0 ? '+' : ''}
            {Number(context.passenger_growth_1y_pct).toFixed(2)} %
          </div>
          <div className="ia-driver__expl">
            Dernière année réellement disponible dans le warehouse.
          </div>
        </div>

        <div className="ia-driver">
          <div className="ia-driver__name">
            CO₂ {context.origin_year - 1} → {context.origin_year}
          </div>
          <div className="ia-driver__value">
            {formatValue(context.co2_previous)}
            {' → '}
            {formatValue(context.co2_current)}{' '}
            {context.co2_unit}
          </div>
          <div className="ia-driver__dir ia-driver__dir--neutral">
            {context.co2_growth_1y_pct >= 0 ? '+' : ''}
            {Number(context.co2_growth_1y_pct).toFixed(2)} %
          </div>
          <div className="ia-driver__expl">
            Aucune donnée CO₂ future n'est utilisée.
          </div>
        </div>

        <div className="ia-driver">
          <div className="ia-driver__name">
            Offre ferroviaire {context.origin_year}
          </div>
          <div className="ia-driver__value">
            {formatValue(context.train_count_current, 0)} trajets
          </div>
          <div className="ia-driver__expl">
            {context.operator_count_current} opérateurs ·{' '}
            {(Number(context.night_share_current) * 100).toFixed(1)} % nuit ·{' '}
            {(Number(context.real_share_current) * 100).toFixed(1)} % réels.
          </div>
        </div>
      </div>
    </div>
  );
}


function MetricsBlock({ metadata, axis, horizon }) {
  const finalHoldout = metadata?.metrics || {};
  const horizonMetrics = finalHoldout?.by_horizon?.[String(horizon)];

  if (!horizonMetrics) return null;

  return (
    <div className="ia-result__section ia-anim">
      <h4>Qualité mesurée sur le holdout temporel</h4>

      <div className="ia-drivers">
        {axis === 'classification' ? (
          <>
            <div className="ia-driver">
              <div className="ia-driver__name">F1 horizon N+{horizon}</div>
              <div className="ia-driver__value">
                {Number(horizonMetrics.f1 || 0).toFixed(3)}
              </div>
            </div>

            <div className="ia-driver">
              <div className="ia-driver__name">ROC-AUC horizon N+{horizon}</div>
              <div className="ia-driver__value">
                {horizonMetrics.roc_auc != null
                  ? Number(horizonMetrics.roc_auc).toFixed(3)
                  : 'N/A'}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="ia-driver">
              <div className="ia-driver__name">MAE horizon N+{horizon}</div>
              <div className="ia-driver__value">
                {formatValue(horizonMetrics.mae)} MIO_PKM
              </div>
            </div>

            <div className="ia-driver">
              <div className="ia-driver__name">R² horizon N+{horizon}</div>
              <div className="ia-driver__value">
                {Number(horizonMetrics.r2 || 0).toFixed(3)}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}


function Warnings({ warnings }) {
  if (!warnings?.length) return null;

  return (
    <div className="ia-warnings ia-anim">
      {warnings.map((warning, index) => (
        <div key={`${warning}-${index}`} className="ia-warning">
          <span className="ia-warning__icon">⚠</span>
          <span>{warning}</span>
        </div>
      ))}
    </div>
  );
}


function ClassificationResult({ data }) {
  const probabilityPct = Number(data.probability_decline || 0) * 100;

  return (
    <div className="ia-result">
      <div className="ia-result__header ia-anim">
        <div className="ia-result__prediction">
          <span className="ia-result__label">{data.label}</span>
          <Badge
            label={data.risk_level}
            variant={riskVariant(data.risk_level)}
          />
        </div>

        <div className="ia-result__confidence">
          <span>Probabilité de baisse</span>
          <div className="ia-progress">
            <div
              className="ia-progress__bar"
              style={{ width: `${probabilityPct}%` }}
            />
          </div>
          <span className="ia-result__pct">
            {probabilityPct.toFixed(1)} %
          </span>
        </div>
      </div>

      <div className="ia-result__section ia-anim">
        <h4>Résultat à horizon N+{data.horizon}</h4>
        <p className="ia-result__message">{data.business_message}</p>
        <p>{data.risk_description}</p>
        <p>
          Marge par rapport au seuil de décision de 50 % :{' '}
          <strong>{Number(data.decision_margin).toFixed(1)} points</strong>.
        </p>
      </div>

      <ForecastContextCard context={data.forecast_context} />

      <div className="ia-result__section ia-anim">
        <h4>Signaux utilisés</h4>
        <div className="ia-drivers">
          {(data.key_drivers || []).map(driver => (
            <div key={driver.variable} className="ia-driver">
              <div className="ia-driver__name">{driver.variable}</div>
              <div className="ia-driver__value">{driver.value}</div>
              <div className="ia-driver__expl">{driver.explanation}</div>
            </div>
          ))}
        </div>
      </div>

      <MetricsBlock
        metadata={data.metadata}
        axis="classification"
        horizon={data.horizon}
      />

      <Warnings warnings={data.warnings} />

      <div className="ia-result__meta ia-anim">
        <span>{data.metadata?.model_name}</span>
        <span>·</span>
        <span>Inférence : {data.inference_ms} ms</span>
        <span>·</span>
        <span>Origine : {data.origin_year}</span>
      </div>
    </div>
  );
}


function RegressionResult({ data }) {
  const change = Number(data.trend_vs_origin || 0);
  const intervalPct = Math.round(Number(data.interval_level || 0.9) * 100);

  return (
    <div className="ia-result">
      <div className="ia-result__header ia-anim">
        <div className="ia-result__prediction">
          <span className="ia-result__label">
            {data.prediction_display}
          </span>
          <Badge
            label={data.trend_label}
            variant={trendVariant(data.trend_label)}
          />
        </div>

        <div className="ia-result__trend">
          <span
            className={
              `ia-trend ${
                change >= 0 ? 'ia-trend--up' : 'ia-trend--down'
              }`
            }
          >
            {change >= 0 ? '▲' : '▼'}{' '}
            {Math.abs(change).toFixed(2)} % vs {data.origin_year}
          </span>
        </div>
      </div>

      <div className="ia-result__section ia-anim">
        <h4>Prévision directe N+{data.horizon}</h4>
        <p className="ia-result__message">{data.business_message}</p>
        <p>
          Intervalle indicatif {intervalPct} % :{' '}
          <strong>
            {formatValue(data.prediction_low)} –{' '}
            {formatValue(data.prediction_high)} MIO_PKM
          </strong>
        </p>
      </div>

      <ForecastContextCard context={data.forecast_context} />

      <div className="ia-result__section ia-anim">
        <h4>Pourquoi cette version est plus robuste</h4>
        <p>{data.reliability_note}</p>
      </div>

      <div className="ia-result__section ia-anim">
        <h4>Variables importantes</h4>
        <div className="ia-drivers">
          {(data.key_drivers || []).map(driver => (
            <div key={driver.variable} className="ia-driver">
              <div className="ia-driver__name">{driver.variable}</div>
              <div className="ia-driver__value">{driver.value}</div>
              <div className="ia-driver__expl">{driver.explanation}</div>
            </div>
          ))}
        </div>
      </div>

      <MetricsBlock
        metadata={data.metadata}
        axis="regression"
        horizon={data.horizon}
      />

      <Warnings warnings={data.warnings} />

      <div className="ia-result__meta ia-anim">
        <span>{data.metadata?.model_name}</span>
        <span>·</span>
        <span>Inférence : {data.inference_ms} ms</span>
        <span>·</span>
        <span>Origine : {data.origin_year}</span>
      </div>
    </div>
  );
}


export default function IaPage() {
  const [axis, setAxis] = useState('classification');
  const [context, setContext] = useState(null);
  const [form, setForm] = useState({
    country: 'France',
    year: 2025,
  });

  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [contextLoading, setContextLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPredictionContext()
      .then(response => {
        const payload = response.data;
        setContext(payload);

        setForm(current => ({
          country: payload.countries?.includes(current.country)
            ? current.country
            : (payload.countries?.[0] || ''),
          year: payload.target_min_year,
        }));
      })
      .catch(err => {
        console.error(err);
        setError("Impossible de charger le contexte IA.");
      })
      .finally(() => setContextLoading(false));
  }, []);

  const years = useMemo(() => {
    if (!context) return [];

    const values = [];
    for (
      let year = context.target_min_year;
      year <= context.target_max_year;
      year += 1
    ) {
      values.push(year);
    }
    return values;
  }, [context]);

  const handleSubmit = useCallback(async () => {
    setResult(null);
    setError(null);
    setIsLoading(true);

    try {
      const payload = {
        country: form.country,
        year: Number(form.year),
      };

      const request = axis === 'classification'
        ? predictClassification
        : predictRegression;

      const response = await request(payload);
      setResult(response.data);
    } catch (err) {
      console.error(err);
      const detail = err.response?.data?.detail;

      if (detail && typeof detail === 'object') {
        setError(
          `${detail.error || 'Erreur'} — ${
            detail.message || 'Prédiction impossible.'
          }`,
        );
      } else {
        setError(
          detail
          || err.message
          || 'Une erreur inattendue est survenue.',
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [axis, form]);

  return (
    <div className="ia-page">
      <header className="ia-header">
        <div className="ia-header__eyebrow">
          Analyse prédictive
        </div>
        <h1 className="ia-header__title">
          Prévisions ferroviaires N+1 à N+3
        </h1>
        <p className="ia-header__desc">
          Les prévisions 2025, 2026 et 2027 sont produites directement
          depuis la dernière année observée, sans réinjecter une prédiction
          précédente comme si elle était une donnée réelle.
        </p>
      </header>

      <div className="ia-layout">
        <aside className="ia-panel ia-panel--form">
          <div className="ia-axis-switcher">
            <button
              type="button"
              className={
                `ia-axis-btn ${
                  axis === 'classification'
                    ? 'ia-axis-btn--active'
                    : ''
                }`
              }
              onClick={() => {
                setAxis('classification');
                setResult(null);
                setError(null);
              }}
            >
              Risque de baisse
            </button>

            <button
              type="button"
              className={
                `ia-axis-btn ${
                  axis === 'regression'
                    ? 'ia-axis-btn--active'
                    : ''
                }`
              }
              onClick={() => {
                setAxis('regression');
                setResult(null);
                setError(null);
              }}
            >
              Activité voyageurs
            </button>
          </div>

          <p className="ia-axis-desc">
            {axis === 'classification'
              ? (
                "Risque que l'activité voyageurs à l'horizon choisi soit "
                + "inférieure à la dernière année observée."
              )
              : (
                "Prévision directe de l'activité voyageurs en MIO_PKM "
                + "à horizon N+1, N+2 ou N+3."
              )}
          </p>

          {contextLoading ? (
            <div className="ia-loading-state">
              Chargement du référentiel…
            </div>
          ) : (
            <div className="ia-form">
              <div className="ia-field">
                <label className="ia-field__label" htmlFor="country">
                  Pays
                </label>
                <select
                  id="country"
                  name="country"
                  className="ia-field__input"
                  value={form.country}
                  onChange={event => setForm(current => ({
                    ...current,
                    country: event.target.value,
                  }))}
                >
                  {(context?.countries || []).map(country => (
                    <option key={country} value={country}>
                      {country}
                    </option>
                  ))}
                </select>
              </div>

              <div className="ia-field">
                <label className="ia-field__label" htmlFor="year">
                  Année cible
                  {context && (
                    <span className="ia-field__hint">
                      {context.target_min_year} – {context.target_max_year}
                    </span>
                  )}
                </label>
                <select
                  id="year"
                  name="year"
                  className="ia-field__input"
                  value={form.year}
                  onChange={event => setForm(current => ({
                    ...current,
                    year: Number(event.target.value),
                  }))}
                >
                  {years.map(year => (
                    <option key={year} value={year}>
                      {year} (N+{year - context.forecast_origin_year})
                    </option>
                  ))}
                </select>
              </div>

              {context && (
                <div className="ia-result__section">
                  <h4>Référentiel utilisé</h4>
                  <p>
                    Données : {context.data_min_year}–
                    {context.data_max_year}.
                  </p>
                  <p>
                    Origine des prévisions : {context.forecast_origin_year}.
                  </p>
                  <p>
                    Horizons : N+1 à N+{context.max_horizon}.
                  </p>
                </div>
              )}

              <button
                type="button"
                className={
                  `ia-submit ${
                    isLoading ? 'ia-submit--loading' : ''
                  }`
                }
                onClick={handleSubmit}
                disabled={isLoading || !form.country}
              >
                {isLoading
                  ? 'Analyse en cours…'
                  : 'Lancer la prédiction'}
              </button>
            </div>
          )}
        </aside>

        <section className="ia-panel ia-panel--result">
          {!isLoading && !result && !error && (
            <div className="ia-empty">
              <div className="ia-empty__icon">◎</div>
              <p className="ia-empty__title">
                Choisis un horizon entre 2025 et 2027
              </p>
              <p className="ia-empty__sub">
                La base historique est automatiquement récupérée dans
                PostgreSQL.
              </p>
            </div>
          )}

          {isLoading && (
            <div className="ia-loading-state">
              <p>Calcul de la prévision multi-horizon…</p>
            </div>
          )}

          {error && (
            <div className="ia-error">
              <strong>Prédiction impossible</strong>
              <p>{error}</p>
            </div>
          )}

          {result && axis === 'classification' && (
            <ClassificationResult data={result} />
          )}

          {result && axis === 'regression' && (
            <RegressionResult data={result} />
          )}
        </section>
      </div>
    </div>
  );
}
