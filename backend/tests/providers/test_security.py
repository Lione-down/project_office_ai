from base64 import urlsafe_b64encode

import pytest

from app.services.provider_security import (
    CredentialCipher,
    ProviderConfigurationError,
)
from app.settings.config import Settings


def valid_master_key() -> str:
    return urlsafe_b64encode(b"provider-test-master-key-32bytes").decode()


def test_master_key_is_unconfigured_when_missing_or_blank() -> None:
    assert Settings(_env_file=None).master_key is None
    assert Settings(OFFICE_AI_MASTER_KEY="", _env_file=None).master_key is None


def test_credential_cipher_fails_closed_without_master_key() -> None:
    with pytest.raises(ProviderConfigurationError) as error:
        CredentialCipher(None)

    assert error.value.error_code == "provider_not_configured"


def test_credential_cipher_encrypts_randomly_and_fingerprints_stably() -> None:
    cipher = CredentialCipher(valid_master_key())
    plaintext = "agnes-key-never-store-in-plaintext"

    first_ciphertext = cipher.encrypt(plaintext)
    second_ciphertext = cipher.encrypt(plaintext)

    assert plaintext not in first_ciphertext
    assert first_ciphertext != second_ciphertext
    assert cipher.decrypt(first_ciphertext) == plaintext
    assert cipher.fingerprint(plaintext) == cipher.fingerprint(plaintext)
    assert len(cipher.fingerprint(plaintext)) == 64
