import unittest
from fastapi.testclient import TestClient

from app.database.connection import get_db_manager
from app.main import app


class AdminBookingReviewAndWhatsAppWorkflowTestSuite(unittest.TestCase):
    """Tests Admin booking visibility, WhatsApp alerts, Pet media review payment confirmation, Caretaker assignment, and strict Role Blocking."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)

    def test_01_booking_triggers_whatsapp_alert_and_admin_media_review_and_caretaker_assignment(self) -> None:
        seed = self.client.post("/api/v1/demo/seed").json()
        parent_headers = {"Authorization": f"Bearer {seed['pet_parent']['access_token']}"}
        admin_headers = {"Authorization": f"Bearer {seed['admin']['access_token']}"}
        pet_id = seed["pet_parent"]["pet_id"]

        # Verify Bruno's profile contains the uploaded videos & photos
        pet_res = self.client.get(f"/api/v1/pets/{pet_id}", headers=parent_headers).json()
        self.assertEqual(len(pet_res["media_gallery"]), 4)

        # Pet Owner uploads an additional video to Bruno's profile
        add_vid = self.client.post(
            f"/api/v1/pets/{pet_id}/media",
            json={
                "media_type": "VIDEO",
                "title": "Bruno Evening Fetch Video",
                "url": "https://cdn.pawcare.local/pawcare-media/pets/bruno/evening-fetch.mp4",
                "duration_seconds": 28,
                "notes": "Shows energy level",
            },
            headers=parent_headers,
        )
        self.assertEqual(add_vid.status_code, 201)

        # Pet Parent creates a booking
        cgs = self.client.get("/api/v1/caregivers?city=Bengaluru&verified_only=true").json()["items"]
        anita = [c for c in cgs if c["full_name"] == "Anita Rao"][0]
        vikram = [c for c in cgs if c["full_name"] == "Vikram Nair"][0]

        book_res = self.client.post(
            "/api/v1/bookings",
            json={
                "caregiver_id": anita["id"],
                "pet_id": pet_id,
                "service_type": "PET_BOARDING",
                "start_time": "2026-11-24T09:00:00Z",
                "end_time": "2026-11-26T09:00:00Z",
                "special_instructions": "Please review Bruno's videos",
            },
            headers=parent_headers,
        )
        self.assertEqual(book_res.status_code, 201)
        booking_id = book_res.json()["id"]

        # STRICT ROLE BLOCKING: Regular User (PET_PARENT) is blocked (403) from Admin endpoints
        user_try_notifs = self.client.get("/api/v1/notifications", headers=parent_headers)
        self.assertEqual(user_try_notifs.status_code, 403)

        user_try_confirm_pay = self.client.patch(
            f"/api/v1/bookings/{booking_id}/admin-confirm-payment",
            json={"media_reviewed": True},
            headers=parent_headers,
        )
        self.assertEqual(user_try_confirm_pay.status_code, 403)

        user_try_assign_cg = self.client.patch(
            f"/api/v1/bookings/{booking_id}/admin-assign-caregiver",
            json={"caregiver_id": vikram["id"]},
            headers=parent_headers,
        )
        self.assertEqual(user_try_assign_cg.status_code, 403)

        # Admin can view WhatsApp notifications and confirm payment after media review
        notifs = self.client.get(f"/api/v1/notifications?booking_id={booking_id}", headers=admin_headers).json()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["event_type"], "NEW_BOOKING_ADMIN_ALERT")

        confirm_pay = self.client.patch(
            f"/api/v1/bookings/{booking_id}/admin-confirm-payment",
            json={
                "media_reviewed": True,
                "review_notes": "Inspected all 3 videos and 2 photos of Bruno; payment verified.",
            },
            headers=admin_headers,
        )
        self.assertEqual(confirm_pay.status_code, 200)
        self.assertEqual(confirm_pay.json()["status"], "PAID")

        # Admin assigns verified Caretaker (Vikram Nair) after review -> transitions to CONFIRMED
        assign_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/admin-assign-caregiver",
            json={
                "caregiver_id": vikram["id"],
                "assignment_notes": "Assigned Vikram Nair in Kadugodi after reviewing Bruno's temperament videos.",
            },
            headers=admin_headers,
        )
        self.assertEqual(assign_res.status_code, 200)
        self.assertEqual(assign_res.json()["status"], "CONFIRMED")
        self.assertEqual(assign_res.json()["caregiver_name"], "Vikram Nair")


if __name__ == "__main__":
    unittest.main()
