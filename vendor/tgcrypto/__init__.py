"""Pure-Python TgCrypto-compatible AES-256-IGE (no C++ Build Tools needed)."""
import os
import pyaes


def _to_bytes(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if hasattr(value, "data") and callable(value.data):
        return bytes(value.data())
    if isinstance(value, list):
        return bytes(value)
    return bytes(value)


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def ige256_encrypt(data, key, iv):
    data = _to_bytes(data)
    key = _to_bytes(key)
    iv = _to_bytes(iv)

    padding = len(data) % 16
    if padding:
        data += os.urandom(16 - padding)

    aes = pyaes.AES(key)
    iv1, iv2 = iv[:16], iv[16:32]
    out = bytearray()

    for i in range(0, len(data), 16):
        plain = data[i : i + 16]
        cipher = _xor(bytes(aes.encrypt(list(_xor(plain, iv1)))), iv2)
        out.extend(cipher)
        iv1, iv2 = cipher, plain

    return bytes(out)


def ige256_decrypt(data, key, iv):
    data = _to_bytes(data)
    key = _to_bytes(key)
    iv = _to_bytes(iv)

    aes = pyaes.AES(key)
    iv1, iv2 = iv[:16], iv[16:32]
    out = bytearray()

    for i in range(0, len(data), 16):
        cipher = data[i : i + 16]
        plain = _xor(bytes(aes.decrypt(list(_xor(cipher, iv2)))), iv1)
        out.extend(plain)
        iv1, iv2 = cipher, plain

    return bytes(out)
