const { test, expect } = require('@playwright/test');
const { createAuthenticatedSession } = require('./auth');

const API_BASE_URL =
  process.env.E2E_API_URL || 'http://localhost:8000';

/**
 * Effectue une requête avec retry automatique, sans afficher le contenu des réponses.
 */
async function fetchWithRetry(request, url, options = {}) {
  const {
    method = 'GET',
    retries = 3,
    delay = 1500,
  } = options;

  let lastResponse = null;
  let lastBody = null;

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response =
        method === 'POST'
          ? await request.post(url)
          : await request.get(url);

      const rawBody = await response.text();

      // On ne logge plus le corps de la réponse pour éviter la pollution
      if (attempt > 1 || response.status() !== 200) {
        console.log(`[${method}] ${url} -> status ${response.status()} (attempt ${attempt}/${retries})`);
      }

      lastResponse = response;
      lastBody = rawBody;

      if (response.status() === 200) {
        return {
          response,
          rawBody,
        };
      }

      if (attempt < retries) {
        console.log(`Retry dans ${delay}ms (status=${response.status()})`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    } catch (error) {
      console.error(`Erreur réseau tentative ${attempt}:`, error.message);
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  throw new Error(
    [
      `Erreur API après ${retries} tentatives`,
      `URL: ${url}`,
      `STATUS: ${lastResponse?.status?.()}`,
    ].join('\n')
  );
}

test.describe(
  'Endpoints internes FastAPI utilisés par le front admin',
  () => {
    test.describe.configure({
      mode: 'serial',
    });

    test.beforeEach(async ({ request }) => {
      await createAuthenticatedSession(request, 'admin');
    });

    test(
      'GET /api/internal/overview répond et expose les blocs attendus',
      async ({ request }) => {
        test.setTimeout(120000);

        const { rawBody } = await fetchWithRetry(
          request,
          `${API_BASE_URL}/api/internal/overview`,
          {
            method: 'GET',
            retries: 5,
            delay: 2000,
          }
        );

        let body;

        try {
          body = JSON.parse(rawBody);
        } catch (error) {
          console.error('JSON invalide:', rawBody);
          throw new Error(
            `Impossible de parser le JSON:\n${rawBody}`
          );
        }

        // On ne logge plus le JSON formaté
        // Vérification structure globale
        expect(body).toBeTruthy();

        // Vérification des blocs principaux
        expect(body).toHaveProperty('metrics');
        expect(body).toHaveProperty('prometheus');
        expect(body).toHaveProperty('grafana');
        expect(body).toHaveProperty('docker');
        expect(body).toHaveProperty('reports');

        // Vérifications supplémentaires robustes
        expect(body.metrics).toBeDefined();
        expect(body.prometheus).toBeDefined();
        expect(body.grafana).toBeDefined();
        expect(body.docker).toBeDefined();

        // Vérification status health si présent
        if (body.health) {
          expect(body.health).toHaveProperty('status');
        }
      }
    );

    test(
      'POST /api/internal/diagnostic/run répond',
      async ({ request }) => {
        test.setTimeout(120000);

        const { rawBody } = await fetchWithRetry(
          request,
          `${API_BASE_URL}/api/internal/diagnostic/run`,
          {
            method: 'POST',
            retries: 3,
            delay: 1500,
          }
        );

        let body;

        try {
          body = JSON.parse(rawBody);
        } catch (error) {
          throw new Error(
            `JSON diagnostic invalide:\n${rawBody}`
          );
        }

        expect(body).toHaveProperty('ran_at');
        expect(body).toHaveProperty('success');
        expect(typeof body.success).toBe('boolean');
      }
    );

    test(
      'POST /api/internal/tests/run répond',
      async ({ request }) => {
        test.setTimeout(120000);

        const { rawBody } = await fetchWithRetry(
          request,
          `${API_BASE_URL}/api/internal/tests/run`,
          {
            method: 'POST',
            retries: 3,
            delay: 1500,
          }
        );

        let body;

        try {
          body = JSON.parse(rawBody);
        } catch (error) {
          throw new Error(
            `JSON tests invalide:\n${rawBody}`
          );
        }

        // On ne logge plus le JSON des tests
        expect(body).toHaveProperty('ran_at');
        expect(body).toHaveProperty('success');
        expect(typeof body.success).toBe('boolean');

        // Les logs pytest sont optionnels : on les garde mais on peut les commenter si besoin
        if (body.stdout) {
          console.log('\nPYTEST STDOUT (tronqué si long) :\n');
          console.log(body.stdout.substring(0, 500) + (body.stdout.length > 500 ? '…' : ''));
        }

        if (body.stderr) {
          console.error('\nPYTEST STDERR (tronqué) :\n');
          console.error(body.stderr.substring(0, 500) + (body.stderr.length > 500 ? '…' : ''));
        }
      }
    );
  }
);
