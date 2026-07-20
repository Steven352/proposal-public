from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Callable
from urllib.parse import quote

import requests

from .config import HISTORICAL_DIR, LEARNED_RULES_PATH, LIBRARY_INDEX_ADDITIONS
from .revision_learning import aggregate_rule_candidates


STATE_PATH = "knowledge/library_state.json"
ADDITIONS_PATH = "knowledge/library_additions.json"
LEARNED_RULES_REPO_PATH = "knowledge/learned_rules.md"
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._() -]+")


class GitHubLibrary:
    def __init__(self, token: str, repository: str, branch: str = "main"):
        if not token:
            raise ValueError("GITHUB_LIBRARY_TOKEN is required.")
        if repository.count("/") != 1:
            raise ValueError("GITHUB_LIBRARY_REPO must use owner/repository format.")
        self.repository = repository
        self.branch = branch
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "almor-proposal-builder",
            }
        )

    def _url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repository}/contents/{quote(path, safe='/')}"

    def _content(self, path: str) -> dict | None:
        response = self.session.get(self._url(path), params={"ref": self.branch}, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def read_bytes(self, path: str) -> bytes | None:
        payload = self._content(path)
        if payload is None:
            return None
        return base64.b64decode(payload["content"])

    def write_bytes(self, path: str, data: bytes, message: str) -> None:
        existing = self._content(path)
        payload = {
            "message": message,
            "content": base64.b64encode(data).decode("ascii"),
            "branch": self.branch,
        }
        if existing:
            payload["sha"] = existing["sha"]
        response = self.session.put(self._url(path), json=payload, timeout=30)
        response.raise_for_status()

    def read_json(self, path: str, default: dict) -> dict:
        data = self.read_bytes(path)
        return deepcopy(default) if data is None else json.loads(data.decode("utf-8"))

    def update_json(self, path: str, default: dict, updater: Callable[[dict], dict], message: str) -> dict:
        last_error: requests.HTTPError | None = None
        for _ in range(3):
            value = updater(self.read_json(path, default))
            try:
                self.write_bytes(
                    path,
                    json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8"),
                    message,
                )
                return value
            except requests.HTTPError as error:
                last_error = error
                if error.response is None or error.response.status_code not in {409, 422}:
                    raise
        if last_error:
            raise last_error
        raise RuntimeError("Could not update the private proposal library.")


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    cleaned = SAFE_FILENAME_RE.sub("_", name).strip(" .")
    if not cleaned:
        cleaned = "Final Proposal"
    if not cleaned.lower().endswith(".docx"):
        cleaned += ".docx"
    return cleaned


def empty_state() -> dict:
    return {"version": 1, "records": [], "approved_rules": []}


def sync_runtime_knowledge(client: GitHubLibrary) -> None:
    additions = client.read_bytes(ADDITIONS_PATH)
    learned_rules = client.read_bytes(LEARNED_RULES_REPO_PATH)
    if additions:
        LIBRARY_INDEX_ADDITIONS.parent.mkdir(parents=True, exist_ok=True)
        LIBRARY_INDEX_ADDITIONS.write_bytes(additions)
        payload = json.loads(additions.decode("utf-8"))
        HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)
        for proposal in payload.get("proposals", []):
            filename = safe_filename(proposal.get("filename", ""))
            document = client.read_bytes(f"data/historical_proposals/{filename}")
            if document:
                (HISTORICAL_DIR / filename).write_bytes(document)
    if learned_rules:
        LEARNED_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_RULES_PATH.write_bytes(learned_rules)


def add_final_to_library(
    client: GitHubLibrary,
    final_filename: str,
    final_bytes: bytes,
    index_record: dict,
    revision_record: dict,
) -> tuple[dict, dict, str]:
    filename = safe_filename(final_filename)
    repository_path = f"data/historical_proposals/{filename}"
    client.write_bytes(repository_path, final_bytes, f"Add reviewed final proposal {filename}")
    HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)
    (HISTORICAL_DIR / filename).write_bytes(final_bytes)

    def update_additions(value: dict) -> dict:
        proposals = value.setdefault("proposals", [])
        key = (index_record.get("proposal_number") or filename).upper()
        proposals[:] = [
            item
            for item in proposals
            if (item.get("proposal_number") or item.get("filename", "")).upper() != key
        ]
        proposals.append({**index_record, "filename": filename})
        value["version"] = 1
        value["proposal_count"] = len(proposals)
        return value

    additions = client.update_json(
        ADDITIONS_PATH,
        {"version": 1, "proposal_count": 0, "proposals": []},
        update_additions,
        f"Index reviewed final proposal {filename}",
    )

    revision_path = f"knowledge/revision_records/{revision_record['id']}.json"
    client.write_bytes(
        revision_path,
        json.dumps(revision_record, indent=2, ensure_ascii=False).encode("utf-8"),
        f"Record detailed reviewer differences for {filename}",
    )

    def update_state(value: dict) -> dict:
        records = value.setdefault("records", [])
        records[:] = [item for item in records if item.get("id") != revision_record["id"]]
        summary_record = {
            key: item_value
            for key, item_value in revision_record.items()
            if key != "differences"
        }
        records.append(
            {
                **summary_record,
                "final_filename": filename,
                "repository_path": repository_path,
                "revision_path": revision_path,
            }
        )
        value.setdefault("approved_rules", [])
        value["version"] = 1
        return value

    state = client.update_json(
        STATE_PATH,
        empty_state(),
        update_state,
        f"Record reviewer changes for {filename}",
    )
    LIBRARY_INDEX_ADDITIONS.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_INDEX_ADDITIONS.write_text(
        json.dumps(additions, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return additions, state, repository_path


def approve_rules(client: GitHubLibrary, keys: list[str]) -> tuple[dict, str]:
    selected = set(keys)

    def update_state(value: dict) -> dict:
        ready = {item["key"]: item for item in aggregate_rule_candidates(value)}
        approved = value.setdefault("approved_rules", [])
        approved_keys = {item["key"] for item in approved}
        for key in sorted(selected):
            if key not in ready or key in approved_keys:
                continue
            candidate = ready[key]
            approved.append(
                {
                    "key": key,
                    "category": candidate.get("category", "wording"),
                    "instruction": candidate["instruction"],
                    "occurrences": candidate["occurrences"],
                    "approved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        return value

    state = client.update_json(
        STATE_PATH,
        empty_state(),
        update_state,
        "Approve repeated proposal drafting rules",
    )
    lines = [
        "# Approved Learned Proposal Rules",
        "",
        "Only rules explicitly approved in the Proposal Builder appear here.",
        "",
    ]
    for rule in state.get("approved_rules", []):
        lines.append(
            f"- [{rule.get('category', 'wording')}] {rule['instruction']} "
            f"(approved after {rule.get('occurrences', 3)} final proposals)"
        )
    content = "\n".join(lines).rstrip() + "\n"
    client.write_bytes(
        LEARNED_RULES_REPO_PATH,
        content.encode("utf-8"),
        "Update approved learned proposal rules",
    )
    LEARNED_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEARNED_RULES_PATH.write_text(content, encoding="utf-8")
    return state, content
