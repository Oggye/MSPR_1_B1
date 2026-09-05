import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
} from 'react-leaflet';
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

import {
  getGeographicCoverage,
  getStratifiedTrains,
  getTrainFacets,
} from '../../services/api';
import {
  PagePagination,
  SlicePagination,
} from '../../components/DataPagination';

import 'leaflet/dist/leaflet.css';
import './css/MapPage.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
);

const COUNTRY_COORDS = {
  AT: [47.5162, 14.5501], BE: [50.5039, 4.4699],
  BG: [42.7339, 25.4858], HR: [45.1, 15.2],
  CY: [35.1264, 33.4299], CZ: [49.8175, 15.473],
  DK: [56.2639, 9.5018], EE: [58.5953, 25.0136],
  FI: [61.9241, 25.7482], FR: [46.6034, 1.8883],
  DE: [51.1657, 10.4515], GR: [39.0742, 21.8243],
  HU: [47.1625, 19.5033], IE: [53.1424, -7.6921],
  IT: [41.8719, 12.5674], LV: [56.8796, 24.6032],
  LT: [55.1694, 23.8813], LU: [49.8153, 6.1296],
  MT: [35.9375, 14.3754], NL: [52.1326, 5.2913],
  PL: [51.9194, 19.1451], PT: [39.3999, -8.2245],
  RO: [45.9432, 24.9668], SK: [48.669, 19.699],
  SI: [46.1512, 14.9955], ES: [40.4637, -3.7492],
  SE: [60.1282, 18.6435], CH: [46.8182, 8.2275],
  GB: [55.3781, -3.436], UK: [55.3781, -3.436],
  NO: [60.472, 8.4689], UA: [48.3794, 31.1656],
};

const formatNumber = value => Number(value || 0).toLocaleString('fr-FR');

const normalizeFilters = filters => ({
  country_code: filters.country || undefined,
  year: filters.year === 'all' ? undefined : Number(filters.year),
  is_night: (
    filters.trainType === 'night'
      ? true
      : filters.trainType === 'day'
        ? false
        : undefined
  ),
  is_synthetic: (
    filters.origin === 'real'
      ? false
      : filters.origin === 'synthetic'
        ? true
        : undefined
  ),
  data_source: filters.source === 'all' ? undefined : filters.source,
});

const circleRadius = (count, max) => {
  if (!count || !max) return 6;
  return 7 + (Math.sqrt(count / max) * 21);
};

