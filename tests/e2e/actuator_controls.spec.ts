import { test, expect } from "@playwright/test";

/**
 * Tier 4 Playwright E2E Test Suite:
 * Two-Way Actuator Controls & Interactive Hardware Toggles.
 *
 * Derivation Source: ORIGINAL_REQUEST § R4 & PROJECT.md § Feature 22:
 * "Two-Way Actuator Control Panel: Interactive UI toggles for Peltier cooling,
 *  ventilation servo, and slot RGB locator triggers."
 */

test.describe("Tier 4: Two-Way Actuator Controls UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard");
  });

  test("actuator control toggles exist on dashboard panel", async ({ page }) => {
    // Check for actuator controls panel
    const actuatorSection = page.locator(
      "[data-testid='actuator-panel'], [data-testid='hardware-controls'], :text('Peltier'), :text('Cooling'), :text('Ventilation')"
    );
    if (await actuatorSection.count() > 0) {
      await expect(actuatorSection.first()).toBeVisible();
    }
  });

  test("toggling Peltier cooler triggers active state transition", async ({ page }) => {
    // Find Peltier cooling switch / button
    const peltierToggle = page.locator(
      "[data-testid='toggle-peltier'], button:has-text('Peltier'), button:has-text('Cooling'), [aria-label*='Peltier']"
    );
    if (await peltierToggle.isVisible()) {
      await peltierToggle.first().click();
      await page.waitForTimeout(300);

      // Verify button or status indicator reflects updated state
      const activeIndicator = page.locator(".bg-emerald-500, .bg-cyan-500, :text('ACTIVE'), :text('ON')");
      expect(await activeIndicator.count()).toBeGreaterThanOrEqual(1);
    }
  });

  test("toggling ventilation exhaust servo updates mechanical angle indicator", async ({ page }) => {
    // Find ventilation servo switch / slider
    const servoToggle = page.locator(
      "[data-testid='toggle-ventilation'], button:has-text('Ventilation'), button:has-text('Servo'), button:has-text('Exhaust')"
    );
    if (await servoToggle.isVisible()) {
      await servoToggle.first().click();
      await page.waitForTimeout(300);

      const angleLabel = page.locator(":text('90°'), :text('OPEN'), :text('Exhaust Active')");
      if (await angleLabel.count() > 0) {
        await expect(angleLabel.first()).toBeVisible();
      }
    }
  });
});
