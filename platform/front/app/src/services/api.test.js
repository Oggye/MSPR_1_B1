// fichier : platform/front/app/src/services/api.test.js

const mockGet = jest.fn();
const mockClientConfigs = [];

jest.mock('axios', () => ({
  create: jest.fn((config) => {
    mockClientConfigs.push(config);
    return {
      get: (...args) => mockGet(...args),
    };
  }),
}));

const {
  getAllTrains,
  getCo2Ranking,
  getCountries,
  getHealth,
  getNightTrainsOnly,
  getOperatorById,
  getOperators,
} = require('./api');

beforeEach(() => {
  mockGet.mockClear();
});

test('calls health endpoint', () => {
  getHealth();

  expect(mockGet).toHaveBeenCalledWith('/health');
});

test('configures API clients to send authentication cookies', () => {
  expect(mockClientConfigs).toEqual(expect.arrayContaining([
    expect.objectContaining({ withCredentials: true }),
  ]));
});

test('passes pagination and filters for all trains', () => {
  getAllTrains(10, 25, { country_code: 'FR', year: 2024 });

  expect(mockGet).toHaveBeenCalledWith('/night-trains', {
    params: { skip: 10, limit: 25, country_code: 'FR', year: 2024 },
  });
});

test('passes filters for night trains only', () => {
  getNightTrainsOnly(0, 100, { operator_name: 'SNCF' });

  expect(mockGet).toHaveBeenCalledWith('/night-trains/night', {
    params: { skip: 0, limit: 100, operator_name: 'SNCF' },
  });
});

test('does not limit CO2 ranking by default', () => {
  getCo2Ranking();

  expect(mockGet).toHaveBeenCalledWith('/statistics/co2-ranking', {
    params: {},
  });
});

test('calls countries and operator stats endpoints', () => {
  getCountries();
  getOperatorById(3);

  expect(mockGet).toHaveBeenCalledWith('/countries', {
    params: { skip: 0, limit: 200 },
  });
  expect(mockGet).toHaveBeenCalledWith('/operators/3/stats');
});

test('does not limit operators by default', () => {
  getOperators();

  expect(mockGet).toHaveBeenCalledWith('/operators', {
    params: { skip: 0, limit: 500 },
  });
});
