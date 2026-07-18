import { defineConfig, devices } from '@playwright/test';
import path from 'path';

const OUTPUT_DIR = path.join(__dirname, '../outputs/playwright');

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on',
    video: 'on',
    screenshot: 'on',
    headless: true,
    actionTimeout: 15000,
    navigationTimeout: 30000,
    recordHar: { path: path.join(OUTPUT_DIR, 'network.har'), mode: 'full' },
  },
  projects: [
    {
      name: 'chromium',
      use: { 
        ...devices['Desktop Chrome'],
      },
    },
  ],
  outputDir: OUTPUT_DIR,
});