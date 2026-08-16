import {
  getInternalOverview,
  runInternalDiagnostic,
  runInternalTests,
} from './api_interne';

beforeEach(() => {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    })
  );
});

afterEach(() => {
  jest.restoreAllMocks();
});

test('loads the internal overview', async () => {
  await getInternalOverview();

  expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/internal/overview', {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  });
});

test('starts the diagnostic with POST', async () => {
  await runInternalDiagnostic();

  expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/internal/diagnostic/run', {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
});

test('starts backend tests with POST', async () => {
  await runInternalTests();

  expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/internal/tests/run', {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  });
});

test('throws a readable error on API failure', async () => {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: false,
      status: 503,
    })
  );

  await expect(getInternalOverview()).rejects.toThrow('Erreur API 503 sur /api/internal/overview');
});
