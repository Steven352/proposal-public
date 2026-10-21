"""Access roles; legacy configured codes always receive unsigned access."""
import hashlib
import hmac


def access_role(entered: str, configured_code: str = "") -> str | None:
    digest = hashlib.sha256(entered.encode()).hexdigest()
    if hmac.compare_digest(digest, "fdc5d8bf2ff94c03d95f6a8f8914a91f7082d20de4b0335c05f55f84863374a5"):
        return "signer"
    if hmac.compare_digest(digest, "60a1775ceadd0bd015eec0ea9f25322a19a4293e2f834eef33a30a4ccb9b8b80"):
        return "standard"
    if configured_code and hmac.compare_digest(entered, configured_code):
        return "standard"
    return None
