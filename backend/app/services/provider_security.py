from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class ProviderConfigurationError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class CredentialCipher:
    def __init__(self, master_key: SecretStr | str | None) -> None:
        if master_key is None:
            raise ProviderConfigurationError(
                "provider_not_configured", "Provider Master Key 未配置"
            )
        key = (
            master_key.get_secret_value()
            if isinstance(master_key, SecretStr)
            else master_key
        )
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exception:
            raise ProviderConfigurationError(
                "provider_not_configured", "Provider Master Key 配置无效"
            ) from exception

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exception:
            raise ProviderConfigurationError(
                "credential_decryption_failed", "Credential 无法解密"
            ) from exception

    @staticmethod
    def fingerprint(plaintext: str) -> str:
        return sha256(plaintext.encode("utf-8")).hexdigest()
