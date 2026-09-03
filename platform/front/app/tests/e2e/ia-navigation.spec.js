const { test, expect } = require('@playwright/test');
const { createAuthenticatedSession } = require('./auth');

test.describe('Navigation de l’interface IA', () => {
  test.beforeEach(async ({ page }) => {
    await createAuthenticatedSession(page.context().request, 'user');
  });

  test('barre latérale, prédictions et liens restent fonctionnels', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text());
    });

    await page.goto('/ia');

    await expect(
      page.getByRole('heading', { name: 'Prévisions ferroviaires N+1 à N+3' })
    ).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Navigation IA' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'IA' })).toHaveAttribute('aria-current', 'page');
    await expect(page.getByRole('link', { name: 'Supervision' })).toHaveCount(0);

    await expect(page.getByLabel('Pays')).toBeVisible();
    await page.getByRole('button', { name: 'Lancer la prédiction' }).click();
    await expect(page.locator('.ia-result')).toBeVisible();

    await page.getByRole('button', { name: 'Activité voyageurs' }).click();
    await page.getByRole('button', { name: 'Lancer la prédiction' }).click();
    await expect(page.locator('.ia-result')).toBeVisible();

    await page.getByRole('link', { name: 'Espace externe' }).click();
    await expect(page).toHaveURL(/\/externe\/HomePage$/);
    await expect(page.getByRole('heading', { name: /Vue d'ensemble/i })).toBeVisible();

    await page.goto('/ia');
    await page.getByRole('link', { name: 'Accueil' }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('heading', { name: 'ObRail Europe' })).toBeVisible();

    await page.goto('/ia');
    await page.getByRole('button', { name: 'Déconnexion' }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(consoleErrors).toEqual([]);
  });
});
