import axios from 'axios';

const API_BASE_URL = (
  process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api'
).replace(/\/$/, '');

const API_ROOT_URL = API_BASE_URL.replace(/\/api$/, '');

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const rootApi = axios.create({
  baseURL: API_ROOT_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const cleanParams = (params = {}) => Object.fromEntries(
  Object.entries(params).filter(([, value]) => (
    value !== undefined
    && value !== null
    && value !== ''
    && value !== 'all'
  ))
);

// Dashboard / synthèses
export const getSummary = () => api.get('/night-trains/summary');
export const getTimeline = () => api.get('/statistics/timeline');
export const getDashboardKpis = () => api.get('/dashboard/kpis');

export const getCo2Ranking = (limit = null) => (
  api.get('/statistics/co2-ranking', {
    params: cleanParams({ limit }),
  })
);

export const getTrainTypeComparison = () => (
  api.get('/analysis/train-types-comparison')
);

export const getPolicyRecommendations = () => (
  api.get('/analysis/policy-recommendations')
);

// Trains
export const getTrainFacets = () => api.get('/night-trains/facets');

export const getStratifiedTrains = (
  slicePage = 1,
  samplePerCountry = 2,
  filters = {},
) => (
  api.get('/night-trains/stratified', {
    params: cleanParams({
      slice_page: slicePage,
      sample_per_country: samplePerCountry,
      ...filters,
    }),
  })
);

export const getNightTrains = (
  skip = 0,
  limit = 100,
  filters = {},
) => (
  api.get('/night-trains', {
    params: cleanParams({ skip, limit, ...filters }),
  })
);

export const getNightTrainsOnly = (
  skip = 0,
  limit = 100,
  filters = {},
) => (
  api.get('/night-trains/night', {
    params: cleanParams({ skip, limit, ...filters }),
  })
);

export const getDayTrainsOnly = (
  skip = 0,
  limit = 100,
  filters = {},
) => (
  api.get('/night-trains/day', {
    params: cleanParams({ skip, limit, ...filters }),
  })
);

export const getGeographicCoverage = () => (
  api.get('/geographic/coverage')
);

export const getAllTrains = getNightTrains;

export const getTrainsByCountry = (
  countryCode,
  skip = 0,
  limit = 100,
  filters = {},
) => (
  getNightTrains(skip, limit, {
    country_code: countryCode,
    ...filters,
  })
);

export const getTrainsByOperator = (
  operatorName,
  skip = 0,
  limit = 100,
  filters = {},
) => (
  getNightTrains(skip, limit, {
    operator_name: operatorName,
    ...filters,
  })
);

export const getTrainsByYear = (
  year,
  skip = 0,
  limit = 100,
  filters = {},
) => (
  getNightTrains(skip, limit, {
    year,
    ...filters,
  })
);

export const getTrainsByOperatorId = (
  operatorId,
  skip = 0,
  limit = 25,
  filters = {},
) => (
  api.get(`/night-trains/by-operator/${operatorId}`, {
    params: cleanParams({ skip, limit, ...filters }),
  })
);

// Pays
export const getCountries = (skip = 0, limit = 200) => (
  api.get('/countries', {
    params: cleanParams({ skip, limit }),
  })
);

export const getCountryStats = (
  filters = {},
  skip = 0,
  limit = 100,
) => (
  api.get('/countries/stats', {
    params: cleanParams({ skip, limit, ...filters }),
  })
);

// Opérateurs
export const getOperators = (skip = 0, limit = 500) => (
  api.get('/operators', {
    params: cleanParams({ skip, limit }),
  })
);

export const getOperatorStats = operatorId => (
  api.get(`/operators/${operatorId}/stats`)
);

export const getOperatorTimeline = operatorId => (
  api.get(`/operators/${operatorId}/timeline`)
);

export const getOperatorById = getOperatorStats;

// IA
export const getPredictionContext = () => (
  api.get('/predict/context')
);

export const predictClassification = payload => (
  api.post('/predict/classification', payload)
);

export const predictRegression = payload => (
  api.post('/predict/regression', payload)
);

// Health
export const getHealth = () => rootApi.get('/health');

export default api;