export default function MapPage() {
  const [coverage, setCoverage] = useState([]);
  const [facets, setFacets] = useState({ years: [], data_sources: [] });

  const [filters, setFilters] = useState({
    trainType: 'all',
    country: '',
    origin: 'all',
    source: 'all',
    year: 'all',
  });

  const [slicePage, setSlicePage] = useState(1);
  const [sliceData, setSliceData] = useState(null);

  const [countryTablePage, setCountryTablePage] = useState(1);
  const countriesPerPage = 10;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getGeographicCoverage(),
      getTrainFacets(),
    ])
      .then(([coverageResponse, facetsResponse]) => {
        setCoverage(coverageResponse.data?.coverage_by_country || []);
        setFacets(facetsResponse.data || { years: [], data_sources: [] });
      })
      .catch(err => {
        console.error(err);
        setError('Impossible de charger les filtres de la carte.');
      });
  }, []);

  const loadSlice = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await getStratifiedTrains(
        slicePage,
        0,
        normalizeFilters(filters),
      );
      setSliceData(response.data);
      setCountryTablePage(1);
    } catch (err) {
      console.error(err);
      setError('Impossible de charger la synthèse cartographique.');
    } finally {
      setLoading(false);
    }
  }, [filters, slicePage]);

  useEffect(() => {
    loadSlice();
  }, [loadSlice]);

  const visibleCountries = useMemo(
    () => (sliceData?.by_country || []).filter(
      country => country.slice_trains > 0,
    ),
    [sliceData],
  );

  const maxCountryCount = useMemo(
    () => Math.max(
      ...visibleCountries.map(country => country.slice_trains),
      1,
    ),
    [visibleCountries],
  );

  const chartData = useMemo(() => {
    const ordered = [...visibleCountries].sort(
      (a, b) => b.slice_trains - a.slice_trains,
    );

    return {
      labels: ordered.map(country => country.country_code),
      datasets: [
        {
          label: 'Données réelles',
          data: ordered.map(country => country.real_trains),
          backgroundColor: '#1769aa',
          borderRadius: 4,
        },
        {
          label: 'Données synthétiques',
          data: ordered.map(country => country.synthetic_trains),
          backgroundColor: '#f59e0b',
          borderRadius: 4,
        },
      ],
    };
  }, [visibleCountries]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    scales: {
      x: {
        stacked: true,
        beginAtZero: true,
        title: { display: true, text: 'Nombre de trajets dans la tranche' },
      },
      y: { stacked: true },
    },
    plugins: { legend: { position: 'top' } },
  };

  const summary = useMemo(() => {
    if (!sliceData || sliceData.slice_total <= 0) return null;

    return {
      nightShare: (
        sliceData.total_night_trains / sliceData.slice_total
      ) * 100,
      realShare: (
        sliceData.total_real_trains / sliceData.slice_total
      ) * 100,
    };
  }, [sliceData]);

  const tableStart = (countryTablePage - 1) * countriesPerPage;
  const tableCountries = visibleCountries.slice(
    tableStart,
    tableStart + countriesPerPage,
  );

  const updateFilter = (name, value) => {
    setSlicePage(1);
    setFilters(current => ({ ...current, [name]: value }));
  };

  return (
    <div className="ob-map-page">
      <header className="ob-map-heading">
        <div>
          <span className="ob-map-eyebrow">Couverture européenne</span>
          <h1>Carte de synthèse ferroviaire</h1>
          <p>
            La carte présente un agrégat national. Les bulles sont placées au
            centre des pays : elles représentent un volume de données, pas la
            position d'une gare ou d'un train précis.
          </p>
        </div>
      </header>

      <section className="ob-map-filters">
        <label>
          <span>Type</span>
          <select
            value={filters.trainType}
            onChange={event => updateFilter('trainType', event.target.value)}
          >
            <option value="all">Jour + nuit</option>
            <option value="day">Jour</option>
            <option value="night">Nuit</option>
          </select>
        </label>

        <label>
          <span>Pays</span>
          <select
            value={filters.country}
            onChange={event => updateFilter('country', event.target.value)}
          >
            <option value="">Tous les pays couverts</option>
            {coverage.map(country => (
              <option key={country.country_code} value={country.country_code}>
                {country.country_name}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Origine</span>
          <select
            value={filters.origin}
            onChange={event => updateFilter('origin', event.target.value)}
          >
            <option value="all">Réel + synthétique</option>
            <option value="real">Réel uniquement</option>
            <option value="synthetic">Synthétique uniquement</option>
          </select>
        </label>

        <label>
          <span>Source</span>
          <select
            value={filters.source}
            onChange={event => updateFilter('source', event.target.value)}
          >
            <option value="all">Toutes les sources</option>
            {(facets.data_sources || []).map(source => (
              <option key={source} value={source}>{source}</option>
            ))}
          </select>
        </label>

        <label>
          <span>Année</span>
          <select
            value={filters.year}
            onChange={event => updateFilter('year', event.target.value)}
          >
            <option value="all">Toutes les années</option>
            {(facets.years || []).map(year => (
              <option key={year} value={year}>{year}</option>
            ))}
          </select>
        </label>
      </section>

      <SlicePagination
        value={slicePage}
        pageCount={sliceData?.page_count || 10}
        onChange={setSlicePage}
        disabled={loading}
      />

      {error && <div className="ob-map-alert">{error}</div>}

      {sliceData && (
        <section className="ob-map-kpis">
          <article>
            <span>Trajets analysés</span>
            <strong>{formatNumber(sliceData.slice_total)}</strong>
            <small>
              {sliceData.actual_slice_percent.toFixed(2)} % du jeu filtré
            </small>
          </article>
          <article>
            <span>Pays représentés</span>
            <strong>{sliceData.countries_covered}</strong>
            <small>couverture de la tranche</small>
          </article>
          <article>
            <span>Part de nuit</span>
            <strong>{summary ? `${summary.nightShare.toFixed(1)} %` : '0 %'}</strong>
            <small>sur les trajets de la tranche</small>
          </article>
          <article>
            <span>Part réelle</span>
            <strong>{summary ? `${summary.realShare.toFixed(1)} %` : '0 %'}</strong>
            <small>hors données synthétiques</small>
          </article>
        </section>
      )}

      <section className="ob-map-layout">
        <div className="ob-map-card">
          <div className="ob-map-card__heading">
            <div>
              <h2>Répartition géographique</h2>
              <p>Taille de la bulle = volume de trajets dans la tranche.</p>
            </div>
          </div>

          <div className="ob-map-canvas">
            <MapContainer
              center={[51.0, 10.0]}
              zoom={4}
              minZoom={3}
              style={{ height: '560px', width: '100%' }}
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; OpenStreetMap &copy; CARTO'
              />

              {visibleCountries.map(country => {
                const coords = COUNTRY_COORDS[country.country_code];
                if (!coords) return null;

                const syntheticShare = country.slice_trains > 0
                  ? country.synthetic_trains / country.slice_trains
                  : 0;

                return (
                  <CircleMarker
                    key={country.country_code}
                    center={coords}
                    radius={circleRadius(
                      country.slice_trains,
                      maxCountryCount,
                    )}
                    pathOptions={{
                      color: syntheticShare > 0.5 ? '#b45309' : '#1769aa',
                      fillColor: syntheticShare > 0.5 ? '#f59e0b' : '#3b82f6',
                      fillOpacity: 0.58,
                      weight: 2,
                    }}
                  >
                    <Popup>
                      <div className="ob-map-popup">
                        <h3>
                          {country.country_name} ({country.country_code})
                        </h3>
                        <p>
                          <strong>Tranche :</strong>{' '}
                          {formatNumber(country.slice_trains)} trajets
                          {' '}({country.slice_percent.toFixed(2)} % du pays)
                        </p>
                        <p>
                          <strong>Jour / nuit :</strong>{' '}
                          {formatNumber(country.day_trains)}
                          {' / '}
                          {formatNumber(country.night_trains)}
                        </p>
                        <p>
                          <strong>Réel / synthétique :</strong>{' '}
                          {formatNumber(country.real_trains)}
                          {' / '}
                          {formatNumber(country.synthetic_trains)}
                        </p>
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>
        </div>

        <div className="ob-map-card">
          <div className="ob-map-card__heading">
            <div>
              <h2>Qualité de couverture</h2>
              <p>Réel et synthétique par pays dans la tranche.</p>
            </div>
          </div>
          <div className="ob-map-chart">
            <Bar data={chartData} options={chartOptions} />
          </div>
        </div>
      </section>

      <section className="ob-map-card ob-map-country-table-card">
        <div className="ob-map-card__heading">
          <div>
            <h2>Synthèse par pays</h2>
            <p>
              Les pourcentages permettent de vérifier que chaque tranche
              reste proche de 10 % des données de chaque pays.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="ob-map-loading">Chargement...</div>
        ) : (
          <>
            <div className="ob-map-table-scroll">
              <table className="ob-map-table">
                <thead>
                  <tr>
                    <th>Pays</th>
                    <th>Total filtré</th>
                    <th>Tranche</th>
                    <th>% du pays</th>
                    <th>Jour</th>
                    <th>Nuit</th>
                    <th>Réel</th>
                    <th>Synthétique</th>
                  </tr>
                </thead>
                <tbody>
                  {tableCountries.map(country => (
                    <tr key={country.country_code}>
                      <td>
                        <strong>{country.country_name}</strong>
                        <small>{country.country_code}</small>
                      </td>
                      <td>{formatNumber(country.total_filtered)}</td>
                      <td>{formatNumber(country.slice_trains)}</td>
                      <td>{country.slice_percent.toFixed(2)} %</td>
                      <td>{formatNumber(country.day_trains)}</td>
                      <td>{formatNumber(country.night_trains)}</td>
                      <td>{formatNumber(country.real_trains)}</td>
                      <td>{formatNumber(country.synthetic_trains)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PagePagination
              page={countryTablePage}
              total={visibleCountries.length}
              pageSize={countriesPerPage}
              onChange={setCountryTablePage}
            />
          </>
        )}
      </section>
    </div>
  );
}
