import ecdsa
import hashlib

def generate_keys():
    """
    Генерирует пару ключей (приватный и публичный) с использованием кривой SECP256k1.
    Публичный ключ будет использоваться как адрес кошелька.
    """
    sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    private_key = sk.to_string().hex()
    vk = sk.get_verifying_key()
    public_key = vk.to_string().hex()
    return private_key, public_key

def sign_transaction(private_key_hex: str, data_to_sign: str) -> str:
    sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key_hex), curve=ecdsa.SECP256k1)
    message_hash = hashlib.sha256(data_to_sign.encode()).digest()
    signature_bytes = sk.sign(message_hash)
    return signature_bytes.hex()

def verify_signature(public_key_hex: str, data_to_sign: str, signature_hex: str) -> bool:
    """
    Проверяет, что signature_hex — корректная ECDSA‑подпись
    для data_to_sign с данным публичным ключом (hex‑строка).
    """
    try:
        vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=ecdsa.SECP256k1)
    except Exception as e:
        print(f"Ошибка при создании VerifyingKey: {e}")
        return False

    message_hash = hashlib.sha256(data_to_sign.encode('utf-8')).digest()
    try:
        sig_bytes = bytes.fromhex(signature_hex)
    except Exception as e:
        print(f"Неправильный формат подписи: {e}")
        return False

    try:
        return vk.verify(sig_bytes, message_hash)
    except ecdsa.BadSignatureError:
        return False
    except Exception as e:
        print(f"Ошибка при проверке подписи: {e}")
        return False
