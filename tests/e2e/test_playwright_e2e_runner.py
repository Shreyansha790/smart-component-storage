"""
Tier 4 E2E Test Suite Runner & Verification Harness.

Validates Playwright configuration, spec completeness, and test discovery across all
user acceptance criteria:
1. 3D Cabinet Matrix & Slot-Level Telemetry
2. Pull-Out Drawer Inspection & Pick-and-Place Interaction
3. 60 FPS Transition Benchmarking & Zero Layout Shift (CLS < 0.05)
4. Real-Time Telemetry Sync Without Full Page Reload
5. Two-Way Bidirectional Actuator Controls
"""

import os
from pathlib import Path
import subprocess
import pytest


E2E_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = E2E_DIR.parent.parent

REQUIRED_SPECS = [
    "cabinet_3d_matrix.spec.ts",
    "pull_out_drawer.spec.ts",
    "fps_and_cls_benchmark.spec.ts",
    "realtime_telemetry_sync.spec.ts",
    "actuator_controls.spec.ts",
]


class TestTier4PlaywrightE2EIntegrity:
    """Verifies that the Playwright E2E suite is fully configured, discovered, and valid."""

    def test_playwright_config_exists_and_configured(self):
        """Verifies playwright.config.ts exists at project root with proper testDir and baseURL."""
        config_path = PROJECT_ROOT / "playwright.config.ts"
        assert config_path.exists(), "playwright.config.ts must exist at project root"

        content = config_path.read_text(encoding="utf-8")
        assert "testDir" in content
        assert "./tests/e2e" in content
        assert "baseURL" in content
        assert "chromium" in content

    @pytest.mark.parametrize("spec_filename", REQUIRED_SPECS)
    def test_required_e2e_spec_exists(self, spec_filename):
        """Verifies each required Playwright test specification file exists in tests/e2e/."""
        spec_path = E2E_DIR / spec_filename
        assert spec_path.exists(), f"Missing required Playwright spec: {spec_filename}"
        assert spec_path.stat().st_size > 200, f"Spec {spec_filename} is empty or incomplete"

    def test_package_json_contains_e2e_test_scripts(self):
        """Verifies package.json contains test:e2e runner scripts."""
        package_json_path = PROJECT_ROOT / "package.json"
        assert package_json_path.exists()
        content = package_json_path.read_text(encoding="utf-8")
        assert '"test:e2e": "playwright test"' in content

    def test_playwright_discovers_all_test_specs_cleanly(self):
        """
        Runs `npx playwright test --list` to verify all specs are discovered
        by Playwright runner without syntax or TypeScript errors.
        """
        result = subprocess.run(
            ["npx", "playwright", "test", "--list"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            shell=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Playwright test discovery failed!\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

        output = result.stdout
        # Verify that all 5 spec files are listed in Playwright output
        for spec in REQUIRED_SPECS:
            assert spec in output, f"Spec {spec} was not discovered by Playwright runner!\nOutput: {output}"
