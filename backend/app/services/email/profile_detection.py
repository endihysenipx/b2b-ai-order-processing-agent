from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field


class ClientProfile(StrEnum):
    LUTZ = "lutz"
    LESNINA = "lesnina"


class ClientProfileDetection(BaseModel):
    client_profile: ClientProfile | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    is_manual_override: bool = False


class ClientProfileDetector:
    """Identify a client profile from stable email-format and attachment signals."""

    _lutz_item_pattern = re.compile(
        r"^\s*\d+(?:[.,]\d+)?\s*x\s+[A-Z0-9]+(?:-[A-Z0-9]+)+\s+\([^)]*\)", re.IGNORECASE | re.MULTILINE
    )
    _lesnina_delivery_country_pattern = re.compile(r"\b(?:HR|RS)-\d{4,6}\b", re.IGNORECASE)

    def detect(self, subject: str, body: str, attachment_names: list[str]) -> ClientProfileDetection:
        text = f"{subject}\n{body}".casefold()
        lutz_score, lutz_evidence = self._score_lutz(text, body, attachment_names)
        lesnina_score, lesnina_evidence = self._score_lesnina(text, body, attachment_names)

        if max(lutz_score, lesnina_score) < 0.65 or abs(lutz_score - lesnina_score) < 0.2:
            return ClientProfileDetection(
                confidence=round(max(lutz_score, lesnina_score), 2),
                evidence=[*lutz_evidence, *lesnina_evidence],
            )
        if lutz_score > lesnina_score:
            return ClientProfileDetection(
                client_profile=ClientProfile.LUTZ,
                confidence=round(min(lutz_score, 1), 2),
                evidence=lutz_evidence,
            )
        return ClientProfileDetection(
            client_profile=ClientProfile.LESNINA,
            confidence=round(min(lesnina_score, 1), 2),
            evidence=lesnina_evidence,
        )

    @staticmethod
    def manual_override(client_profile: ClientProfile) -> ClientProfileDetection:
        return ClientProfileDetection(
            client_profile=client_profile,
            confidence=1,
            evidence=["Client profile was selected manually."],
            is_manual_override=True,
        )

    def _score_lutz(self, text: str, body: str, attachment_names: list[str]) -> tuple[float, list[str]]:
        score = 0.0
        evidence: list[str] = []
        attachment_names_lower = [filename.casefold() for filename in attachment_names]
        if "filiale:" in text:
            score += 0.4
            evidence.append("Contains the Lutz 'Filiale:' field.")
        if self._lutz_item_pattern.search(body):
            score += 0.3
            evidence.append("Contains Lutz structured item lines.")
        if any(filename.endswith(".dhp") for filename in attachment_names_lower):
            score += 0.25
            evidence.append("Contains a Lutz DHP planning attachment.")
        if "details zur bestellung" in text:
            score += 0.1
            evidence.append("Contains the Lutz order-detail section.")
        if "office-lutz@" in text:
            score += 0.15
            evidence.append("Contains the original Lutz sender address.")
        return score, evidence

    def _score_lesnina(self, text: str, body: str, attachment_names: list[str]) -> tuple[float, list[str]]:
        score = 0.0
        evidence: list[str] = []
        attachment_names_lower = [filename.casefold() for filename in attachment_names]
        if any(filename.endswith((".tif", ".tiff")) for filename in attachment_names_lower):
            score += 0.45
            evidence.append("Contains a Lesnina TIFF scan attachment.")
        if "lesnina" in text:
            score += 0.25
            evidence.append("Contains Lesnina company text.")
        if "moemax" in text:
            score += 0.15
            evidence.append("Contains a Moemax/Lesnina delivery location.")
        if "lesnina" in text and any(
            phrase
            in text
            for phrase in ("retoure", "auftragsbestaetigung", "schicken sie uns die ab", "bitte sie um ab", "služba za kupce")
        ):
            score += 0.4
            evidence.append("Contains a Lesnina return or order-confirmation message pattern.")
        if self._lesnina_delivery_country_pattern.search(body):
            score += 0.2
            evidence.append("Contains a Croatian or Serbian delivery address.")
        if any(phrase in text for phrase in ("prema skici", "ormar s ", "aviso per mail")):
            score += 0.2
            evidence.append("Contains Lesnina Croatian order wording.")
        if "tip:" in text or "mod:" in text:
            score += 0.15
            evidence.append("Contains a Lesnina TIP/MOD item reference.")
        return score, evidence
