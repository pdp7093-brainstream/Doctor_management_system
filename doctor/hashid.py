ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)

def encode_id(num: int) -> str:
    """Encode integer id to a short base62 string."""
    if num is None:
        return ''
    if num == 0:
        return ALPHABET[0]
    out = []
    n = int(num)
    while n > 0:
        n, rem = divmod(n, BASE)
        out.append(ALPHABET[rem])
    return ''.join(reversed(out))

def decode_hash(s: str) -> int:
    """Decode base62 string back to integer id. Raises ValueError if invalid."""
    if not s:
        raise ValueError('Empty hash')
    n = 0
    for ch in s:
        try:
            idx = ALPHABET.index(ch)
        except ValueError:
            raise ValueError('Invalid character in hash')
        n = n * BASE + idx
    return n
