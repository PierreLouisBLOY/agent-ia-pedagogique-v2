"""Local content checks only; implementations acquire no generation authority."""
from collections.abc import Mapping
from typing import Protocol

from backend.modules.pedagogical_design.contracts.dto.p0_production import P0Production


class CapturedContentValidation(Protocol):
    def parse(self, text: str, dispatch: Mapping[str, object]) -> Mapping[str, object]: ...
    def bind(self, dispatch: Mapping[str, object], content: Mapping[str, object]
             ) -> tuple[P0Production, Mapping[str, object]]: ...
