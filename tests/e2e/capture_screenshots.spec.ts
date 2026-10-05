import { test } from '@playwright/test';
import path from 'path';

test('capture authentic presentation screenshots', async ({ page }) => {
  const outDir = 'C:/Users/Shreyansh Agrawal/.gemini/antigravity/brain/eed6dcf9-947b-418b-82b4-c07514f51216/scratch';

  await page.setViewportSize({ width: 1440, height: 900 });

  console.log('Navigating to http://localhost:3000/dashboard...');
  await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // 1. Full Dashboard Real Screenshot
  await page.screenshot({ path: path.join(outDir, 'real_app_dashboard.png') });
  console.log('Captured real_app_dashboard.png');

  // 2. 3D Cabinet Matrix
  const cabinet = page.locator('[data-testid="cabinet-matrix"]');
  if (await cabinet.count() > 0) {
    await cabinet.screenshot({ path: path.join(outDir, 'real_app_cabinet_3d.png') });
    console.log('Captured real_app_cabinet_3d.png');
  }

  // 3. Actuator Controls
  const actuators = page.locator('[data-testid="actuator-panel"]');
  if (await actuators.count() > 0) {
    await actuators.screenshot({ path: path.join(outDir, 'real_app_actuators.png') });
    console.log('Captured real_app_actuators.png');
  }

  // 4. Oscilloscope Canvas
  const oscilloscope = page.locator('[data-testid="oscilloscope-container"]');
  if (await oscilloscope.count() > 0) {
    await oscilloscope.screenshot({ path: path.join(outDir, 'real_app_oscilloscope.png') });
    console.log('Captured real_app_oscilloscope.png');
  }

  // 5. Drawer Inspection Modal
  const slot = page.locator('[data-testid="slot-A1"]');
  if (await slot.count() > 0) {
    await slot.click();
    await page.waitForTimeout(800);
    const drawerInspection = page.locator('[data-testid="drawer-inspection"]');
    if (await drawerInspection.count() > 0) {
      await drawerInspection.screenshot({ path: path.join(outDir, 'real_app_drawer_inspection.png') });
      console.log('Captured real_app_drawer_inspection.png');
    }
  }

  // 6. Inventory Page
  await page.goto('http://localhost:3000/inventory', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, 'real_app_inventory.png') });
  console.log('Captured real_app_inventory.png');
});
