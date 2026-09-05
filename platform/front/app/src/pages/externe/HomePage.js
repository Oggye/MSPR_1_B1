import { useEffect, useMemo, useState } from 'react';
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

import {
  getDashboardKpis,
  getGeographicCoverage,
  getSummary,
  getTimeline,
} from '../../services/api';

import './css/HomePage.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
);

const formatNumber = value => Number(value || 0).toLocaleString('fr-FR');

export default function ExterneHomePage() {
  const [summary, setSummary] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [kpis, setKpis] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getSummary(),
      getTimeline(),
      getDashboardKpis(),
      getGeographicCoverage(),
    ])
      .then(([
        summaryResponse,
        timelineResponse,
        kpiResponse,
        coverageResponse,
      ]) => {
        setSummary(summaryResponse.data);
        setTimeline(timelineResponse.data || []);
        setKpis(kpiResponse.data);
        setCoverage(coverageResponse.data);
      })
      .catch(err => {
        console.error(err);
        setError('Impossible de charger le dashboard.');
      });
  }, []);


  const timeline2010To2024 = useMemo(
    () => timeline.filter(item => (
      Number(item.year) >= 2010 && Number(item.year) <= 2024
    )),
    [timeline],
  );

  const synthesis = useMemo(() => {
    if (!summary || summary.total_trains <= 0) return null;

    return {
      nightShare: (
        summary.total_night_trains / summary.total_trains
      ) * 100,
      syntheticShare: (
        summary.total_synthetic_trains / summary.total_trains
      ) * 100,
    };
  }, [summary]);

  const activityChart = {
    labels: timeline2010To2024.map(item => item.year),
    datasets: [
      {
        label: 'Activité voyageurs (MIO_PKM)',
        data: timeline2010To2024.map(item => item.passengers),
        borderColor: '#1769aa',
        backgroundColor: 'rgba(23, 105, 170, 0.10)',
        yAxisID: 'y',
        tension: 0.3,
        spanGaps: true,
      },
      {
        label: 'CO₂ national (MIO_T)',
        data: timeline2010To2024.map(item => item.co2_emissions),
        borderColor: '#22c55e',
        backgroundColor: 'rgba(34, 197, 94, 0.10)',
        yAxisID: 'y1',
        tension: 0.3,
        spanGaps: true,
      },
    ],
  };

  const trainChart = {
    labels: timeline2010To2024.map(item => item.year),
    datasets: [
      {
        label: 'Trajets de jour',
        data: timeline2010To2024.map(item => item.day_trains_count),
        borderColor: '#1769aa',
        backgroundColor: 'rgba(23, 105, 170, 0.10)',
        tension: 0.3,
      },
      {
        label: 'Trajets de nuit',
        data: timeline2010To2024.map(item => item.night_trains_count),
        borderColor: '#7e22ce',
        backgroundColor: 'rgba(126, 34, 206, 0.10)',
        tension: 0.3,
      },
    ],
  };

  const activityOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        type: 'linear',
        position: 'left',
        title: { display: true, text: 'MIO_PKM' },
      },
      y1: {
        type: 'linear',
        position: 'right',
        grid: { drawOnChartArea: false },
        title: { display: true, text: 'MIO_T CO₂' },
      },
    },
  };

  const trainOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        beginAtZero: true,
        title: { display: true, text: 'Nombre de trajets' },
      },
    },
  };

  const latestYear = timeline2010To2024.length
    ? timeline2010To2024[timeline2010To2024.length - 1].year
    : null;

  return (
    <div className="ob-home-page">
      <header className="ob-home-heading">
        <span>ObRail Europe</span>
        <h1>Vue d'ensemble</h1>
        <p>
          Une lecture synthétique du warehouse : volumes, couverture,
          provenance des données et évolution temporelle.
        </p>
      </header>

      {error && <div className="ob-home-alert">{error}</div>}

      <section className="ob-home-kpis">
        <article>
          <span>Trajets</span>
          <strong>{formatNumber(summary?.total_trains)}</strong>
          <small>jour + nuit</small>
        </article>
        <article>
          <span>Pays couverts</span>
          <strong>{coverage?.total_countries_covered || 0}</strong>
          <small>avec au moins un trajet</small>
        </article>
        <article>
          <span>Opérateurs</span>
          <strong>{formatNumber(kpis?.total_operators)}</strong>
          <small>référencés</small>
        </article>
        <article>
          <span>Période</span>
          <strong>2010-2024</strong>
          <small>{latestYear ? `dernière année : ${latestYear}` : ''}</small>
        </article>
      </section>

      <section className="ob-home-summary-grid">
        <article className="ob-home-summary-card">
          <h2>Composition du réseau</h2>
          <div><span>Jour</span><strong>{formatNumber(summary?.total_day_trains)}</strong></div>
          <div><span>Nuit</span><strong>{formatNumber(summary?.total_night_trains)}</strong></div>
          <div>
            <span>Part nocturne</span>
            <strong>
              {synthesis ? `${synthesis.nightShare.toFixed(1)} %` : '0 %'}
            </strong>
          </div>
        </article>

        <article className="ob-home-summary-card">
          <h2>Origine des données</h2>
          <div><span>Réelles</span><strong>{formatNumber(summary?.total_real_trains)}</strong></div>
          <div><span>Synthétiques</span><strong>{formatNumber(summary?.total_synthetic_trains)}</strong></div>
          <div>
            <span>Part synthétique</span>
            <strong>
              {synthesis ? `${synthesis.syntheticShare.toFixed(1)} %` : '0 %'}
            </strong>
          </div>
        </article>

        <article className="ob-home-summary-card">
          <h2>Indicateurs statistiques</h2>
          <div>
            <span>Activité voyageurs cumulée</span>
            <strong>{formatNumber(kpis?.total_passengers)} MIO_PKM</strong>
          </div>
          <div>
            <span>CO₂ cumulé</span>
            <strong>{formatNumber(kpis?.total_co2_emissions)} MIO_T</strong>
          </div>
          <div>
            <span>Ratio CO₂ / activité</span>
            <strong>
              {kpis?.avg_co2_per_passenger != null
                ? Number(kpis.avg_co2_per_passenger).toFixed(4)
                : '—'}
            </strong>
          </div>
        </article>
      </section>

      <section className="ob-home-insight">
        <strong>Comment lire ces chiffres</strong>
        <p>
          Les trajets réels proviennent des sources GTFS et Back on Track.
          Les trajets synthétiques complètent les pays sans dataset détaillé.
          Les valeurs voyageurs sont exprimées en millions de passager-km
          (MIO_PKM), pas en nombre brut de personnes.
        </p>
      </section>

      <section className="ob-home-charts">
        <article className="ob-home-chart-card">
          <div>
            <h2>Évolution de l'activité et du CO₂</h2>
            <p>Deux axes séparés afin de ne pas mélanger des unités différentes.</p>
          </div>
          <div className="ob-home-chart">
            <Line data={activityChart} options={activityOptions} />
          </div>
        </article>

        <article className="ob-home-chart-card">
          <div>
            <h2>Évolution jour / nuit</h2>
            <p>Comptages réellement retournés par l'API.</p>
          </div>
          <div className="ob-home-chart">
            <Line data={trainChart} options={trainOptions} />
          </div>
        </article>
      </section>
    </div>
  );
}
