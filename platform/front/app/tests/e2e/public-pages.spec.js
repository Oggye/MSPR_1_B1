const { test, expect } = require('@playwright/test');
const { createAuthenticatedSession } = require('./auth');

test.describe('Parcours frontend externe', () => {
  test.beforeEach(async ({ page }) => {
    await createAuthenticatedSession(page.context().request, 'user');
  });

  async function openMobileMenuIfNeeded(page) {
    const menuButton = page.getByRole('button', { name: /☰/ });
    if (await menuButton.isVisible()) {
      await menuButton.click();
    }
  }

  test('navigation entre toutes les pages externes obligatoires', async ({ page }) => {
    await page.goto('/externe/HomePage');
    await expect(page.getByRole('heading', { name: /Vue d'ensemble/i })).toBeVisible();

    await openMobileMenuIfNeeded(page);
    await page.getByRole('link', { name: /Trajets/i }).click();
    await expect(page).toHaveURL(/\/externe\/Trajets$/);
    await expect(page.getByRole('heading', { name: /Trajets européens/i })).toBeVisible();

    await openMobileMenuIfNeeded(page);
    await page.getByRole('link', { name: /Carte/i }).click();
    await expect(page).toHaveURL(/\/externe\/Map$/);
    await expect(page.getByRole('heading', { name: /Carte de synthèse ferroviaire/i })).toBeVisible();

    await openMobileMenuIfNeeded(page);
    await page.getByRole('link', { name: /Statistiques/i }).click();
    await expect(page).toHaveURL(/\/externe\/Statistique$/);
    await expect(page.getByRole('heading', { name: /Tableau de bord statistique/i })).toBeVisible();

    await openMobileMenuIfNeeded(page);
    await page.getByRole('link', { name: /Opérateurs/i }).click();
    await expect(page).toHaveURL(/\/externe\/Operateur$/);
    await expect(page.getByRole('heading', { name: /Opérateurs ferroviaires/i })).toBeVisible();
  });

  test('page trajets: filtres + état vide utilisateur', async ({ page }) => {
    await page.goto('/externe/Trajets');
    await expect(page.getByRole('heading', { name: /Trajets européens/i })).toBeVisible();

    await page.getByPlaceholder('SNCF, DB, Renfe...').fill('this_operator_does_not_exist');
    await page.getByRole('button', { name: 'Appliquer' }).click();
    await expect(page.getByText('Aucun trajet pour ces filtres.')).toBeVisible();
  });

  test('page map: filtre de type et synthèse', async ({ page }) => {
    await page.goto('/externe/Map');

    await expect(page.getByRole('heading', { name: /Carte de synthèse ferroviaire/i })).toBeVisible();
    await expect(page.locator('.ob-map-canvas')).toBeVisible();
    await expect(page.getByRole('combobox')).toHaveCount(5);

    const typeFilter = page.getByRole('combobox', { name: 'Type' });
    await typeFilter.selectOption('night');
    await expect(typeFilter).toHaveValue('night');
    await expect(page.getByRole('heading', { name: /Synthèse par pays/i })).toBeVisible();
  });

  test('page statistiques: sections analytiques visibles', async ({ page }) => {
    await page.goto('/externe/Statistique');
    await expect(page.getByRole('heading', { name: /Tableau de bord statistique/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Évolution jour \/ nuit/i })).toBeVisible();
    await expect(
      page.getByRole('heading', { name: /Classement du ratio CO₂ \/ activité voyageurs/i })
    ).toBeVisible();
  });

  test('page opérateurs: sélection et affichage des détails', async ({ page }) => {
    await page.goto('/externe/Operateur');
    await expect(page.getByRole('heading', { name: /Opérateurs ferroviaires/i })).toBeVisible();

    const operators = page.locator('.ob-operators-list button');
    const count = await operators.count();
    test.skip(count === 0, 'Aucun opérateur disponible dans l’environnement de test');

    await operators.first().click();
    await expect(page.locator('.ob-operator-hero')).toBeVisible();
    await expect(page.getByRole('heading', { name: /Évolution annuelle/i })).toBeVisible();
  });
});
