import unittest
from fastapi.testclient import TestClient

from app.database.connection import get_db_manager
from app.main import app


class WebAppDemoFlowTestSuite(unittest.TestCase):
    """Tests the /api/v1/demo/seed, /api/v1/demo/client-logs, and no-gateway demo booking flow."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)

    def test_01_seed_demo_workspace_and_complete_end_to_end_ui_booking_flow(self) -> None:
        # 1. Seed workspace via POST /api/v1/demo/seed
        seed_res = self.client.post("/api/v1/demo/seed")
        self.assertEqual(seed_res.status_code, 200)
        seed = seed_res.json()
        self.assertEqual(seed["status"], "seeded")
        self.assertEqual(seed["pet_parent"]["pet_name"], "Bruno")

        parent_headers = {"Authorization": f"Bearer {seed['pet_parent']['access_token']}"}
        cg_headers = {"Authorization": f"Bearer {seed['caregiver']['access_token']}"}
        pet_id = seed["pet_parent"]["pet_id"]

        # 2. Discover caregivers in Bengaluru
        cg_list = self.client.get("/api/v1/caregivers?city=Bengaluru&verified_only=true").json()
        self.assertGreaterEqual(cg_list["total"], 2)
        anita = [c for c in cg_list["items"] if c["full_name"] == "Anita Rao"][0]

        # 3. Create booking as Pet Parent
        book_res = self.client.post(
            "/api/v1/bookings",
            json={
                "caregiver_id": anita["id"],
                "pet_id": pet_id,
                "service_type": "PET_BOARDING",
                "start_time": "2026-11-20T09:00:00Z",
                "end_time": "2026-11-22T09:00:00Z",
                "special_instructions": "Follow Bruno schedule",
            },
            headers=parent_headers,
        )
        self.assertEqual(book_res.status_code, 201)
        booking_id = book_res.json()["id"]

        # 4. Complete demo checkout without payment gateway (POST /api/v1/bookings/{id}/demo-pay)
        pay_res = self.client.post(f"/api/v1/bookings/{booking_id}/demo-pay", headers=parent_headers)
        self.assertEqual(pay_res.status_code, 200)
        self.assertEqual(pay_res.json()["status"], "PAID")

        # 5. Caregiver accepts booking (PAID -> CONFIRMED)
        conf_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "CONFIRMED"},
            headers=cg_headers,
        )
        self.assertEqual(conf_res.status_code, 200)
        self.assertEqual(conf_res.json()["status"], "CONFIRMED")

    def test_02_client_error_telemetry_logged_for_developers_without_exposing_to_users(self) -> None:
        log_res = self.client.post(
            "/api/v1/demo/client-logs",
            json={
                "trace_id": "trc-99887766",
                "component": "Auth",
                "operation": "loginNetworkFailure",
                "error_message": "TypeError: Failed to fetch",
                "path": "/pawCare/login",
            },
        )
        self.assertEqual(log_res.status_code, 202)
        self.assertEqual(log_res.json()["status"], "logged")
        self.assertEqual(log_res.json()["trace_id"], "trc-99887766")


if __name__ == "__main__":
    unittest.main()
