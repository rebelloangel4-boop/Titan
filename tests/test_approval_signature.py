import base64
import tempfile
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from titan.security import (
    approval_signing_payload,
    create_approval_challenge,
    register_device_public_key,
    verify_approval_signature,
)
from titan.store import Database
from titan.tools import ToolRegistry


class ApprovalSignatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "approvals.db")
        self.approval = ToolRegistry(self.db).request(
            "mission-1", "github.read", {"repository": "owner/repo"}
        )
        self.approval_id = self.approval["id"]

    def tearDown(self):
        self.temp.cleanup()

    def register_ecdsa(self, device="android-1"):
        private = ec.generate_private_key(ec.SECP256R1())
        public = private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        register_device_public_key(self.db, device, "ECDSA_P256_SHA256", public)
        return private, device

    def register_ed25519(self, device="android-ed"):
        private = ed25519.Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        register_device_public_key(self.db, device, "ED25519", public)
        return private, device

    def sign(self, private, challenge, algorithm):
        payload = approval_signing_payload(
            challenge["device_id"], challenge["approval_id"],
            challenge["action_digest"], challenge["expiry"], challenge["nonce"],
        )
        if algorithm == "ECDSA_P256_SHA256":
            signature = private.sign(payload, ec.ECDSA(hashes.SHA256()))
        else:
            signature = private.sign(payload)
        return base64.b64encode(signature).decode()

    def test_ecdsa_p256_approval_succeeds(self):
        private, device = self.register_ecdsa()
        challenge = create_approval_challenge(self.db, self.approval_id, device)
        signature = self.sign(private, challenge, "ECDSA_P256_SHA256")
        result = verify_approval_signature(
            self.db, device, self.approval_id, challenge["action_digest"],
            challenge["expiry"], challenge["nonce"], signature,
        )
        self.assertTrue(result["approved"])

    def test_ed25519_approval_succeeds(self):
        private, device = self.register_ed25519()
        challenge = create_approval_challenge(self.db, self.approval_id, device)
        signature = self.sign(private, challenge, "ED25519")
        result = verify_approval_signature(
            self.db, device, self.approval_id, challenge["action_digest"],
            challenge["expiry"], challenge["nonce"], signature,
        )
        self.assertTrue(result["approved"])

    def test_expired_nonce_rejected(self):
        private, device = self.register_ecdsa()
        challenge = create_approval_challenge(self.db, self.approval_id, device)
        signature = self.sign(private, challenge, "ECDSA_P256_SHA256")
        with self.db.connect() as c:
            c.execute("UPDATE approval_challenges SET expiry=? WHERE nonce=?",
                      (int(time.time()) - 1, challenge["nonce"]))
        with self.assertRaises(PermissionError):
            verify_approval_signature(
                self.db, device, self.approval_id, challenge["action_digest"],
                challenge["expiry"], challenge["nonce"], signature,
            )

    def test_replayed_nonce_rejected(self):
        private, device = self.register_ecdsa()
        challenge = create_approval_challenge(self.db, self.approval_id, device)
        signature = self.sign(private, challenge, "ECDSA_P256_SHA256")
        args = (self.db, device, self.approval_id, challenge["action_digest"],
                challenge["expiry"], challenge["nonce"], signature)
        self.assertTrue(verify_approval_signature(*args)["approved"])
        with self.assertRaises(PermissionError):
            verify_approval_signature(*args)

    def test_tampered_action_digest_rejected(self):
        private, device = self.register_ecdsa()
        challenge = create_approval_challenge(self.db, self.approval_id, device)
        tampered = "0" * 64
        signature = self.sign(private, {**challenge, "action_digest": tampered},
                              "ECDSA_P256_SHA256")
        with self.assertRaises(PermissionError):
            verify_approval_signature(
                self.db, device, self.approval_id, tampered,
                challenge["expiry"], challenge["nonce"], signature,
            )

    def test_wrong_device_and_bad_signature_rejected(self):
        private, device = self.register_ecdsa()
        challenge = create_approval_challenge(self.db, self.approval_id, device)
        with self.assertRaises(PermissionError):
            verify_approval_signature(
                self.db, "other-device", self.approval_id,
                challenge["action_digest"], challenge["expiry"],
                challenge["nonce"], base64.b64encode(b"bad-signature").decode(),
            )

    def test_registered_device_key_cannot_be_silently_replaced(self):
        private, device = self.register_ecdsa()
        replacement = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        with self.assertRaises(ValueError):
            register_device_public_key(self.db, device, "ECDSA_P256_SHA256", replacement)

    def test_invalid_key_algorithm_rejected(self):
        with self.assertRaises(ValueError):
            register_device_public_key(self.db, "bad", "RSA", "not-a-key")


if __name__ == "__main__":
    unittest.main()
