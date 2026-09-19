import { expect, test } from '@playwright/test';
import path from 'node:path';

const FIXTURES = path.resolve(import.meta.dirname, '..', 'backend', 'tests', 'fixtures');
const VENDOR_BPMN = path.join(FIXTURES, 'import_camunda_vendor.bpmn');
const INCIDENT_XLSX = path.join(FIXTURES, 'scenario_it_incident_capture.xlsx');

/**
 * End-to-end user scenarios for Process2BPMN (Scope v2).
 * Exercises empty start state, foreign BPMN import, structured capture template ingestion,
 * target profile switching, and export generation.
 */
test.describe('Process2BPMN smoke and multi-scenario verification', () => {
  test('the app starts empty and offers the capture template', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Turn any process description into BPMN')).toBeVisible();
    // Nothing is preloaded: no diagram until the person converts something.
    await expect(page.locator('#bpmn-canvas-container')).toHaveCount(0);

    await page.locator('#toolbar-template-btn').click();
    await expect(page.getByText('Download blank (.xlsx)')).toBeVisible();
    await expect(page.getByText('Download blank (.docx)')).toBeVisible();
    await page.keyboard.press('Escape');
  });

  test('imports a foreign BPMN file, keeps layout, triggers relayout, and exports', async ({ page }) => {
    await page.goto('/');

    await page.locator('input[type="file"]').first().setInputFiles(VENDOR_BPMN);

    // The diagram renders…
    await expect(page.locator('#bpmn-canvas-container')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('.djs-container')).toBeVisible({ timeout: 30_000 });

    // …with the counts the importer reported, and the imported coordinates kept.
    await expect(page.getByText(/7 Elements · 6 Flows/)).toBeVisible();
    await expect(page.locator('#relayout-btn')).toBeVisible();

    // Re-layout swaps the imported coordinates for a computed layout and then goes away.
    await page.locator('#relayout-btn').click();
    await expect(page.locator('#relayout-btn')).toHaveCount(0);

    // Export produces a real BPMN file.
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export', exact: true }).click();
    await page.getByText('BPMN 2.0 XML', { exact: true }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.bpmn$/);
  });

  test('converts structured capture template (.xlsx) deterministically and allows profile switching', async ({ page }) => {
    await page.goto('/');

    // Upload IT incident capture Excel sheet
    await page.locator('input[type="file"]').first().setInputFiles(INCIDENT_XLSX);

    // Click "Convert Process"
    await page.getByRole('button', { name: 'Convert Process' }).click();

    // Diagram container renders without model call
    await expect(page.locator('#bpmn-canvas-container')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('.djs-container')).toBeVisible({ timeout: 30_000 });

    // Switch export profile from Celonis to Generic in toolbar
    const selector = page.locator('#toolbar-profile-selector');
    await expect(selector).toBeVisible();
    await selector.getByRole('tab', { name: 'Generic' }).click();

    // Verify Generic tab becomes active
    await expect(selector.getByRole('tab', { name: 'Generic' })).toHaveAttribute('aria-selected', 'true');

    // Verify Export dropdown options
    await page.getByRole('button', { name: 'Export', exact: true }).click();
    await expect(page.getByText('BPMN 2.0 XML', { exact: true })).toBeVisible();
    await expect(page.getByText('Vector Graphic', { exact: true })).toBeVisible();
    await expect(page.getByText('High-Res Image', { exact: true })).toBeVisible();
  });

  test('the target selector offers exactly Celonis and Generic', async ({ page }) => {
    await page.goto('/');
    const selector = page.locator('#toolbar-profile-selector');
    await expect(selector).toBeVisible();
    const labels = await selector.locator('button').allInnerTexts();
    expect(labels.map((l) => l.trim())).toEqual(['Celonis', 'Generic']);
  });
});
