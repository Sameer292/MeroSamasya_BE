from hashlib import sha256


def digest_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()
