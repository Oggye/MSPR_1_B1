const { defineConfig, devices } = require('@playwright/test');

const isCI = Boolean(process.env.CI);

module.exports = defineConfig({
  testDir: './tests/e2e',

  // En local on garde le parallélisme.
  // En CI on sérialise les tests pour éviter les conflits
  // sur la même base PostgreSQL (création de comptes, sessions, etc.).
  fullyParallel: !isCI,
  workers: isCI ? 1 : undefined,

  // Une seule relance suffit en CI.
  retries: isCI ? 1 : 0,

  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],

  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',

    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  expect: {
    timeout: 10000,
  },

  projects: [
    {
      name: 'desktop-chromium',
      use: {
        ...devices['Desktop Chrome'],
        browserName: 'chromium',
      },
    },
    {
      name: 'tablet',
      testIgnore: /internal-endpoints\.spec\.js/,
      use: {
        ...devices['iPad (gen 7)'],
        browserName: 'chromium',
      },
    },
    {
      name: 'mobile',
      testIgnore: /internal-endpoints\.spec\.js/,
      use: {
        ...devices['Pixel 5'],
        browserName: 'chromium',
      },
    },
  ],
});