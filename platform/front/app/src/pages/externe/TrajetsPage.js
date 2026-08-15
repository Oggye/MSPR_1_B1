import React, { useCallback, useEffect, useMemo, useState } from 'react';

import {
  getGeographicCoverage,
  getStratifiedTrains,
  getTrainFacets,
} from '../../services/api';
import { SlicePagination } from '../../components/DataPagination';

import './css/TrajetsPage.css';

const formatNumber = value => Number(value || 0).toLocaleString('fr-FR');

const formatDistance = value => {
  const number = Number(value);
  return Number.isFinite(number) && number > 0
    ? `${number.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} km`
    : 'Non renseignée';
};

const formatDuration = value => {
  const minutes = Number(value);
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return 'Non renseignée';
  }

  const hours = Math.floor(minutes / 60);
  const remaining = Math.round(minutes % 60);

  return `${hours} h ${String(remaining).padStart(2, '0')} min`;
};

const normalizeFilters = filters => ({
  country_code: filters.country || undefined,
  operator_name: filters.operator || undefined,
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

export default function TrajetsPage() {
  const [coverage, setCoverage] = useState([]);
  const [facets, setFacets] = useState({ years: [], data_sources: [] });

  const [draftFilters, setDraftFilters] = useState({
    operator: '',
    country: '',
    trainType: 'all',
    origin: 'all',
    source: 'all',
    year: 'all',
  });
  const [filters, setFilters] = useState(draftFilters);

  const [slicePage, setSlicePage] = useState(1);
  const [sliceData, setSliceData] = useState(null);
  const [selectedRoute, setSelectedRoute] = useState(null);

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
        setError('Impossible de charger les filtres de référence.');
      });
  }, []);

  const loadSlice = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const apiFilters = normalizeFilters(filters);

      // Vue Europe : 1 exemple par pays garantit une lecture globale légère.
      // Vue pays : 30 exemples permettent une inspection plus détaillée.
      const samplePerCountry = filters.country ? 30 : 1;

      const response = await getStratifiedTrains(
        slicePage,
        samplePerCountry,
        apiFilters,
      );

      setSliceData(response.data);
      setSelectedRoute(current => {
        if (!current) return null;

        const stillVisible = (response.data?.items || []).find(
          item => item.fact_id === current.fact_id,
        );

        return stillVisible || null;
      });
    } catch (err) {
      console.error(err);
      setError(
        "Impossible de charger cette tranche. Vérifie que l'API est démarrée.",
      );
    } finally {
      setLoading(false);
    }
  }, [filters, slicePage]);

  useEffect(() => {
    loadSlice();
  }, [loadSlice]);

  const applyFilters = event => {
    event.preventDefault();
    setSlicePage(1);
    setSelectedRoute(null);
    setFilters(draftFilters);
  };

  const resetFilters = () => {
    const empty = {
      operator: '',
      country: '',
      trainType: 'all',
      origin: 'all',
      source: 'all',
      year: 'all',
    };

    setDraftFilters(empty);
    setFilters(empty);
    setSlicePage(1);
    setSelectedRoute(null);
  };

  const items = sliceData?.items || [];

  const insight = useMemo(() => {
    if (!sliceData || sliceData.slice_total <= 0) {
      return 'Aucune donnée ne correspond aux filtres sélectionnés.';
    }

    const nightShare = (
      sliceData.total_night_trains / sliceData.slice_total
    ) * 100;

    const realShare = (
      sliceData.total_real_trains / sliceData.slice_total
    ) * 100;

    return (
      `Cette tranche analyse ${formatNumber(sliceData.slice_total)} trajets `
      + `répartis sur ${sliceData.countries_covered} pays. `
      + `${nightShare.toFixed(1)} % sont nocturnes et `
      + `${realShare.toFixed(1)} % proviennent de données réelles.`
    );
  }, [sliceData]);

  return (
    <div className="ob-trajets-page">
      <header className="ob-page-heading">
        <div>
          <span className="ob-eyebrow">Exploration ferroviaire</span>
          <h1>Trajets européens</h1>
          <p>
            Analyse par tranches stables de 10 % de chaque pays.
            Les indicateurs utilisent toute la tranche ; la liste n'affiche
            qu'un aperçu représentatif pour rester rapide.
          </p>
        </div>
      </header>

      <form className="ob-filter-panel" onSubmit={applyFilters}>
        <div className="ob-filter-grid">
          <label>
            <span>Opérateur</span>
            <input
              type="search"
              placeholder="SNCF, DB, Renfe..."
              value={draftFilters.operator}
              onChange={event => setDraftFilters(current => ({
                ...current,
                operator: event.target.value,
              }))}
            />
          </label>

          <label>
            <span>Pays</span>
            <select
              value={draftFilters.country}
              onChange={event => setDraftFilters(current => ({
                ...current,
                country: event.target.value,
              }))}
            >
              <option value="">Tous les pays couverts</option>
              {coverage.map(country => (
                <option
                  key={country.country_code}
                  value={country.country_code}
                >
                  {country.country_name} ({country.country_code})
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Type</span>
            <select
              value={draftFilters.trainType}
              onChange={event => setDraftFilters(current => ({
                ...current,
                trainType: event.target.value,
              }))}
            >
              <option value="all">Jour + nuit</option>
              <option value="day">Jour</option>
              <option value="night">Nuit</option>
            </select>
          </label>

          <label>
            <span>Origine des données</span>
            <select
              value={draftFilters.origin}
              onChange={event => setDraftFilters(current => ({
                ...current,
                origin: event.target.value,
              }))}
            >
              <option value="all">Réelles + synthétiques</option>
              <option value="real">Réelles uniquement</option>
              <option value="synthetic">Synthétiques uniquement</option>
            </select>
          </label>

          <label>
            <span>Source</span>
            <select
              value={draftFilters.source}
              onChange={event => setDraftFilters(current => ({
                ...current,
                source: event.target.value,
              }))}
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
              value={draftFilters.year}
              onChange={event => setDraftFilters(current => ({
                ...current,
                year: event.target.value,
              }))}
            >
              <option value="all">Toutes les années</option>
              {(facets.years || []).map(year => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="ob-filter-actions">
          <button className="ob-primary-button" type="submit">
            Appliquer
          </button>
          <button
            className="ob-secondary-button"
            type="button"
            onClick={resetFilters}
          >
            Réinitialiser
          </button>
        </div>
      </form>

      <SlicePagination
        value={slicePage}
        pageCount={sliceData?.page_count || 10}
        onChange={page => {
          setSlicePage(page);
          setSelectedRoute(null);
        }}
        disabled={loading}
      />

      {error && <div className="ob-alert ob-alert--error">{error}</div>}

      {sliceData && (
        <>
          <section className="ob-kpi-grid">
            <article className="ob-kpi-card">
              <span>Trajets analysés</span>
              <strong>{formatNumber(sliceData.slice_total)}</strong>
              <small>
                {sliceData.actual_slice_percent.toFixed(2)} % du jeu filtré
              </small>
            </article>

            <article className="ob-kpi-card">
              <span>Pays représentés</span>
              <strong>{sliceData.countries_covered}</strong>
              <small>sur {sliceData.countries_filtered} pays filtrés</small>
            </article>

            <article className="ob-kpi-card">
              <span>Jour / nuit</span>
              <strong>
                {formatNumber(sliceData.total_day_trains)}
                {' / '}
                {formatNumber(sliceData.total_night_trains)}
              </strong>
              <small>jour / nuit</small>
            </article>

            <article className="ob-kpi-card">
              <span>Réel / synthétique</span>
              <strong>
                {formatNumber(sliceData.total_real_trains)}
                {' / '}
                {formatNumber(sliceData.total_synthetic_trains)}
              </strong>
              <small>données observées / complétées</small>
            </article>
          </section>

          <div className="ob-insight">
            <strong>Synthèse de la tranche</strong>
            <p>{insight}</p>
            <small>
              {sliceData.items_returned} trajets représentatifs affichés ;
              les KPI portent sur les {formatNumber(sliceData.slice_total)} lignes
              de la tranche.
            </small>
          </div>
        </>
      )}

      <section className="ob-trajets-layout">
        <div className="ob-panel">
          <div className="ob-panel-heading">
            <div>
              <h2>Aperçu des trajets</h2>
              <p>
                {filters.country
                  ? 'Aperçu diversifié du pays sélectionné.'
                  : 'Un trajet représentatif par pays pour une lecture globale.'}
              </p>
            </div>
            <span className="ob-count-chip">{items.length} affichés</span>
          </div>

          {loading ? (
            <div className="ob-loading-state">Chargement de la tranche...</div>
          ) : items.length === 0 ? (
            <div className="ob-empty-state">Aucun trajet pour ces filtres.</div>
          ) : (
            <div className="ob-table-scroll">
              <table className="ob-data-table">
                <thead>
                  <tr>
                    <th>Train</th>
                    <th>Pays</th>
                    <th>Opérateur</th>
                    <th>Type</th>
                    <th>Origine</th>
                    <th>Distance</th>
                    <th>Durée</th>
                    <th>Année</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(train => (
                    <tr
                      key={train.fact_id}
                      className={
                        selectedRoute?.fact_id === train.fact_id
                          ? 'is-selected'
                          : ''
                      }
                      onClick={() => setSelectedRoute(train)}
                    >
                      <td>
                        <strong>{train.train}</strong>
                        <small className="ob-cell-subtitle">
                          {train.route_id}
                        </small>
                      </td>
                      <td>{train.country_name}</td>
                      <td>{train.operator_name}</td>
                      <td>
                        <span className={
                          `ob-tag ${train.is_night ? 'ob-tag--night' : 'ob-tag--day'}`
                        }>
                          {train.is_night ? 'Nuit' : 'Jour'}
                        </span>
                      </td>
                      <td>
                        <span className={
                          `ob-tag ${
                            train.is_synthetic
                              ? 'ob-tag--synthetic'
                              : 'ob-tag--real'
                          }`
                        }>
                          {train.is_synthetic ? 'Synthétique' : 'Réel'}
                        </span>
                      </td>
                      <td>{formatDistance(train.distance_km)}</td>
                      <td>{formatDuration(train.duration_min)}</td>
                      <td>{train.year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <aside className="ob-panel ob-route-detail">
          <div className="ob-panel-heading">
            <div>
              <h2>Détail</h2>
              <p>Données réellement disponibles dans le warehouse.</p>
            </div>
          </div>

          {selectedRoute ? (
            <dl className="ob-detail-list">
              <div><dt>Train</dt><dd>{selectedRoute.train}</dd></div>
              <div><dt>Route ID</dt><dd>{selectedRoute.route_id}</dd></div>
              <div><dt>Opérateur</dt><dd>{selectedRoute.operator_name}</dd></div>
              <div>
                <dt>Pays</dt>
                <dd>
                  {selectedRoute.country_name} ({selectedRoute.country_code})
                </dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{selectedRoute.is_night ? 'Train de nuit' : 'Train de jour'}</dd>
              </div>
              <div><dt>Distance</dt><dd>{formatDistance(selectedRoute.distance_km)}</dd></div>
              <div><dt>Durée</dt><dd>{formatDuration(selectedRoute.duration_min)}</dd></div>
              <div><dt>Année</dt><dd>{selectedRoute.year}</dd></div>
              <div><dt>Source</dt><dd>{selectedRoute.data_source}</dd></div>
              <div>
                <dt>Origine</dt>
                <dd>
                  {selectedRoute.is_synthetic
                    ? 'Donnée synthétique de complétion'
                    : 'Donnée issue d’une source observée'}
                </dd>
              </div>
            </dl>
          ) : (
            <div className="ob-empty-state">
              Sélectionne un trajet du tableau pour afficher ses détails.
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}
