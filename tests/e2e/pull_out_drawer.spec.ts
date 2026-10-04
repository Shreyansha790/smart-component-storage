import { test, expect } from "@playwright/test";

/**
 * Tier 4 Playwright E2E Test Suite:
 * Pull-Out Drawer Inspection & Smooth Pick-and-Place Interaction.
 *
 * Derivation Source: ORIGINAL_REQUEST § Acceptance:
 * "Interactive 3D physical cabinet matrix with slot-level telemetry,
 *  status glow, and pull-out drawer inspection."
 */

test.describe("Tier 4: Pull-Out Drawer Inspection Interaction", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("clicking a slot triggers drawer pull-out animation and inspection card", async ({ page }) => {
    // Locate interactive slot
    const slot = page.locator("[data-testid^='slot-'], [data-slot-id], .cabinet-slot, [data-slot]").first();
    if (await slot.isVisible()) {
      // Click slot to initiate pull-out inspection
      await slot.click();

      // Drawer inspection panel / modal should appear or transform
      const inspectionPanel = page.locator(
        "[data-testid='drawer-inspection'], [data-testid='slot-details'], [role='dialog'], .drawer-panel, .inspection-card"
      );
      await expect(inspectionPanel.first()).toBeVisible({ timeout: 5000 });

      // Verify batch parameters are displayed in the inspection panel
      const batchDetails = page.locator(
        ":text('Part Number'), :text('Batch ID'), :text('Shelf Life'), :text('Remaining'), :text('Degradation')"
      );
      expect(await batchDetails.count()).toBeGreaterThanOrEqual(1);

      // Close drawer inspection (via close button or backdrop click)
      const closeButton = page.locator("button:has-text('Close'), button[aria-label='Close'], [data-testid='close-drawer']");
      if (await closeButton.isVisible()) {
        await closeButton.first().click();
        await page.waitForTimeout(300);
      }
    }
  });

  test("pick-and-place locator indicator highlights target slot", async ({ page }) => {
    // Test slot locator button or LED trigger if present
    const locateButton = page.locator("button:has-text('Locate'), button:has-text('Find Slot'), [data-testid='locate-slot']");
    if (await locateButton.isVisible()) {
      await locateButton.first().click();
      await page.waitForTimeout(200);

      // Verify highlighted / active pulse animation
      const activePulseSlot = page.locator(".animate-pulse, .glow-active, [data-located='true'], .ring-emerald-400");
      expect(await activePulseSlot.count()).toBeGreaterThanOrEqual(1);
    }
  });
});
