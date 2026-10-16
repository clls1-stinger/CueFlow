import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', testMatch: '**/*.spec.js', timeout: 120000, workers: 1,
  use: { baseURL: process.env.CUEFLOW_URL || 'http://127.0.0.1:4173', locale: 'es-MX', launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox'] } },
  webServer: process.env.CUEFLOW_URL ? undefined : { command: 'npm run preview -- --port 4173', url: 'http://127.0.0.1:4173', reuseExistingServer: !process.env.CI },
});
