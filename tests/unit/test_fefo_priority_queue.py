"""
Tier 1 Unit Tests: Dynamic Arrhenius FEFO (First Expired, First Out) Queue Sorting Algorithm.

Derivation Source: PROJECT.md § Feature 11 & explorer_survey_testing_1/report.md § 3.7.
Tests standard linear FEFO and Dynamic Arrhenius FEFO queue priority inversion.
"""

import pytest
from services.fefo_service import prioritize_fefo
from services.lifecycle_service import calculate_lifecycle
from tests.helpers.arrhenius_oracle import dynamic_fefo_sort, calculate_dynamic_shelf_life


class TestFEFOPriorityQueue:
    """Verifies queue sorting rules, tie-breaking, and dynamic thermal inversion."""

    def test_dynamic_arrhenius_fefo_queue_inversion(self):
        """
        CRITICAL TEST: Thermal degradation inverts calendar-based FEFO priority.

        Batch A: Stored 60 calendar days at 20°C (cold/nominal).
                 Linear remaining: 120 days.
        Batch B: Stored 30 calendar days at 50°C (severe thermal stress, AF ≈ 6.4).
                 Linear remaining: 150 days.

        Under naive linear FEFO:
          Batch A (120 remaining) is dispatched BEFORE Batch B (150 remaining).

        Under Dynamic Arrhenius FEFO:
          Batch B has suffered accelerated degradation and has < 0 days remaining!
          Batch B MUST be prioritized FIRST in the dispatch queue ahead of Batch A!
        """
        # Batch A: 60 days stored at 20°C (AF ≈ 0.67, effective days ≈ 40.2, remaining ≈ 139.8)
        batch_a = {
            "batch_id": "BATCH-001-COLD",
            "part_number": "STM32F4",
            "nominal_shelf_life_days": 180,
            "nominal_stored_days": 60,
            "dynamic_remaining_days": 139.8,
            "status": "OPTIMAL",
        }

        # Batch B: 30 days stored at 50°C (AF ≈ 6.4, effective days ≈ 192, remaining ≈ -12)
        batch_b = {
            "batch_id": "BATCH-002-HEAT-STRESSED",
            "part_number": "STM32F4",
            "nominal_shelf_life_days": 180,
            "nominal_stored_days": 30,
            "dynamic_remaining_days": -12.0,
            "status": "EXPIRED",
        }

        # Batch C: 10 days stored at 25°C baseline (remaining = 170)
        batch_c = {
            "batch_id": "BATCH-003-NEW",
            "part_number": "STM32F4",
            "nominal_shelf_life_days": 180,
            "nominal_stored_days": 10,
            "dynamic_remaining_days": 170.0,
            "status": "OPTIMAL",
        }

        queue = [batch_a, batch_b, batch_c]
        sorted_queue = dynamic_fefo_sort(queue)

        # Batch B must be first, followed by A, then C
        assert sorted_queue[0]["batch_id"] == "BATCH-002-HEAT-STRESSED"
        assert sorted_queue[1]["batch_id"] == "BATCH-001-COLD"
        assert sorted_queue[2]["batch_id"] == "BATCH-003-NEW"

    def test_standard_linear_fefo_fallback(self):
        """
        Verifies standard FEFO sorting by remainingDays using root services.fefo_service.
        """
        components = [
            {"batchId": "B3", "remainingDays": 200},
            {"batchId": "B1", "remainingDays": 15},
            {"batchId": "B2", "remainingDays": 80},
        ]

        sorted_components = prioritize_fefo(components)
        assert [c["batchId"] for c in sorted_components] == ["B1", "B2", "B3"]

    def test_fefo_tie_breaking_consistency(self):
        """
        When two batches have identical dynamic remaining shelf life,
        tie breaking should prefer the batch with higher nominal stored days
        (older stock) or deterministic batch_id.
        """
        batch_x = {
            "batch_id": "BATCH-X",
            "nominal_stored_days": 40,
            "dynamic_remaining_days": 50.0,
        }
        batch_y = {
            "batch_id": "BATCH-Y",
            "nominal_stored_days": 60,  # Older batch
            "dynamic_remaining_days": 50.0,
        }

        sorted_queue = dynamic_fefo_sort([batch_x, batch_y])
        assert sorted_queue[0]["batch_id"] == "BATCH-Y"
        assert sorted_queue[1]["batch_id"] == "BATCH-X"

    def test_fefo_handles_empty_queue(self):
        """Empty component list returns empty queue without exceptions."""
        assert dynamic_fefo_sort([]) == []
        assert prioritize_fefo([]) == []

    def test_fefo_handles_all_expired_components(self):
        """
        All components expired (negative remaining days):
        Sorts the most severely expired first (most negative remaining days).
        """
        batches = [
            {"batch_id": "B-EXP-10", "dynamic_remaining_days": -10.0},
            {"batch_id": "B-EXP-50", "dynamic_remaining_days": -50.0},
            {"batch_id": "B-EXP-01", "dynamic_remaining_days": -1.0},
        ]
        sorted_batches = dynamic_fefo_sort(batches)
        assert [b["batch_id"] for b in sorted_batches] == ["B-EXP-50", "B-EXP-10", "B-EXP-01"]

    def test_fefo_skips_malformed_entries(self):
        """Entries missing remainingDays key are gracefully ignored by linear FEFO."""
        entries = [
            {"batchId": "VALID-1", "remainingDays": 10},
            {"batchId": "INVALID-NO-DAYS", "status": "Error"},
            {"batchId": "VALID-2", "remainingDays": 5},
        ]
        sorted_entries = prioritize_fefo(entries)
        assert len(sorted_entries) == 2
        assert sorted_entries[0]["batchId"] == "VALID-2"
        assert sorted_entries[1]["batchId"] == "VALID-1"
