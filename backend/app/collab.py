from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class VerificationCase:
    id: str
    report_id: str
    media_hint: str
    status: str = "open"
    votes: List[Dict[str, str]] = field(default_factory=list)


class CollaborationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cases: Dict[str, VerificationCase] = {}

    def create_case(self, report_id: str, media_hint: str) -> VerificationCase:
        with self._lock:
            case = VerificationCase(id=uuid.uuid4().hex, report_id=report_id, media_hint=media_hint)
            self._cases[case.id] = case
            return case

    def vote(self, case_id: str, reviewer: str, verdict: str, note: str = "") -> VerificationCase:
        with self._lock:
            case = self._cases[case_id]
            case.votes.append({"reviewer": reviewer, "verdict": verdict, "note": note})
            votes = [v["verdict"] for v in case.votes]
            if votes.count("fake") >= 2:
                case.status = "consensus_fake"
            elif votes.count("real") >= 2:
                case.status = "consensus_real"
            return case

    def get_case(self, case_id: str) -> VerificationCase:
        return self._cases[case_id]
