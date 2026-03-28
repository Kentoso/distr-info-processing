import hashlib


def h(data: str) -> str:
    """Single SHA-256 hash, returns lowercase hex string."""
    return hashlib.sha256(data.encode()).hexdigest()


def hash_chain(value: str, n: int) -> str:
    """Apply H exactly n times: H^n(value).

    hash_chain(w, 0) == w          (identity)
    hash_chain(w, 1) == H(w)
    hash_chain(w, t) == H^t(w)     (initial anchor w_0)
    """
    for _ in range(n):
        value = h(value)
    return value
