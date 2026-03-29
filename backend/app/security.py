from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class MerkleTree:
    leaves: List[str]

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def from_items(cls, items: Iterable[str]) -> "MerkleTree":
        hashed = [cls._hash(item) for item in items]
        if not hashed:
            hashed = [cls._hash("empty")]
        return cls(leaves=hashed)

    def root(self) -> str:
        level = list(self.leaves)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            next_level = []
            for i in range(0, len(level), 2):
                next_level.append(self._hash(level[i] + level[i + 1]))
            level = next_level
        return level[0]


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def payload_integrity_checksum(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sign_payload(payload: dict, secret: str) -> str:
    body = canonical_json(payload).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
