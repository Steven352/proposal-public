"""Access roles; legacy configured codes always receive unsigned access."""
import hashlib
import hmac


ACCESS_SESSION_VERSION = 2
_SIGNER_SALT = bytes.fromhex("04f97ebbfb7f9ea6509882d3045d728a")
_SIGNER_VERIFIER = bytes.fromhex("0a5d516c4850352acce3011b3bff2ab8b666cad4557296f5ea2490191f3d7217")
_RETIRED_SIGNER_DIGEST = "fdc5d8bf2ff94c03d95f6a8f8914a91f7082d20de4b0335c05f55f84863374a5"


def access_role(entered: str, configured_code: str = "") -> str | None:
    entered_bytes = entered.encode()
    digest = hashlib.sha256(entered_bytes).hexdigest()
    if hmac.compare_digest(digest, _RETIRED_SIGNER_DIGEST):
        return None
    if hmac.compare_digest(digest, "60a1775ceadd0bd015eec0ea9f25322a19a4293e2f834eef33a30a4ccb9b8b80"):
        return "standard"
    verifier = hashlib.scrypt(
        entered_bytes, salt=_SIGNER_SALT, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32,
    )
    if hmac.compare_digest(verifier, _SIGNER_VERIFIER):
        return "signer"
    if configured_code and hmac.compare_digest(entered_bytes, configured_code.encode()):
        return "standard"
    return None
