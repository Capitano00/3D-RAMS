from __future__ import annotations

import sys
import unittest
import os
from pathlib import Path
from unittest import mock


ENTRY_APP_ROOT = Path(__file__).resolve().parents[1]
if str(ENTRY_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(ENTRY_APP_ROOT))

from intake_coordinator import (  # noqa: E402
    IntakeValidationError,
    build_confirmed_entry_payload,
    build_entry_turn,
    coordinate_intake,
)
from llm_intake import openai_intake_model_json, select_model_json  # noqa: E402


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        import json

        return json.dumps(self.payload).encode("utf-8")


class IntakeCoordinatorTests(unittest.TestCase):
    def test_blank_intake_provider_selects_openai_compatible_model(self):
        with mock.patch.dict("os.environ", {"ENTRY_INTAKE_PROVIDER": "", "ENTRY_INTAKE_MODE": "llm_first"}, clear=False):
            selected = select_model_json({"runtimeOptions": {"useBedrock": True}}, None)

        self.assertIs(selected, openai_intake_model_json)

    def test_missing_location_returns_clarification(self):
        result = coordinate_intake({"message": "Can you help me?", "conversationId": "c1"})

        self.assertEqual(result["status"], "clarification_required")
        self.assertTrue(result["clarifyingQuestions"])
        self.assertIsNone(result["caseId"])

    def test_site_message_returns_confirmation_ready_intake(self):
        result = coordinate_intake(
            {
                "message": "I want to visit 8 Albert Embankment tomorrow for a survey for 2km",
                "conversationId": "c2",
            }
        )

        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["intake"]["locationText"], "8 Albert Embankment")
        self.assertEqual(result["intake"]["areaScope"]["meters"], 2000)
        self.assertIsNone(result["caseId"])

    def test_site_message_without_area_asks_only_for_area(self):
        result = coordinate_intake(
            {
                "message": "I want to visit 8 Albert Embankment tomorrow for a survey",
                "conversationId": "c2-missing-area",
            }
        )

        self.assertEqual(result["status"], "clarification_required")
        self.assertEqual(result["clarifyingQuestions"], ["What area should I cover around the site, for example a radius or boundary?"])

    def test_confirmed_intake_creates_case_id(self):
        payload = {
            "message": "I want to visit 8 Albert Embankment tomorrow for a survey for 2km",
            "conversationId": "c3",
            "confirmedByUser": True,
        }

        result = coordinate_intake(payload)
        confirmed = build_confirmed_entry_payload(build_entry_turn(payload), result)

        self.assertEqual(result["status"], "launch_ready")
        self.assertTrue(result["caseId"].startswith("case_"))
        self.assertEqual(confirmed["caseId"], result["caseId"])
        self.assertTrue(confirmed["confirmedByUser"])

    def test_confirmed_model_confirmation_with_valid_intake_launches(self):
        result = coordinate_intake(
            {
                "message": "Confirmed. Location: 48 Quernmore Road. Area scope: 25m radius. Goal: confined workspace readiness review.",
                "conversationId": "c3-model-confirm",
                "confirmedByUser": True,
            },
            model_json=lambda _: {
                "status": "confirmation_required",
                "intake": {
                    "locationText": "48 Quernmore Road",
                    "areaScope": {"type": "radius", "meters": 25},
                    "userGoal": "confined workspace readiness review",
                    "materials": [],
                },
            },
        )

        self.assertEqual(result["status"], "launch_ready")
        self.assertTrue(result["caseId"].startswith("case_"))

    def test_confirmation_sentence_creates_case_id(self):
        payload = {
            "message": "Confirmed. Proceed with the review-required workflow.",
            "conversationId": "c3-sentence-confirmation",
            "intake": {
                "locationText": "48 Quernmore Road",
                "areaScope": {"type": "radius", "meters": 25},
                "userGoal": "confined workspace readiness review",
                "materials": [],
            },
        }

        result = coordinate_intake(payload)

        self.assertEqual(result["status"], "launch_ready")
        self.assertTrue(result["caseId"].startswith("case_"))

    def test_ask_me_to_confirm_does_not_launch(self):
        result = coordinate_intake(
            {
                "message": (
                    "Location: 48 Quernmore Road. Area scope: 25m radius. "
                    "Goal: confined workspace readiness review. Ask me to confirm before launching."
                ),
                "conversationId": "c-ask-confirm",
            }
        )

        self.assertEqual(result["status"], "confirmation_required")
        self.assertIsNone(result["caseId"])

    def test_confirmed_payload_preserves_report_access(self):
        payload = {
            "message": "I want to visit 8 Albert Embankment tomorrow for a survey for 2km",
            "conversationId": "proxy-session-id",
            "confirmedByUser": True,
            "reportAccess": {
                "mode": "asi_session",
                "sessionId": "asi-launch-session",
                "authorizedCaseIds": ["case_expected"],
            },
        }

        result = coordinate_intake(payload)
        confirmed = build_confirmed_entry_payload(build_entry_turn(payload), result)

        self.assertEqual(confirmed["reportAccess"]["sessionId"], "asi-launch-session")

    def test_invalid_model_json_is_rejected(self):
        with self.assertRaisesRegex(IntakeValidationError, "valid JSON"):
            coordinate_intake({"message": "8 Albert Embankment for 2km"}, model_json=lambda _: "not json")

    def test_confirmation_message_includes_summary_when_model_message_is_empty_shell(self):
        result = coordinate_intake(
            {"message": "review 48 Quernmore Road within 800m", "conversationId": "c-empty-details"},
            model_json=lambda _: {
                "status": "confirmation_required",
                "assistantMessage": "Please confirm the details below before proceeding.",
                "intake": {
                    "locationText": "48 Quernmore Road, London",
                    "areaScope": {"type": "radius", "meters": 800},
                    "userGoal": "confined workspace inspection readiness review",
                    "materials": [],
                },
            },
        )

        self.assertEqual(result["status"], "confirmation_required")
        self.assertIn("48 Quernmore Road", result["assistantMessage"])
        self.assertIn("800m radius", result["assistantMessage"])
        self.assertIn("48 Quernmore Road", result["confirmation"]["summary"])

    def test_invalid_model_json_uses_deterministic_fallback(self):
        result = coordinate_intake(
            {
                "message": "I want to visit 8 Albert Embankment tomorrow for a survey for 2km",
                "conversationId": "c4",
            },
            model_json=lambda _: "not json",
            fallback_to_deterministic=True,
        )

        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["fallbackReason"], "invalid_model_json")
        self.assertEqual(result["intakeMode"], "fallback")
        self.assertEqual(result["intake"]["locationText"], "8 Albert Embankment")

    def test_model_schema_failure_uses_deterministic_fallback_and_can_launch(self):
        result = coordinate_intake(
            {
                "message": "I want to visit 8 Albert Embankment tomorrow for a survey for 2km",
                "conversationId": "c5",
                "confirmedByUser": True,
            },
            model_json=lambda _: {"status": "launch_ready", "intake": {"locationText": "8 Albert Embankment"}},
            fallback_to_deterministic=True,
        )

        self.assertEqual(result["status"], "launch_ready")
        self.assertEqual(result["fallbackReason"], "schema_validation_failed")
        self.assertEqual(result["intakeMode"], "fallback")
        self.assertTrue(result["caseId"].startswith("case_"))

    def test_zero_area_from_model_falls_back_to_area_clarification(self):
        result = coordinate_intake(
            {
                "message": "Inspect 48 Quernmore Road for confined workspace readiness",
                "conversationId": "c-zero-area",
            },
            model_json=lambda _: {
                "status": "confirmation_required",
                "intake": {
                    "locationText": "48 Quernmore Road",
                    "areaScope": {"type": "radius", "meters": 0},
                    "userGoal": "confined workspace readiness review",
                    "materials": [],
                },
            },
            fallback_to_deterministic=True,
        )

        self.assertEqual(result["status"], "clarification_required")
        self.assertIn("area", result["clarifyingQuestions"][0])

    def test_invalid_model_json_can_fallback_to_deterministic_intake(self):
        result = coordinate_intake(
            {"message": "8 Albert Embankment survey for 2km", "conversationId": "c4"},
            model_json=lambda _: "not json",
            fallback_to_deterministic=True,
        )

        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["intakeMode"], "fallback")
        self.assertEqual(result["fallbackReason"], "invalid_model_json")

    def test_postcodes_io_resolver_is_default_off(self):
        with mock.patch.dict(os.environ, {"ENABLE_POSTCODES_IO_RESOLVER": ""}, clear=False):
            with mock.patch("intake_coordinator.urllib.request.urlopen", side_effect=AssertionError("network disabled")) as urlopen:
                result = coordinate_intake({"message": "Survey SW1A 1AA within 500m", "conversationId": "postcode-off"})

        self.assertEqual(result["status"], "confirmation_required")
        self.assertNotIn("lat", result["intake"]["locationCandidate"])
        urlopen.assert_not_called()

    def test_enabled_full_postcode_lookup_adds_source_labelled_candidate(self):
        response = {
            "status": 200,
            "result": {
                "postcode": "SW1A 1AA",
                "outcode": "SW1A",
                "latitude": 51.501009,
                "longitude": -0.141588,
                "admin_district": "Westminster",
                "region": "London",
                "country": "England",
            },
        }

        def fake_urlopen(req, timeout):
            self.assertIn("/postcodes/SW1A1AA", req.full_url)
            self.assertEqual(timeout, 2.0)
            return FakeHttpResponse(response)

        with mock.patch.dict(os.environ, {"ENABLE_POSTCODES_IO_RESOLVER": "true", "POSTCODES_IO_TIMEOUT_SECONDS": ""}, clear=False):
            with mock.patch("intake_coordinator.urllib.request.urlopen", side_effect=fake_urlopen):
                result = coordinate_intake({"message": "Survey SW1A 1AA within 500m", "conversationId": "postcode-on"})

        candidate = result["intake"]["locationCandidate"]
        self.assertEqual(result["status"], "confirmation_required")
        self.assertIsNone(result["caseId"])
        self.assertEqual(candidate["label"], "SW1A 1AA")
        self.assertEqual(candidate["lat"], 51.501009)
        self.assertEqual(candidate["lng"], -0.141588)
        self.assertEqual(candidate["source"], "Postcodes.io postcode lookup")
        self.assertEqual(candidate["dataMode"], "live-postcodes-io-postcode")
        self.assertEqual(candidate["postcodeKind"], "postcode")
        self.assertEqual(candidate["adminDistrict"], "Westminster")

    def test_enabled_outcode_lookup_adds_lower_confidence_candidate(self):
        response = {
            "status": 200,
            "result": {
                "outcode": "SW1A",
                "latitude": 51.501,
                "longitude": -0.141,
                "admin_district": ["Westminster"],
                "region": "London",
                "country": "England",
            },
        }

        with mock.patch.dict(os.environ, {"ENABLE_POSTCODES_IO_RESOLVER": "true"}, clear=False):
            with mock.patch("intake_coordinator.urllib.request.urlopen", return_value=FakeHttpResponse(response)) as urlopen:
                result = coordinate_intake({"message": "Survey outcode SW1A within 500m", "conversationId": "outcode-on"})

        candidate = result["intake"]["locationCandidate"]
        self.assertEqual(result["status"], "confirmation_required")
        self.assertIn("/outcodes/SW1A", urlopen.call_args.args[0].full_url)
        self.assertEqual(candidate["source"], "Postcodes.io outcode lookup")
        self.assertEqual(candidate["dataMode"], "live-postcodes-io-outcode")
        self.assertEqual(candidate["postcodeKind"], "outcode")
        self.assertEqual(candidate["confidence"], 0.66)

    def test_postcodes_io_failure_falls_back_to_text_candidate(self):
        with mock.patch.dict(os.environ, {"ENABLE_POSTCODES_IO_RESOLVER": "true"}, clear=False):
            with mock.patch("intake_coordinator.urllib.request.urlopen", side_effect=TimeoutError("timed out")):
                result = coordinate_intake({"message": "Survey SW1A 1AA within 500m", "conversationId": "postcode-fail"})

        candidate = result["intake"]["locationCandidate"]
        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(candidate["label"], "SW1A 1AA")
        self.assertNotIn("lat", candidate)


if __name__ == "__main__":
    unittest.main()
