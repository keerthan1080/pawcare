import unittest
from fastapi.testclient import TestClient

from app.common.enums import UserRole
from app.database.connection import get_db_manager
from app.main import app
from app.modules.users.repository import UserRepository
from app.security.jwt import create_jwt_token
from app.security.passwords import hash_password, verify_password


class Phase1FoundationTestSuite(unittest.TestCase):
    """Unit and Integration tests for PawCare Phase 1 Foundation."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)
        self.repo = UserRepository(self.db)

    def test_01_health_check_and_correlation_id_header(self) -> None:
        response = self.client.get(
            "/api/v1/health",
            headers={"X-Correlation-ID": "corr-test-12345"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Correlation-ID"), "corr-test-12345")
        body = response.json()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["service"], "PawCare")

    def test_02_password_hashing_and_verification(self) -> None:
        hashed = hash_password("BrunoCare2026")
        self.assertTrue(verify_password("BrunoCare2026", hashed))
        self.assertFalse(verify_password("WrongPassword1", hashed))
        with self.assertRaises(ValueError):
            hash_password("short1")

    def test_03_register_pet_parent_and_audit_log_created(self) -> None:
        payload = {
            "email": "Keerthan@Example.com",
            "password": "Password123",
            "full_name": "Keerthan Tenneti",
            "phone": "+919876543210",
            "role": "PET_PARENT",
        }
        response = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["user"]["email"], "keerthan@example.com")
        self.assertEqual(data["user"]["role"], "PET_PARENT")

        logs = self.repo.list_audit_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].action, "USER_REGISTERED")
        self.assertEqual(logs[0].actor_user_id, data["user"]["id"])

    def test_04_duplicate_email_registration_returns_standardized_conflict_error(self) -> None:
        payload = {
            "email": "parent@pawcare.in",
            "password": "Password123",
            "full_name": "Parent One",
            "role": "PET_PARENT",
        }
        first = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(first.status_code, 201)

        second = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(second.status_code, 409)
        err = second.json()
        self.assertEqual(err["status"], 409)
        self.assertEqual(err["code"], "EMAIL_ALREADY_REGISTERED")
        self.assertEqual(err["path"], "/api/v1/auth/register")
        self.assertIn("timestamp", err)

    def test_05_public_admin_self_registration_is_blocked(self) -> None:
        payload = {
            "email": "attacker@pawcare.in",
            "password": "Password123",
            "full_name": "Malicious Actor",
            "role": "ADMIN",
        }
        response = self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(response.status_code, 422)
        err = response.json()
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_06_login_and_refresh_token_workflow(self) -> None:
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "sitter@pawcare.in",
                "password": "SitterPass99",
                "full_name": "Anita Rao",
                "role": "CAREGIVER",
            },
        )
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"email": "sitter@pawcare.in", "password": "SitterPass99"},
        )
        self.assertEqual(login_res.status_code, 200)
        tokens = login_res.json()
        self.assertEqual(tokens["user"]["role"], "CAREGIVER")

        refresh_res = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refresh_res.status_code, 200)
        self.assertIn("access_token", refresh_res.json())

        # Using access token on refresh endpoint must fail with INVALID_TOKEN_TYPE
        bad_refresh = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        self.assertEqual(bad_refresh.status_code, 401)
        self.assertEqual(bad_refresh.json()["code"], "INVALID_TOKEN_TYPE")

    def test_07_profile_get_and_update_requires_authentication(self) -> None:
        unauth = self.client.get("/api/v1/users/me")
        self.assertEqual(unauth.status_code, 401)
        self.assertEqual(unauth.json()["code"], "AUTHENTICATION_REQUIRED")

        reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "bruno.parent@pawcare.in",
                "password": "Password123",
                "full_name": "Bruno Parent",
                "role": "PET_PARENT",
            },
        ).json()
        headers = {"Authorization": f"Bearer {reg['access_token']}"}

        me_res = self.client.get("/api/v1/users/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["full_name"], "Bruno Parent")

        patch_res = self.client.patch(
            "/api/v1/users/me",
            json={"full_name": "Bruno Senior Parent", "phone": "+919988776655"},
            headers=headers,
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["full_name"], "Bruno Senior Parent")
        self.assertEqual(patch_res.json()["phone"], "+919988776655")

    def test_08_rbac_enforcement_and_admin_user_deactivation(self) -> None:
        # Create normal PET_PARENT
        parent_reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "user1@pawcare.in",
                "password": "Password123",
                "full_name": "User One",
                "role": "PET_PARENT",
            },
        ).json()
        parent_headers = {"Authorization": f"Bearer {parent_reg['access_token']}"}

        # PET_PARENT must be forbidden from listing all users
        forbidden_res = self.client.get("/api/v1/users", headers=parent_headers)
        self.assertEqual(forbidden_res.status_code, 403)
        self.assertEqual(forbidden_res.json()["code"], "INSUFFICIENT_PERMISSIONS")

        # Seed an ADMIN account via repository (since public ADMIN signup is disabled)
        admin_record = self.repo.create_user(
            email="admin@pawcare.in",
            full_name="Platform Admin",
            phone=None,
            password_hash=hash_password("AdminSecret99"),
            role=UserRole.ADMIN.value,
        )
        admin_token = create_jwt_token(subject=admin_record.id, role=admin_record.role, token_type="access")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # ADMIN can list users
        list_res = self.client.get("/api/v1/users?page=1&size=10", headers=admin_headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(list_res.json()["total"], 2)

        # ADMIN deactivates User One
        target_id = parent_reg["user"]["id"]
        deact_res = self.client.patch(
            f"/api/v1/users/{target_id}/status",
            json={"is_active": False},
            headers=admin_headers,
        )
        self.assertEqual(deact_res.status_code, 200)
        self.assertFalse(deact_res.json()["is_active"])

        # Deactivated user's existing JWT is immediately rejected
        blocked_me = self.client.get("/api/v1/users/me", headers=parent_headers)
        self.assertEqual(blocked_me.status_code, 403)
        self.assertEqual(blocked_me.json()["code"], "ACCOUNT_DEACTIVATED")


if __name__ == "__main__":
    unittest.main()
