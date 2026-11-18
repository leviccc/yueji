import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5183',
    channel: process.platform === 'win32' ? 'msedge' : undefined,
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
  },
  outputDir: '../output/browser-tests',
  webServer: [
    {
      command: process.platform === 'win32'
        ? '..\\.venv\\Scripts\\python.exe ..\\scripts\\e2e_server.py'
        : '../.venv/bin/python ../scripts/e2e_server.py',
      url: 'http://127.0.0.1:8013/api/health',
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --config vite.e2e.config.ts',
      url: 'http://127.0.0.1:5183',
      reuseExistingServer: false,
    },
  ],
})
