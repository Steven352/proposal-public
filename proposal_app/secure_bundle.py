from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from cryptography.fernet import Fernet, InvalidToken

from proposal_app.config import (
    ABDUL_SIGNATURE_PATH,
    HISTORICAL_DIR,
    KNOWLEDGE_INDEX,
    ROOT_DIR,
    RULES_PATH,
    STANDARD_TERMS_PATH,
    STEVEN_SIGNATURE_PATH,
    WORK_AUTHORIZATION_PATH,
)


ENCRYPTED_BUNDLE_PATH = ROOT_DIR / "proposal_private_assets.enc"
PUBLIC_DEPLOYMENT_MARKER = ROOT_DIR / ".public_deployment"


def is_public_deployment() -> bool:
    return PUBLIC_DEPLOYMENT_MARKER.exists()


def private_assets_ready() -> bool:
    required = (
        KNOWLEDGE_INDEX,
        RULES_PATH,
        STANDARD_TERMS_PATH,
        WORK_AUTHORIZATION_PATH,
        STEVEN_SIGNATURE_PATH,
        ABDUL_SIGNATURE_PATH,
    )
    return all(path.is_file() for path in required) and any(HISTORICAL_DIR.glob("*.docx"))


def ensure_private_assets(encryption_key: str) -> None:
    if private_assets_ready():
        return
    if not ENCRYPTED_BUNDLE_PATH.is_file():
        raise FileNotFoundError("The encrypted proposal asset bundle is missing.")
    if not encryption_key:
        raise ValueError("DATA_ENCRYPTION_KEY is not configured in Streamlit Secrets.")

    try:
        payload = Fernet(encryption_key.encode("utf-8")).decrypt(
            ENCRYPTED_BUNDLE_PATH.read_bytes()
        )
    except (InvalidToken, ValueError) as exc:
        raise ValueError("DATA_ENCRYPTION_KEY is invalid.") from exc

    root = ROOT_DIR.resolve()
    with ZipFile(BytesIO(payload)) as archive:
        for member in archive.infolist():
            destination = (ROOT_DIR / member.filename).resolve()
            if root not in destination.parents:
                raise ValueError("The encrypted proposal asset bundle contains an unsafe path.")
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))

    if not private_assets_ready():
        raise ValueError("The encrypted proposal asset bundle is incomplete.")
