import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

import {
  getOperatorStats,
  getOperatorTimeline,
  getOperators,
  getTrainsByOperatorId,
} from '../../services/api';
import { PagePagination } from '../../components/DataPagination';

import './css/OperatorsPage.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
);

const OPERATOR_PAGE_SIZE = 15;
const ROUTE_PAGE_SIZE = 25;

const formatNumber = value => Number(value || 0).toLocaleString('fr-FR');

const formatDistance = value => {
  const number = Number(value);
  return Number.isFinite(number) && number > 0
    ? `${number.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} km`
    : 'N/A';
};

const formatDuration = value => {
  const minutes = Number(value);
  if (!Number.isFinite(minutes) || minutes <= 0) return 'N/A';

  const hours = Math.floor(minutes / 60);
  const rest = Math.round(minutes % 60);
  return `${hours} h ${String(rest).padStart(2, '0')} min`;
};

export default function OperatorsPage() {
  const [operators, setOperators] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [operatorPage, setOperatorPage] = useState(1);

  const [selectedOperator, setSelectedOperator] = useState(null);
  const [operatorDetails, setOperatorDetails] = useState(null);
  const [timeline, setTimeline] = useState([]);

  const [routePage, setRoutePage] = useState(1);
  const [operatorTrains, setOperatorTrains] = useState([]);

  const [loadingDetails, setLoadingDetails] = useState(false);
  const [loadingRoutes, setLoadingRoutes] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getOperators(0, 500)
      .then(response => setOperators(response.data || []))
      .catch(err => {
        console.error(err);
        setError('Impossible de charger les opérateurs.');
      });
  }, []);

  const filteredOperators = useMemo(
    () => operators.filter(operator => (
      operator.operator_name
        ?.toLowerCase()
        .includes(searchTerm.toLowerCase())
    )),
    [operators, searchTerm],
  );

  useEffect(() => {
    setOperatorPage(1);
  }, [searchTerm]);

  const operatorStart = (operatorPage - 1) * OPERATOR_PAGE_SIZE;
  const visibleOperators = filteredOperators.slice(
    operatorStart,
    operatorStart + OPERATOR_PAGE_SIZE,
  );

  const loadRoutes = useCallback(async (operatorId, page) => {
    setLoadingRoutes(true);

    try {
      const response = await getTrainsByOperatorId(
        operatorId,
        (page - 1) * ROUTE_PAGE_SIZE,
        ROUTE_PAGE_SIZE,
      );
      setOperatorTrains(response.data || []);
    } catch (err) {
      console.error(err);
      setError("Impossible de charger les trajets de l'opérateur.");
    } finally {
      setLoadingRoutes(false);
    }
  }, []);

  const selectOperator = async operator => {
    setSelectedOperator(operator);
    setOperatorDetails(null);
    setTimeline([]);
    setOperatorTrains([]);
    setRoutePage(1);
    setLoadingDetails(true);
    setError(null);

    try {
      const [statsResponse, timelineResponse] = await Promise.all([
        getOperatorStats(operator.operator_id),
        getOperatorTimeline(operator.operator_id),
      ]);

      setOperatorDetails(statsResponse.data);
      setTimeline(timelineResponse.data || []);
      await loadRoutes(operator.operator_id, 1);
    } catch (err) {
      console.error(err);
      setError("Impossible de charger les détails de l'opérateur.");
    } finally {
      setLoadingDetails(false);
    }
  };

  const changeRoutePage = page => {
    if (!selectedOperator) return;
    setRoutePage(page);
    loadRoutes(selectedOperator.operator_id, page);
  };


  const timeline2010To2024 = useMemo(
    () => timeline.filter(item => (
      Number(item.year) >= 2010 && Number(item.year) <= 2024
    )),
    [timeline],
  );

  const timelineData = {
    labels: timeline2010To2024.map(item => item.year),
    datasets: [
      {
        label: 'Jour',
        data: timeline2010To2024.map(item => item.day_trains),
        borderColor: '#1769aa',
        backgroundColor: 'rgba(23, 105, 170, 0.12)',
        tension: 0.3,
      },
      {
        label: 'Nuit',
        data: timeline2010To2024.map(item => item.night_trains),
        borderColor: '#7e22ce',
        backgroundColor: 'rgba(126, 34, 206, 0.12)',
        tension: 0.3,
      },
    ],
  };

  const timelineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: { beginAtZero: true, title: { display: true, text: 'Nombre de trajets' } },
    },
  };

  const syntheticShare = operatorDetails?.total_trains
    ? (operatorDetails.synthetic_trains / operatorDetails.total_trains) * 100
    : 0;

  return (
    <div className="ob-operators-page">
      <header className="ob-operators-heading">
        <span>Analyse par opérateur</span>
        <h1>Opérateurs ferroviaires</h1>
        <p>
          Les listes volumineuses sont paginées. Les graphiques sont calculés
          depuis des agrégats serveur, sans génération aléatoire côté frontend.
        </p>
      </header>

      {error && <div className="ob-operators-alert">{error}</div>}

      <div className="ob-operators-layout">
        <aside className="ob-operators-panel">
          <div className="ob-operators-panel__header">
            <h2>Opérateurs</h2>
            <input
              type="search"
              placeholder="Rechercher..."
              value={searchTerm}
              onChange={event => setSearchTerm(event.target.value)}
            />
          </div>

          <div className="ob-operators-list">
            {visibleOperators.map(operator => (
              <button
                type="button"
                key={operator.operator_id}
                className={
                  selectedOperator?.operator_id === operator.operator_id
                    ? 'is-active'
                    : ''
                }
                onClick={() => selectOperator(operator)}
              >
                <span>{operator.operator_name}</span>
                <small>#{operator.operator_id}</small>
              </button>
            ))}
          </div>

          <PagePagination
            page={operatorPage}
            total={filteredOperators.length}
            pageSize={OPERATOR_PAGE_SIZE}
            onChange={setOperatorPage}
          />
        </aside>

        <main className="ob-operator-main">
          {!selectedOperator ? (
            <div className="ob-operator-placeholder">
              Sélectionne un opérateur pour afficher ses indicateurs.
            </div>
          ) : loadingDetails && !operatorDetails ? (
            <div className="ob-operator-placeholder">
              Chargement des indicateurs...
            </div>
          ) : operatorDetails ? (
            <>
              <section className="ob-operator-hero">
                <div>
                  <span>Opérateur</span>
                  <h2>{operatorDetails.operator_name}</h2>
                  <p>
                    {operatorDetails.countries_count} pays desservis :
                    {' '}
                    {operatorDetails.countries_served.join(', ')}
                  </p>
                </div>
                <div className="ob-operator-origin">
                  <strong>{syntheticShare.toFixed(1)} %</strong>
                  <span>de données synthétiques</span>
                </div>
              </section>

              <section className="ob-operator-kpis">
                <article>
                  <span>Total trajets</span>
                  <strong>{formatNumber(operatorDetails.total_trains)}</strong>
                </article>
                <article>
                  <span>Jour / nuit</span>
                  <strong>
                    {formatNumber(operatorDetails.day_trains)}
                    {' / '}
                    {formatNumber(operatorDetails.night_trains)}
                  </strong>
                </article>
                <article>
                  <span>Réel / synthétique</span>
                  <strong>
                    {formatNumber(operatorDetails.real_trains)}
                    {' / '}
                    {formatNumber(operatorDetails.synthetic_trains)}
                  </strong>
                </article>
                <article>
                  <span>Durée moyenne</span>
                  <strong>{formatDuration(operatorDetails.duree_moyenne_min)}</strong>
                </article>
              </section>

              <section className="ob-operator-card">
                <div className="ob-operator-card__heading">
                  <div>
                    <h3>Évolution annuelle</h3>
                    <p>Comptages réels du warehouse par année.</p>
                  </div>
                </div>
                <div className="ob-operator-chart">
                  {timeline2010To2024.length > 0 ? (
                    <Line data={timelineData} options={timelineOptions} />
                  ) : (
                    <div className="ob-operator-empty">
                      Pas de série temporelle disponible.
                    </div>
                  )}
                </div>
              </section>

              <section className="ob-operator-card">
                <div className="ob-operator-card__heading">
                  <div>
                    <h3>Indicateurs complémentaires</h3>
                    <p>
                      Le ratio CO₂ correspond à l'indicateur pays/activité
                      disponible, pas à une mesure directe de cet opérateur.
                    </p>
                  </div>
                </div>

                <div className="ob-operator-metrics">
                  <div>
                    <span>Distance totale</span>
                    <strong>{formatDistance(operatorDetails.distance_totale_km)}</strong>
                  </div>
                  <div>
                    <span>Ratio CO₂ / activité voyageurs</span>
                    <strong>
                      {operatorDetails.avg_co2_per_passenger != null
                        ? Number(operatorDetails.avg_co2_per_passenger).toFixed(4)
                        : 'N/A'}
                    </strong>
                  </div>
                </div>
              </section>

              <section className="ob-operator-card">
                <div className="ob-operator-card__heading">
                  <div>
                    <h3>Trajets</h3>
                    <p>{ROUTE_PAGE_SIZE} lignes maximum par requête.</p>
                  </div>
                </div>

                {loadingRoutes ? (
                  <div className="ob-operator-empty">Chargement...</div>
                ) : (
                  <div className="ob-operator-table-scroll">
                    <table className="ob-operator-table">
                      <thead>
                        <tr>
                          <th>Train</th>
                          <th>Pays</th>
                          <th>Type</th>
                          <th>Origine</th>
                          <th>Distance</th>
                          <th>Durée</th>
                          <th>Année</th>
                        </tr>
                      </thead>
                      <tbody>
                        {operatorTrains.map(train => (
                          <tr key={train.fact_id}>
                            <td>
                              <strong>{train.train}</strong>
                              <small>{train.route_id}</small>
                            </td>
                            <td>{train.country_code}</td>
                            <td>{train.is_night ? 'Nuit' : 'Jour'}</td>
                            <td>{train.is_synthetic ? 'Synthétique' : 'Réel'}</td>
                            <td>{formatDistance(train.distance_km)}</td>
                            <td>{formatDuration(train.duration_min)}</td>
                            <td>{train.year}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <PagePagination
                  page={routePage}
                  total={operatorDetails.total_trains}
                  pageSize={ROUTE_PAGE_SIZE}
                  onChange={changeRoutePage}
                  disabled={loadingRoutes}
                />
              </section>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
