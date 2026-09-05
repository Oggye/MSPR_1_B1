const { test, expect } = require('@playwright/test');
const { createAuthenticatedSession } = require('./auth');

test.describe('Parcours frontend interne admin', () => {
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ page }) => {
    await createAuthenticatedSession(page.context().request, 'admin');
  });

  test('chargement dashboard interne et navigation tabs', async ({ page }) => {
    await page.goto('/interne/HomePage');

    await expect(page.getByRole('heading', { name: 'ObRail Operations' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Monitoring' })).toBeVisible();

    await page.getByRole('button', { name: 'Tests & Qualite' }).click();

    await expect(
      page.getByRole('button', { name: /diagnostic/i })
    ).toBeVisible({ timeout: 30000 });

    // Correction : le composant TestsTab affiche un bouton "Lancer" par catégorie de test
    // On vérifie qu'au moins un bouton "Lancer" est visible
    await expect(page.getByRole('button', { name: 'Lancer' }).first()).toBeVisible();

    await page.getByRole('button', { name: 'CI/CD' }).click();

    await expect(page.getByText(/Pipeline/i)).toBeVisible();
  });

  test('affichage erreur réseau sur overview interne', async ({ page }) => {
    await page.route('**/api/internal/overview', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'boom'
        })
      });
    });

    await page.goto('/interne/HomePage');

    await expect(
      page.getByText(/Erreur API 500 sur \/api\/internal\/overview/i)
    ).toBeVisible();

    await page.unroute('**/api/internal/overview');
  });
});
