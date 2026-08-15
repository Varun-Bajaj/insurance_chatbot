from base64 import urlsafe_b64encode as b64e, urlsafe_b64decode as b64d
from settings import setting
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

backend = default_backend()
iterations = 100_000


def password_encrypt(password: str, secret_key: str):
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=backend
    )
    key = kdf.derive(secret_key.encode())
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=backend)
    encryptor = cipher.encryptor()
    ct = encryptor.update(password.encode()) + encryptor.finalize()
    return b64e(
        b'%b%b%b' % (
            salt,
            iv,
            ct,
        )
    ).decode()


def password_decrypt(password: bytes, secret_key: str, logger):
    try:
        # Early validation of encrypted data structure
        decoded = b64d(password)
        salt, iv, token = decoded[:16], decoded[16:32], decoded[32:]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=backend
        )
        key = kdf.derive(secret_key.encode())
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=backend)
        decryptor = cipher.decryptor()
        decrypted_password = decryptor.update(token) + decryptor.finalize()
        return decrypted_password.decode()
    except Exception as e:
        logger.exception(f"Exception in password_decryption: {e}")
        return None


import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding


def decrypt_token(token_info, logger):
    """
            Decrypts token
            >> Example Response from MedPharma
                {
                    "token": {
                        "access_token": "...",
                        "expires_in": 2592000,
                        "token_type": "Bearer"
                    },
                    "ivp": "..."
                }
            :param token_info:
            :return: decrypted token
            """
    try:
        iv = base64.b64decode(token_info["ivp"].encode())
        token = base64.b64decode(token_info["token"]["access_token"].encode())

        cipher = Cipher(algorithms.AES(setting.medpharm_key), modes.CBC(iv), backend=default_backend)
        decrypt_obj = cipher.decryptor()
        tkn = decrypt_obj.update(token) + decrypt_obj.finalize()
        pad = padding.PKCS7(128).unpadder()
        tkn = pad.update(tkn) + pad.finalize()
        return tkn.decode()

    except Exception as err:
        logger.exception(f"exception in decrypting token: {err}")
        return False
