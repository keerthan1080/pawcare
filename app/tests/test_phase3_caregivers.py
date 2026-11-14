import unittest
from fastapi.testclient import TestClient

from app.common.enums import UserRole
from app.database.connection import get_db_manager
from app.main import app
from app.modules.users.repository import UserRepository
from app.security.jwt import create_jwt_token
from app.security.passwords import hash_password


class Phase3CaregiversTestSuite(unittest.TestCase):
    """Unit and Integration tests for PawCare Phase 3 — Caregivers, Services, Availability & Verification."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)
        self.user_repo = UserRepository(self.db)

        # Register Caregiver 1
        cg1 = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "anita.sitter@pawcare.in",
                "password": "Password123",
                "full_name": "Anita Rao",
                "phone": "+919845012345",
                "role": "CAREGIVER",
            },
        ).json()
        self.cg1_headers = {"Authorization": f"Bearer {cg1['access_token']}"}

        # Register Pet Parent
        pp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "parent@pawcare.in",
                "password": "Password123",
                "full_name": "Keerthan Tenneti",
                "role": "PET_PARENT",
            },
        ).json()
        self.parent_headers = {"Authorization": f"Bearer {pp['access_token']}"}

        # Seed Admin User
        admin = self.user_repo.create_user(
            email="admin@pawcare.in",
            full_name="PawCare Admin",
            phone=None,
            password_hash=hash_password("AdminPass99"),
            role=UserRole.ADMIN.value,
        )
        admin_token = create_jwt_token(subject=admin.id, role=admin.role, token_type="access")
        self.admin_headers = {"Authorization": f"Bearer {admin_token}"}

    def _sample_caregiver_payload(self) -> dict:
        return {
            "bio": "Experienced Golden Retriever and Indie dog sitter in Whitefield with a secure fenced garden.",
            "years_of_experience": 6,
            "experience_summary": "Volunteered at animal shelter for 3 years; hosted 80+ boarding stays.",
            "city": "Bengaluru",
            "locality": "Whitefield",
            "latitude": 12.9698,
            "longitude": 77.7500,
            "service_radius_km": 8.0,
            "supported_species": ["DOG", "CAT"],
            "max_pet_weight_kg": 45.0,
            "special_capabilities": ["ORAL_MEDICATION", "SENIOR_PET_CARE", "FIRST_AID_CERTIFIED"],
            "boarding_details": {
                "home_type": "Independent House",
                "has_fenced_yard": True,
                "max_pets_hosted": 3,
                "is_smoke_free": True,
                "has_resident_pets": False,
                "notes": "24/7 supervision with shaded lawn area",
            },
            "services": [
                {
                    "service_type": "PET_BOARDING",
                    "price_inr": 850.0,
                    "price_unit": "PER_NIGHT",
                    "description": "Includes 2 walks per day and photo updates",
                },
                {
                    "service_type": "DOG_WALKING",
                    "price_inr": 300.0,
                    "price_unit": "PER_WALK",
                    "duration_minutes": 45,
                    "description": "45-minute harness walk",
                },
            ],
        }

    def test_01_list_5_initial_mvp_services(self) -> None:
        res = self.client.get("/api/v1/services")
        self.assertEqual(res.status_code, 200)
        services = res.json()
        self.assertEqual(len(services), 5)
        codes = {s["code"] for s in services}
        self.assertEqual(
            codes,
            {
                "PET_BOARDING",
                "IN_HOME_PET_SITTING",
                "DROP_IN_VISITS",
                "DOG_WALKING",
                "DAY_CARE",
            },
        )

    def test_02_create_caregiver_profile_and_enforce_role_and_rule5_badge(self) -> None:
        # PET_PARENT cannot create a caregiver profile
        forbidden = self.client.post(
            "/api/v1/caregivers/me",
            json=self._sample_caregiver_payload(),
            headers=self.parent_headers,
        )
        self.assertEqual(forbidden.status_code, 403)

        # CAREGIVER creates profile
        res = self.client.post(
            "/api/v1/caregivers/me",
            json=self._sample_caregiver_payload(),
            headers=self.cg1_headers,
        )
        self.assertEqual(res.status_code, 201)
        profile = res.json()
        self.assertEqual(profile["full_name"], "Anita Rao")
        self.assertEqual(profile["city"], "Bengaluru")
        self.assertEqual(profile["verification_status"], "PENDING")
        # Rule 5: Never display a Verified badge unless backend records VERIFIED
        self.assertFalse(profile["is_verified_badge"])
        self.assertEqual(len(profile["services"]), 2)

    def test_03_verification_submission_and_admin_only_approval_workflow(self) -> None:
        cg = self.client.post(
            "/api/v1/caregivers/me",
            json=self._sample_caregiver_payload(),
            headers=self.cg1_headers,
        ).json()
        cg_id = cg["id"]

        # Caregiver submits Identity & Background Check documents
        sub_res = self.client.post(
            "/api/v1/caregivers/me/verifications",
            json={
                "category": "IDENTITY",
                "document_reference": "verifications/anita/gov-id-001.pdf",
                "notes": "Government ID submitted",
            },
            headers=self.cg1_headers,
        )
        self.assertEqual(sub_res.status_code, 201)
        ver_id = sub_res.json()["id"]
        self.assertEqual(sub_res.json()["status"], "UNDER_REVIEW")

        # Profile status automatically moves from PENDING -> UNDER_REVIEW, still not verified
        me_after_sub = self.client.get("/api/v1/caregivers/me", headers=self.cg1_headers).json()
        self.assertEqual(me_after_sub["verification_status"], "UNDER_REVIEW")
        self.assertFalse(me_after_sub["is_verified_badge"])

        # Caregiver CANNOT approve their own verification status (403 INSUFFICIENT_PERMISSIONS)
        self_approve = self.client.patch(
            f"/api/v1/caregivers/{cg_id}/verification-status",
            json={"verification_status": "VERIFIED"},
            headers=self.cg1_headers,
        )
        self.assertEqual(self_approve.status_code, 403)

        # Admin reviews verification item and approves caregiver profile
        item_rev = self.client.patch(
            f"/api/v1/caregivers/{cg_id}/verifications/{ver_id}",
            json={"status": "VERIFIED", "review_notes": "Identity document verified"},
            headers=self.admin_headers,
        )
        self.assertEqual(item_rev.status_code, 200)
        self.assertEqual(item_rev.json()["status"], "VERIFIED")

        status_rev = self.client.patch(
            f"/api/v1/caregivers/{cg_id}/verification-status",
            json={"verification_status": "VERIFIED", "review_notes": "All checks passed"},
            headers=self.admin_headers,
        )
        self.assertEqual(status_rev.status_code, 200)
        self.assertEqual(status_rev.json()["verification_status"], "VERIFIED")
        self.assertTrue(status_rev.json()["is_verified_badge"])

    def test_04_availability_slot_creation_and_overlap_prevention(self) -> None:
        cg = self.client.post(
            "/api/v1/caregivers/me",
            json=self._sample_caregiver_payload(),
            headers=self.cg1_headers,
        ).json()
        cg_id = cg["id"]

        # Create valid availability window
        slot1 = self.client.post(
            "/api/v1/availability",
            json={
                "start_time": "2026-11-20T08:00:00Z",
                "end_time": "2026-11-22T18:00:00Z",
                "max_capacity": 2,
                "notes": "Weekend boarding window",
            },
            headers=self.cg1_headers,
        )
        self.assertEqual(slot1.status_code, 201)
        slot_id = slot1.json()["id"]
        self.assertEqual(slot1.json()["remaining_capacity"], 2)

        # Overlapping window for same caregiver must be rejected with 409 AVAILABILITY_OVERLAP
        overlap = self.client.post(
            "/api/v1/availability",
            json={
                "start_time": "2026-11-21T10:00:00Z",
                "end_time": "2026-11-23T10:00:00Z",
                "max_capacity": 1,
            },
            headers=self.cg1_headers,
        )
        self.assertEqual(overlap.status_code, 409)
        self.assertEqual(overlap.json()["code"], "AVAILABILITY_OVERLAP")

        # List caregiver's available slots
        slots_res = self.client.get(f"/api/v1/availability/caregiver/{cg_id}")
        self.assertEqual(slots_res.status_code, 200)
        self.assertEqual(len(slots_res.json()), 1)

        # Delete unbooked slot
        del_res = self.client.delete(f"/api/v1/availability/{slot_id}", headers=self.cg1_headers)
        self.assertEqual(del_res.status_code, 204)

    def test_05_search_and_filter_caregivers_by_city_service_and_verification(self) -> None:
        cg = self.client.post(
            "/api/v1/caregivers/me",
            json=self._sample_caregiver_payload(),
            headers=self.cg1_headers,
        ).json()
        cg_id = cg["id"]

        # Before admin verification, verified_only=true returns 0 results
        unverified_search = self.client.get("/api/v1/caregivers?city=Bengaluru&verified_only=true")
        self.assertEqual(unverified_search.status_code, 200)
        self.assertEqual(unverified_search.json()["total"], 0)

        # Approve caregiver
        self.client.patch(
            f"/api/v1/caregivers/{cg_id}/verification-status",
            json={"verification_status": "VERIFIED"},
            headers=self.admin_headers,
        )

        # Search by city, service_type, species, verified_only, and max_price_inr
        verified_search = self.client.get(
            "/api/v1/caregivers?city=Bengaluru&service_type=PET_BOARDING&species=DOG&verified_only=true&max_price_inr=1000"
        )
        self.assertEqual(verified_search.status_code, 200)
        self.assertEqual(verified_search.json()["total"], 1)
        self.assertTrue(verified_search.json()["items"][0]["is_verified_badge"])


if __name__ == "__main__":
    unittest.main()
