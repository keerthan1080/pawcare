import base64
import unittest
from fastapi.testclient import TestClient

from app.database.connection import get_db_manager
from app.main import app
from app.modules.pets.repository import PetRepository


class Phase2PetsTestSuite(unittest.TestCase):
    """Unit and Integration tests for PawCare Phase 2 — Pets, Emergency Info & Object Storage."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)
        self.pet_repo = PetRepository(self.db)

        # Register Pet Parent 1 (Owner of Bruno)
        r1 = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "parent.bruno@pawcare.in",
                "password": "Password123",
                "full_name": "Keerthan Tenneti",
                "phone": "+919876543210",
                "role": "PET_PARENT",
            },
        ).json()
        self.parent1_token = r1["access_token"]
        self.parent1_headers = {"Authorization": f"Bearer {self.parent1_token}"}
        self.parent1_id = r1["user"]["id"]

        # Register Pet Parent 2 (Another unrelated pet parent)
        r2 = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "other.parent@pawcare.in",
                "password": "Password123",
                "full_name": "Other Parent",
                "role": "PET_PARENT",
            },
        ).json()
        self.parent2_headers = {"Authorization": f"Bearer {r2['access_token']}"}

        # Register Caregiver
        rc = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "caregiver.anita@pawcare.in",
                "password": "Password123",
                "full_name": "Anita Sitter",
                "role": "CAREGIVER",
            },
        ).json()
        self.caregiver_id = rc["user"]["id"]
        self.caregiver_headers = {"Authorization": f"Bearer {rc['access_token']}"}

    def _create_bruno_payload(self) -> dict:
        return {
            "name": "Bruno",
            "species": "DOG",
            "breed": "Golden Retriever",
            "gender": "MALE",
            "date_of_birth": "2023-05-15",
            "weight_kg": 28.5,
            "personality": "Friendly, loves fetch, calm indoors",
            "feeding_instructions": "Freddy Pedigree dry kibble mixed with warm water",
            "feeding_schedule": [
                {"time": "07:30", "meal": "Breakfast", "portion": "1.5 cups", "notes": "Add joint supplement"},
                {"time": "19:00", "meal": "Dinner", "portion": "1.5 cups", "notes": None},
            ],
            "walking_schedule": [
                {"time": "09:00", "duration_minutes": 30, "notes": "Use harness"},
                {"time": "20:00", "duration_minutes": 30, "notes": "Evening stroll"},
            ],
            "medication_instructions": "1 chewable vitamin at 08:00 AM",
            "allergies": "Chicken protein",
            "behaviour_notes": "Friendly with other dogs; dislikes loud fireworks",
            "special_requirements": "Keep fresh water bowl filled at all times",
            "emergency_contacts": [
                {
                    "name": "Baskaran",
                    "relationship": "Colleague / Neighbor",
                    "phone": "+919811122233",
                    "email": "baskaran@example.com",
                    "is_primary": True,
                }
            ],
            "preferred_veterinarian": {
                "clinic_name": "Crown Vet Clinic",
                "vet_name": "Dr. Sharma",
                "phone": "+918044556677",
                "address": "Whitefield Main Rd, Bengaluru",
                "notes": "24x7 emergency unit available",
            },
            "medical_records": [
                {
                    "record_type": "VACCINATION",
                    "title": "Anti-Rabies Annual Booster",
                    "administered_date": "2026-04-10",
                    "expiry_date": "2027-04-10",
                    "provider_name": "Crown Vet Clinic",
                }
            ],
        }

    def test_01_create_and_retrieve_complete_pet_profile(self) -> None:
        res = self.client.post(
            "/api/v1/pets",
            json=self._create_bruno_payload(),
            headers=self.parent1_headers,
        )
        self.assertEqual(res.status_code, 201)
        pet = res.json()
        self.assertEqual(pet["name"], "Bruno")
        self.assertEqual(pet["species"], "DOG")
        self.assertIsNotNone(pet["age_years"])
        self.assertEqual(len(pet["feeding_schedule"]), 2)
        self.assertEqual(len(pet["walking_schedule"]), 2)
        self.assertEqual(len(pet["emergency_contacts"]), 1)
        self.assertEqual(pet["preferred_veterinarian"]["clinic_name"], "Crown Vet Clinic")
        self.assertEqual(len(pet["medical_records"]), 1)

        # List pets for Parent 1
        list_res = self.client.get("/api/v1/pets?species=DOG", headers=self.parent1_headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.json()["total"], 1)

    def test_02_privacy_isolation_between_pet_parents_and_unauthorized_caregivers(self) -> None:
        pet_id = self.client.post(
            "/api/v1/pets",
            json=self._create_bruno_payload(),
            headers=self.parent1_headers,
        ).json()["id"]

        # Unrelated Pet Parent 2 must NOT see Bruno (Rule 4 & Rule 8)
        forbidden_parent = self.client.get(f"/api/v1/pets/{pet_id}", headers=self.parent2_headers)
        self.assertEqual(forbidden_parent.status_code, 403)
        self.assertEqual(forbidden_parent.json()["code"], "PET_ACCESS_FORBIDDEN")

        # Unauthorized Caregiver (without active booking) must NOT see Bruno
        forbidden_cg = self.client.get(f"/api/v1/pets/{pet_id}", headers=self.caregiver_headers)
        self.assertEqual(forbidden_cg.status_code, 403)

        # Grant booking access to Caregiver and verify read access works while write access remains forbidden
        self.pet_repo.grant_caregiver_pet_access(
            pet_id=pet_id,
            caregiver_user_id=self.caregiver_id,
            booking_id="booking-test-001",
        )
        allowed_cg = self.client.get(f"/api/v1/pets/{pet_id}", headers=self.caregiver_headers)
        self.assertEqual(allowed_cg.status_code, 200)
        self.assertEqual(allowed_cg.json()["name"], "Bruno")

        # Caregiver still cannot modify Bruno's profile
        cg_patch = self.client.patch(
            f"/api/v1/pets/{pet_id}",
            json={"weight_kg": 30.0},
            headers=self.caregiver_headers,
        )
        self.assertEqual(cg_patch.status_code, 403)

    def test_03_emergency_information_workflow_and_medical_disclaimer(self) -> None:
        pet_id = self.client.post(
            "/api/v1/pets",
            json=self._create_bruno_payload(),
            headers=self.parent1_headers,
        ).json()["id"]

        # Authorize caregiver for active booking
        self.pet_repo.grant_caregiver_pet_access(
            pet_id=pet_id,
            caregiver_user_id=self.caregiver_id,
            booking_id="booking-test-001",
        )

        em_res = self.client.get(f"/api/v1/pets/{pet_id}/emergency-info", headers=self.caregiver_headers)
        self.assertEqual(em_res.status_code, 200)
        em = em_res.json()
        self.assertEqual(em["pet_name"], "Bruno")
        self.assertEqual(em["pet_parent"]["full_name"], "Keerthan Tenneti")
        self.assertEqual(em["pet_parent"]["phone"], "+919876543210")
        self.assertEqual(em["emergency_contacts"][0]["name"], "Baskaran")
        self.assertEqual(em["preferred_veterinarian"]["clinic_name"], "Crown Vet Clinic")
        self.assertIn("does not diagnose medical conditions", em["medical_disclaimer"])

    def test_04_pet_photo_upload_validation_and_object_storage(self) -> None:
        pet_id = self.client.post(
            "/api/v1/pets",
            json=self._create_bruno_payload(),
            headers=self.parent1_headers,
        ).json()["id"]

        # Valid PNG magic header bytes
        valid_png_bytes = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001")
        b64_png = base64.b64encode(valid_png_bytes).decode("ascii")

        upload_res = self.client.post(
            f"/api/v1/pets/{pet_id}/photo",
            json={"content_type": "image/png", "data_base64": b64_png},
            headers=self.parent1_headers,
        )
        self.assertEqual(upload_res.status_code, 200)
        up_body = upload_res.json()
        self.assertTrue(up_body["photo_url"].startswith("https://cdn.pawcare.local/pawcare-media/pets/"))
        self.assertTrue(up_body["object_key"].endswith(".png"))

        # Spoofed/invalid binary signature must be rejected with 400 INVALID_IMAGE_SIGNATURE
        fake_png = base64.b64encode(b"MZ-executable-disguised-as-png").decode("ascii")
        bad_res = self.client.post(
            f"/api/v1/pets/{pet_id}/photo",
            json={"content_type": "image/png", "data_base64": fake_png},
            headers=self.parent1_headers,
        )
        self.assertEqual(bad_res.status_code, 400)
        self.assertEqual(bad_res.json()["code"], "INVALID_IMAGE_SIGNATURE")

    def test_05_update_medical_records_and_soft_delete_pet(self) -> None:
        pet_id = self.client.post(
            "/api/v1/pets",
            json=self._create_bruno_payload(),
            headers=self.parent1_headers,
        ).json()["id"]

        # Add a second medical record
        med_res = self.client.post(
            f"/api/v1/pets/{pet_id}/medical-records",
            json={
                "record_type": "CHECKUP",
                "title": "Semi-Annual Wellness Check",
                "administered_date": "2026-10-01",
                "provider_name": "Crown Vet Clinic",
            },
            headers=self.parent1_headers,
        )
        self.assertEqual(med_res.status_code, 201)

        all_meds = self.client.get(
            f"/api/v1/pets/{pet_id}/medical-records",
            headers=self.parent1_headers,
        )
        self.assertEqual(len(all_meds.json()), 2)

        # Soft-deactivate pet profile
        del_res = self.client.delete(f"/api/v1/pets/{pet_id}", headers=self.parent1_headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(del_res.json()["is_active"])

        # Subsequent GET returns 404 PET_NOT_FOUND
        after_del = self.client.get(f"/api/v1/pets/{pet_id}", headers=self.parent1_headers)
        self.assertEqual(after_del.status_code, 404)
        self.assertEqual(after_del.json()["code"], "PET_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
