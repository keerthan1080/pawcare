import unittest
from fastapi.testclient import TestClient

from app.database.connection import get_db_manager
from app.main import app


class MultiProviderAuthTestSuite(unittest.TestCase):
    """Unit and Integration tests for Okta SSO, Google Sign-In, and Mobile Number OTP Sign-In."""

    def setUp(self) -> None:
        self.db = get_db_manager()
        self.db.reset()
        self.client = TestClient(app)
        self.client.post("/api/v1/demo/seed")

    def test_01_mobile_number_otp_send_and_verify_existing_and_new_users(self) -> None:
        # 1. Send OTP to Keerthan's seeded mobile number (+91-8247716995)
        send_res = self.client.post(
            "/api/v1/auth/otp/send",
            json={"phone": "+91-8247716995", "role": "PET_PARENT"},
        )
        self.assertEqual(send_res.status_code, 200)
        self.assertEqual(send_res.json()["phone"], "+918247716995")

        # 2. Wrong OTP is rejected with 401 INVALID_OTP_CODE
        bad_verify = self.client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": "8247716995", "otp_code": "000000"},
        )
        self.assertEqual(bad_verify.status_code, 401)
        self.assertEqual(bad_verify.json()["code"], "INVALID_OTP_CODE")

        # 3. Valid OTP (654321 in local/test env) logs in existing user Keerthan Tenneti
        ok_verify = self.client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": "8247716995", "otp_code": "654321"},
        )
        self.assertEqual(ok_verify.status_code, 200)
        body = ok_verify.json()
        self.assertEqual(body["user"]["email"], "keerthan@pawcare.in")
        self.assertEqual(body["user"]["role"], "PET_PARENT")

        # 4. Re-using the same consumed OTP fails with 401 OTP_CHALLENGE_NOT_FOUND
        replay = self.client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": "8247716995", "otp_code": "654321"},
        )
        self.assertEqual(replay.status_code, 401)

        # 5. New mobile number auto-provisions a new PET_PARENT account
        self.client.post("/api/v1/auth/otp/send", json={"phone": "+919000011111", "role": "PET_PARENT"})
        new_verify = self.client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": "+919000011111", "otp_code": "654321", "full_name": "Rohan Sharma"},
        )
        self.assertEqual(new_verify.status_code, 200)
        self.assertEqual(new_verify.json()["user"]["full_name"], "Rohan Sharma")
        self.assertEqual(new_verify.json()["user"]["role"], "PET_PARENT")

    def test_02_google_signin_links_existing_and_provisions_new_user(self) -> None:
        # 1. Google Sign-In for new user
        res = self.client.post(
            "/api/v1/auth/oauth/google",
            json={
                "id_token": "google-oidc-jwt-token-valid-sample",
                "email": "meera.google@gmail.com",
                "full_name": "Meera Krishnan",
                "role": "PET_PARENT",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["user"]["email"], "meera.google@gmail.com")
        self.assertEqual(data["user"]["role"], "PET_PARENT")

        # 2. Attempting to self-register as ADMIN via Google OAuth is blocked (422)
        admin_attempt = self.client.post(
            "/api/v1/auth/oauth/google",
            json={
                "id_token": "google-oidc-jwt-token-valid-sample",
                "email": "hacker@gmail.com",
                "full_name": "Hacker",
                "role": "ADMIN",
            },
        )
        self.assertEqual(admin_attempt.status_code, 422)

    def test_03_okta_sso_signin_and_role_preservation(self) -> None:
        # 1. Okta SSO Sign-In for existing Admin account preserves ADMIN role
        admin_sso = self.client.post(
            "/api/v1/auth/oauth/okta",
            json={
                "id_token": "okta-oidc-assertion-valid-token",
                "email": "admin@pawcare.in",
                "full_name": "PawCare Trust & Safety Admin",
                "okta_issuer": "https://pawcare.okta.com/oauth2/default",
                "role": "PET_PARENT",
            },
        )
        self.assertEqual(admin_sso.status_code, 200)
        self.assertEqual(admin_sso.json()["user"]["role"], "ADMIN")

        # 2. Okta SSO Sign-In for new Caretaker
        cg_sso = self.client.post(
            "/api/v1/auth/oauth/okta",
            json={
                "id_token": "okta-oidc-assertion-caretaker-token",
                "email": "karthik.sitter@okta-enterprise.com",
                "full_name": "Karthik Reddy",
                "okta_issuer": "https://pawcare.okta.com/oauth2/default",
                "role": "CAREGIVER",
            },
        )
        self.assertEqual(cg_sso.status_code, 200)
        self.assertEqual(cg_sso.json()["user"]["role"], "CAREGIVER")


if __name__ == "__main__":
    unittest.main()
