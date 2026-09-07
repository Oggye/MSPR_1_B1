import React, { useEffect, useMemo, useState } from 'react';
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';

import {
  getCo2Ranking,
  getPolicyRecommendations,
  getSummary,
  getTimeline,
  getTrainTypeComparison,
} from '../../services/api';
import { PagePagination } from '../../components/DataPagination';

import './css/StatisticsPage.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
);

const RANKING_PAGE_SIZE = 10;
const formatNumber = value => Number(value || 0).toLocaleString('fr-FR');

export default function StatisticsPage() {
  const [summary, setSummary] = useState(null);
  const [trainTypeData, setTrainTypeData] = useState([]);
  const [timelineData, setTimelineData] = useState([]);
  const [co2Ranking, setCo2Ranking] = useState([]);
  const [policyRecommendations, setPolicyRecommendations] = useState(null);
  const [rankingPage, setRankingPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);

    Promise.all([
      getSummary(),
      getTrainTypeComparison(),
      getTimeline(),
      getCo2Ranking(),
      getPolicyRecommendations(),
    ])
      .then(([
        summaryResponse,
        trainTypeResponse,
        timelineResponse,
        rankingResponse,
        policyResponse,
      ]) => {
        setSummary(summaryResponse.data);
        setTrainTypeData(trainTypeResponse.data || []);
        setTimelineData(timelineResponse.data || []);
        setCo2Ranking(rankingResponse.data || []);
        setPolicyRecommendations(policyResponse.data);
      })
      .catch(err => {
        console.error(err);
        setError('Impossible de charger les données statistiques.');
      })
      .finally(() => setLoading(false));
  }, []);


  const timeline2010To2024 = useMemo(
    () => timelineData.filter(item => (
      Number(item.year) >= 2010 && Number(item.year) <= 2024
    )),
    [timelineData],
  );

  const trainEvolutionData = {
    labels: timeline2010To2024.map(item => item.year),
    datasets: [
      {
        label: 'Jour',
        data: timeline2010To2024.map(item => item.day_trains_count),
        borderColor: '#1769aa',
        backgroundColor: 'rgba(23, 105, 170, 0.12)',
        tension: 0.3,
      },
      {
        label: 'Nuit',
        data: timeline2010To2024.map(item => item.night_trains_count),
        borderColor: '#7e22ce',
        backgroundColor: 'rgba(126, 34, 206, 0.12)',
        tension: 0.3,
      },
    ],
  };

  const comparisonData = {
    labels: trainTypeData.map(item => (
      item.train_type === 'night' ? 'Nuit' : 'Jour'
    )),
    datasets: [
      {
        label: 'Distance moyenne (km)',
        data: trainTypeData.map(item => item.avg_distance),
        backgroundColor: '#1769aa',
        borderRadius: 6,
      },
    ],
  };

  const standardChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: { y: { beginAtZero: true } },
  };

  const rankingStart = (rankingPage - 1) * RANKING_PAGE_SIZE;
  const visibleRanking = co2Ranking.slice(
    rankingStart,
    rankingStart + RANKING_PAGE_SIZE,
  );

  const synthesis = useMemo(() => {
    if (!summary || summary.total_trains <= 0) return null;

    return {
      nightShare: (
        summary.total_night_trains / summary.total_trains
      ) * 100,
      realShare: (
        summary.total_real_trains / summary.total_trains
      ) * 100,
    };
  }, [summary]);

  const latestTimeline = timeline2010To2024[timeline2010To2024.length - 1];

  if (loading) {
    return <div className="ob-statistics-state">Chargement des synthèses...</div>;
  }

  if (error) {
    return <div className="ob-statistics-state is-error">{error}</div>;
  }

  return (
    <div className="ob-statistics-page">
      <header className="ob-statistics-heading">
        <span>Lecture globale</span>
        <h1>Tableau de bord statistique</h1>
        <p>
          Les graphiques utilisent les agrégats de l'API. Aucune série de jour
          ou d'opérateur n'est simulée dans le navigateur.
        </p>
      </header>

      {summary && (
        <section className="ob-statistics-kpis">
          <article>
            <span>Total trajets</span>
            <strong>{formatNumber(summary.total_trains)}</strong>
          </article>
          <article>
            <span>Part nocturne</span>
            <strong>
              {synthesis ? `${synthesis.nightShare.toFixed(1)} %` : '0 %'}
            </strong>
          </article>
          <article>
            <span>Données réelles</span>
            <strong>{formatNumber(summary.total_real_trains)}</strong>
          </article>
          <article>
            <span>Part réelle</span>
            <strong>
              {synthesis ? `${synthesis.realShare.toFixed(1)} %` : '0 %'}
            </strong>
          </article>
        </section>
      )}

      <section className="ob-statistics-insight">
        <strong>Synthèse</strong>
        <p>
          {latestTimeline
            ? (
              `La période va jusqu'à ${latestTimeline.year}. `
              + `Sur l'ensemble du warehouse, `
              + `${formatNumber(summary?.total_day_trains)} trajets sont de jour `
              + `et ${formatNumber(summary?.total_night_trains)} de nuit.`
            )
            : 'Aucune série temporelle disponible.'}
        </p>
        <small>
          La métrique voyageurs est MIO_PKM (millions de passager-km).
          Le champ CO₂/passager du warehouse est présenté comme un ratio
          CO₂ / activité voyageurs, pas comme l'émission directe d'un train.
        </small>
      </section>

      <section className="ob-statistics-grid">
        <article className="ob-statistics-card">
          <div className="ob-statistics-card__heading">
            <h2>Couverture des trajets par année</h2>
            <p>
              Le pic de 2024 reflète surtout une meilleure disponibilité des
              données GTFS détaillées pour cette année, et non une
              multiplication réelle du trafic ferroviaire.
            </p>
          </div>
          <div className="ob-statistics-chart">
            <Line data={trainEvolutionData} options={standardChartOptions} />
          </div>
        </article>

        <article className="ob-statistics-card">
          <div className="ob-statistics-card__heading">
            <h2>Distance moyenne</h2>
            <p>Comparaison des trajets de jour et de nuit.</p>
          </div>
          <div className="ob-statistics-chart">
            <Bar data={comparisonData} options={standardChartOptions} />
          </div>
        </article>

        <article className="ob-statistics-card">
          <div className="ob-statistics-card__heading">
            <h2>Ratio CO₂ / activité associé aux pays/années</h2>
            <p>
              Valeur moyenne associée aux statistiques pays/année ; ce n'est
              pas l'émission directe d'un train.
            </p>
          </div>
          <div className="ob-statistics-comparison-list">
            {trainTypeData.map(item => (
              <div key={item.train_type}>
                <span>{item.train_type === 'night' ? 'Nuit' : 'Jour'}</span>
                <strong>
                  {Number(item.avg_co2_per_passenger || 0).toFixed(4)}
                </strong>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="ob-statistics-card ob-statistics-ranking">
        <div className="ob-statistics-card__heading">
          <h2>Classement du ratio CO₂ / activité voyageurs</h2>
          <p>
            Plus la valeur est basse, plus le ratio est faible selon la
            méthodologie actuelle.
          </p>
        </div>

        <div className="ob-statistics-table-scroll">
          <table className="ob-statistics-table">
            <thead>
              <tr>
                <th>Rang</th>
                <th>Pays</th>
                <th>Ratio</th>
                <th>Catégorie API</th>
              </tr>
            </thead>
            <tbody>
              {visibleRanking.map(country => (
                <tr key={country.country_code}>
                  <td>#{country.ranking}</td>
                  <td>
                    <strong>{country.country_name}</strong>
                    <small>{country.country_code}</small>
                  </td>
                  <td>{Number(country.avg_co2_per_passenger).toFixed(4)}</td>
                  <td>{country.performance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <PagePagination
          page={rankingPage}
          total={co2Ranking.length}
          pageSize={RANKING_PAGE_SIZE}
          onChange={setRankingPage}
        />
      </section>

      <section className="ob-statistics-card ob-statistics-ranking">
        <div className="ob-statistics-card__heading">
          <h2>Recommandations issues des agrégats</h2>
          <p>
            À lire comme des pistes d'analyse, pas comme des causalités
            démontrées.
          </p>
        </div>

        <div className="ob-statistics-policies">
          {(policyRecommendations?.recommendations || []).map(
            (recommendation, index) => (
              <article key={`${recommendation.title}-${index}`}>
                <h3>{recommendation.title}</h3>
                <p>{recommendation.description}</p>
                <strong>{recommendation.suggestion}</strong>
              </article>
            ),
          )}

          {!(policyRecommendations?.recommendations || []).length && (
            <div className="ob-statistics-empty">
              Aucune recommandation disponible.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
