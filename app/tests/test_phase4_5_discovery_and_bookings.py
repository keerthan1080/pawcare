from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient

from app.common.enums import UserRole
from app.database.connection import get_db_manager
from app.main import app
from app.modules.users.repository import UserRepository
from app.security.jwt import create_jwt_token
from app.security.passwords import hash_password


class Phase4And5DiscoveryBookingsTestSuite(unittest.TestCase):
    """Unit and Integration tests for PawCare Phase 4 (Discovery) and Phase 5 (Booking & State Machine)."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)
        self.user_repo = UserRepository(self.db)

        # Seed Admin
        admin = self.user_repo.create_user(
            email="admin@pawcare.in",
            full_name="Platform Admin",
            phone=None,
            password_hash=hash_password("AdminPass99"),
            role=UserRole.ADMIN.value,
        )
        self.admin_headers = {
            "Authorization": f"Bearer {create_jwt_token(subject=admin.id, role=admin.role, token_type='access')}"
        }

        # Register Caregiver (Whitefield, Bengaluru) with max capacity = 1 for single-slot concurrency test
        cg_reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "anita.sitter@pawcare.in",
                "password": "Password123",
                "full_name": "Anita Rao",
                "phone": "+919845011122",
                "role": "CAREGIVER",
            },
        ).json()
        self.cg_headers = {"Authorization": f"Bearer {cg_reg['access_token']}"}

        cg_profile = self.client.post(
            "/api/v1/caregivers/me",
            json={
                "bio": "Trusted Golden Retriever boarding host in Whitefield.",
                "years_of_experience": 5,
                "city": "Bengaluru",
                "locality": "Whitefield",
                "latitude": 12.9698,
                "longitude": 77.7500,
                "service_radius_km": 10.0,
                "supported_species": ["DOG"],
                "max_pet_weight_kg": 35.0,
                "special_capabilities": ["ORAL_MEDICATION"],
                "services": [
                    {
                        "service_type": "PET_BOARDING",
                        "price_inr": 1000.0,
                        "price_unit": "PER_NIGHT",
                        "description": "Overnight boarding",
                    }
                ],
            },
            headers=self.cg_headers,
        ).json()
        self.caregiver_id = cg_profile["id"]

        # Admin verifies Caregiver (Rule 5)
        self.client.patch(
            f"/api/v1/caregivers/{self.caregiver_id}/verification-status",
            json={"verification_status": "VERIFIED"},
            headers=self.admin_headers,
        )

        # Caregiver opens availability slot (2026-11-20 to 2026-11-22, max_capacity = 1)
        slot_res = self.client.post(
            "/api/v1/availability",
            json={
                "start_time": "2026-11-20T08:00:00Z",
                "end_time": "2026-11-22T08:00:00Z",
                "max_capacity": 1,
                "notes": "Single-dog exclusive boarding slot",
            },
            headers=self.cg_headers,
        )
        self.slot_id = slot_res.json()["id"]

        # Register Pet Parent 1 & create Bruno (28.5 kg DOG)
        pp1 = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "keerthan@pawcare.in",
                "password": "Password123",
                "full_name": "Keerthan Tenneti",
                "role": "PET_PARENT",
            },
        ).json()
        self.parent1_headers = {"Authorization": f"Bearer {pp1['access_token']}"}
        self.pet1_id = self.client.post(
            "/api/v1/pets",
            json={"name": "Bruno", "species": "DOG", "weight_kg": 28.5},
            headers=self.parent1_headers,
        ).json()["id"]

        # Register Pet Parent 2 & create Max (24.0 kg DOG)
        pp2 = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "parent2@pawcare.in",
                "password": "Password123",
                "full_name": "Second Parent",
                "role": "PET_PARENT",
            },
        ).json()
        self.parent2_headers = {"Authorization": f"Bearer {pp2['access_token']}"}
        self.pet2_id = self.client.post(
            "/api/v1/pets",
            json={"name": "Max", "species": "DOG", "weight_kg": 24.0},
            headers=self.parent2_headers,
        ).json()["id"]

    def test_01_phase4_discovery_availability_distance_and_quote(self) -> None:
        # 1. Search with Kadugodi/Whitefield coordinates (within 10 km radius) and matching availability window
        res = self.client.get(
            "/api/v1/caregivers"
            "?city=Bengaluru"
            "&service_type=PET_BOARDING"
            "&species=DOG"
            "&pet_weight_kg=28.5"
            "&verified_only=true"
            "&start_time=2026-11-20T10:00:00Z"
            "&end_time=2026-11-22T08:00:00Z"
            "&latitude=12.9850&longitude=77.7600"
            "&sort_by=distance_asc"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertIsNotNone(data["items"][0]["distance_km"])
        self.assertLess(data["items"][0]["distance_km"], 5.0)

        # 2. Search with pet_weight_kg exceeding caregiver's 35 kg limit returns 0
        heavy_res = self.client.get("/api/v1/caregivers?city=Bengaluru&pet_weight_kg=50.0")
        self.assertEqual(heavy_res.json()["total"], 0)

        # 3. Get server-calculated quote for 2 nights (2026-11-20T08:00Z -> 2026-11-22T08:00Z)
        quote_res = self.client.get(
            f"/api/v1/caregivers/{self.caregiver_id}/quote"
            "?service_type=PET_BOARDING"
            "&start_time=2026-11-20T08:00:00Z"
            "&end_time=2026-11-22T08:00:00Z"
        )
        self.assertEqual(quote_res.status_code, 200)
        q = quote_res.json()
        self.assertTrue(q["is_available"])
        self.assertEqual(q["units_count"], 2)
        self.assertEqual(q["subtotal_inr"], 2000.0)
        self.assertEqual(q["platform_commission_inr"], 300.0)
        self.assertEqual(q["total_price_inr"], 2000.0)

    def test_02_rule1_double_booking_prevention_under_concurrency(self) -> None:
        # Both Parent 1 and Parent 2 attempt to book the exact same caregiver & time window concurrently
        def attempt_booking(headers: dict, pet_id: str):
            return self.client.post(
                "/api/v1/bookings",
                json={
                    "caregiver_id": self.caregiver_id,
                    "pet_id": pet_id,
                    "service_type": "PET_BOARDING",
                    "start_time": "2026-11-20T08:00:00Z",
                    "end_time": "2026-11-22T08:00:00Z",
                    "special_instructions": "Please follow Bruno/Max care schedule",
                },
                headers=headers,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(attempt_booking, self.parent1_headers, self.pet1_id)
            f2 = executor.submit(attempt_booking, self.parent2_headers, self.pet2_id)
            r1, r2 = f1.result(), f2.result()

        status_codes = sorted([r1.status_code, r2.status_code])
        # Strictly one succeeds (201) and the other is rejected with 409 CAREGIVER_UNAVAILABLE
        self.assertEqual(status_codes, [201, 409])
        failed_res = r1 if r1.status_code == 409 else r2
        self.assertEqual(failed_res.json()["code"], "CAREGIVER_UNAVAILABLE")

    def test_03_rule6_booking_state_machine_and_invalid_transition_rejection(self) -> None:
        # 1. Parent 1 creates booking (starts in PAYMENT_PENDING)
        create_res = self.client.post(
            "/api/v1/bookings",
            json={
                "caregiver_id": self.caregiver_id,
                "pet_id": self.pet1_id,
                "service_type": "PET_BOARDING",
                "start_time": "2026-11-20T08:00:00Z",
                "end_time": "2026-11-22T08:00:00Z",
            },
            headers=self.parent1_headers,
        )
        self.assertEqual(create_res.status_code, 201)
        booking = create_res.json()
        booking_id = booking["id"]
        self.assertEqual(booking["status"], "PAYMENT_PENDING")
        self.assertEqual(booking["total_price_inr"], 2000.0)
        self.assertEqual(booking["caregiver_payout_inr"], 1700.0)

        # 2. Invalid jump directly from PAYMENT_PENDING -> COMPLETED must fail (Rule 6)
        invalid_jump = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "COMPLETED"},
            headers=self.cg_headers,
        )
        self.assertEqual(invalid_jump.status_code, 400)
        self.assertEqual(invalid_jump.json()["code"], "INVALID_BOOKING_STATE_TRANSITION")

        # 3. Caregiver cannot confirm before payment is verified (PAYMENT_PENDING -> CONFIRMED blocked)
        early_confirm = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "CONFIRMED"},
            headers=self.cg_headers,
        )
        self.assertEqual(early_confirm.status_code, 400)
        self.assertEqual(early_confirm.json()["code"], "PAYMENT_REQUIRED_BEFORE_CONFIRMATION")

        # 4. Server/Admin marks PAYMENT_PENDING -> PAID
        paid_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "PAID", "reason": "Payment verified server-side"},
            headers=self.admin_headers,
        )
        self.assertEqual(paid_res.status_code, 200)
        self.assertEqual(paid_res.json()["status"], "PAID")

        # 5. Caregiver confirms PAID -> CONFIRMED
        conf_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "CONFIRMED"},
            headers=self.cg_headers,
        )
        self.assertEqual(conf_res.status_code, 200)
        self.assertEqual(conf_res.json()["status"], "CONFIRMED")

        # 6. Caregiver starts care CONFIRMED -> IN_PROGRESS
        prog_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "IN_PROGRESS"},
            headers=self.cg_headers,
        )
        self.assertEqual(prog_res.status_code, 200)
        self.assertEqual(prog_res.json()["status"], "IN_PROGRESS")

        # 7. Caregiver completes care IN_PROGRESS -> COMPLETED
        comp_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "COMPLETED"},
            headers=self.cg_headers,
        )
        self.assertEqual(comp_res.status_code, 200)
        self.assertEqual(comp_res.json()["status"], "COMPLETED")

    def test_04_cancellation_releases_capacity_and_revokes_caregiver_pet_access(self) -> None:
        # 1. Parent 1 books the slot
        booking_id = self.client.post(
            "/api/v1/bookings",
            json={
                "caregiver_id": self.caregiver_id,
                "pet_id": self.pet1_id,
                "service_type": "PET_BOARDING",
                "start_time": "2026-11-20T08:00:00Z",
                "end_time": "2026-11-22T08:00:00Z",
            },
            headers=self.parent1_headers,
        ).json()["id"]

        # Caregiver can view Bruno's profile while booking is active
        cg_view = self.client.get(f"/api/v1/pets/{self.pet1_id}", headers=self.cg_headers)
        self.assertEqual(cg_view.status_code, 200)

        # 2. Parent 1 cancels the booking
        cancel_res = self.client.patch(
            f"/api/v1/bookings/{booking_id}/status",
            json={"target_status": "CANCELLED", "reason": "Trip postponed"},
            headers=self.parent1_headers,
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["status"], "CANCELLED")

        # Caregiver's pet access is automatically revoked upon cancellation
        cg_view_after = self.client.get(f"/api/v1/pets/{self.pet1_id}", headers=self.cg_headers)
        self.assertEqual(cg_view_after.status_code, 403)

        # 3. Parent 2 can now book the freed slot!
        rebook_res = self.client.post(
            "/api/v1/bookings",
            json={
                "caregiver_id": self.caregiver_id,
                "pet_id": self.pet2_id,
                "service_type": "PET_BOARDING",
                "start_time": "2026-11-20T08:00:00Z",
                "end_time": "2026-11-22T08:00:00Z",
            },
            headers=self.parent2_headers,
        )
        self.assertEqual(rebook_res.status_code, 201)


if __name__ == "__main__":
    unittest.main()
