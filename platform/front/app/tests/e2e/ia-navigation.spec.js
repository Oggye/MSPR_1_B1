const { test, expect } = require('@playwright/test');
const { createAuthenticatedSession } = require('./auth');


const predictionContext = {
  countries: ['France'],
  data_min_year: 2010,
  data_max_year: 2024,
  forecast_origin_year: 2024,
  target_min_year: 2025,
  target_max_year: 2027,
  max_horizon: 3,
  passenger_unit: 'MIO_PKM',
  co2_unit: 'MIO_T',
};


const classificationPrediction = {
  country: 'France',
  origin_year: 2024,
  year: 2025,
  horizon: 1,

  prediction: 0,
  label: 'Stabilité / croissance probable',
  probability_decline: 0.25,
  decision_margin: 25,

  risk_level: 'Faible',
  risk_description: 'Le risque de baisse estimé reste limité.',

  business_message:
    'La tendance simulée pour le test E2E reste favorable.',

  forecast_context: null,

  key_drivers: [],

  metadata: {
    model_name: 'E2E classification mock',
    axis: 'classification',

    metrics: {
      by_horizon: {
        '1': {
          f1: 0.7,
          roc_auc: 0.8,
        },
      },
    },
  },

  warnings: [],
  inference_ms: 1,
};


const regressionPrediction = {
  country: 'France',
  origin_year: 2024,
  year: 2025,
  horizon: 1,

  prediction_raw: 110,
  prediction_display: '110 MIO_PKM',

  prediction_low: 100,
  prediction_high: 120,
  interval_level: 0.9,

  trend_vs_origin: 10,
  trend_label: 'Croissance',

  business_message:
    'La tendance simulée pour le test E2E est en croissance.',

  reliability_note:
    'Réponse simulée uniquement pour valider le parcours utilisateur.',

  forecast_context: null,

  key_drivers: [],

  metadata: {
    model_name: 'E2E regression mock',
    axis: 'regression',

    metrics: {
      by_horizon: {
        '1': {
          mae: 1,
          r2: 0.9,
        },
      },
    },
  },

  warnings: [],
  inference_ms: 1,
};


async function mockIaEndpoints(page) {
  await page.route('**/api/predict/context', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(predictionContext),
    });
  });

  await page.route('**/api/predict/classification', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(classificationPrediction),
    });
  });

  await page.route('**/api/predict/regression', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(regressionPrediction),
    });
  });
}


test.describe('Navigation de l’interface IA', () => {
  test.beforeEach(async ({ page }) => {
    // L'authentification reste testée avec la vraie API.
    await createAuthenticatedSession(
      page.context().request,
      'user'
    );

    // Seuls les endpoints IA sont simulés.
    // Le but de ce fichier est de tester le parcours UI,
    // pas de reconstruire le warehouse et le pipeline ML.
    await mockIaEndpoints(page);
  });


  test(
    'barre latérale, prédictions et liens restent fonctionnels',
    async ({ page }) => {
      const consoleErrors = [];

      page.on('console', (message) => {
        if (message.type() === 'error') {
          consoleErrors.push(message.text());
        }
      });


      // -------------------------------------------------
      // Page IA
      // -------------------------------------------------

      await page.goto('/ia');

      await expect(
        page.getByRole(
          'heading',
          {
            name: 'Prévisions ferroviaires N+1 à N+3',
          }
        )
      ).toBeVisible();

      await expect(
        page.getByRole(
          'navigation',
          {
            name: 'Navigation IA',
          }
        )
      ).toBeVisible();

      await expect(
        page.getByRole(
          'link',
          {
            name: 'IA',
          }
        )
      ).toHaveAttribute(
        'aria-current',
        'page'
      );

      await expect(
        page.getByRole(
          'link',
          {
            name: 'Supervision',
          }
        )
      ).toHaveCount(0);


      // -------------------------------------------------
      // Classification
      // -------------------------------------------------

      await expect(
        page.getByLabel('Pays')
      ).toBeVisible();

      await page
        .getByRole(
          'button',
          {
            name: 'Lancer la prédiction',
          }
        )
        .click();

      await expect(
        page.locator('.ia-result')
      ).toBeVisible();


      // -------------------------------------------------
      // Régression
      // -------------------------------------------------

      await page
        .getByRole(
          'button',
          {
            name: 'Activité voyageurs',
          }
        )
        .click();

      await page
        .getByRole(
          'button',
          {
            name: 'Lancer la prédiction',
          }
        )
        .click();

      await expect(
        page.locator('.ia-result')
      ).toBeVisible();


      // -------------------------------------------------
      // Retour vers l'espace externe
      // -------------------------------------------------

      await page
        .getByRole(
          'link',
          {
            name: 'Espace externe',
          }
        )
        .click();

      await expect(page).toHaveURL(
        /\/externe\/HomePage$/
      );

      await expect(
        page.getByRole(
          'heading',
          {
            name: /Vue d'ensemble/i,
          }
        )
      ).toBeVisible();


      // -------------------------------------------------
      // Retour accueil
      // -------------------------------------------------

      await page.goto('/ia');

      await page
        .getByRole(
          'link',
          {
            name: 'Accueil',
          }
        )
        .click();

      await expect(page).toHaveURL(
        /\/$/
      );

      await expect(
        page.getByRole(
          'heading',
          {
            name: 'ObRail Europe',
          }
        )
      ).toBeVisible();


      // -------------------------------------------------
      // Déconnexion
      // -------------------------------------------------

      await page.goto('/ia');

      await page
        .getByRole(
          'button',
          {
            name: 'Déconnexion',
          }
        )
        .click();

      await expect(page).toHaveURL(
        /\/login$/
      );


      // -------------------------------------------------
      // Console navigateur
      // -------------------------------------------------

      expect(consoleErrors).toEqual([]);
    }
  );
});