"""ManualClock — um relógio controlado à mão para os testes.

Implementa o Protocol `Clock`. Você avança o tempo explicitamente, então o
coletor vira 100% determinístico: nada de `sleep`, nada de tempo de parede.
"""
from __future__ import annotations

from datetime import datetime, timedelta


class ManualClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, *, hours: float = 0, minutes: float = 0, seconds: float = 0) -> None:
        self._now += timedelta(hours=hours, minutes=minutes, seconds=seconds)
