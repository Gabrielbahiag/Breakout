"""Composition root — onde os contratos encontram as implementações reais.

Este é o único módulo que conhece TODAS as peças concretas ao mesmo tempo. Ele
monta o grafo de dependências (relógio, cliente de API, repositório) a partir das
settings e entrega pronto. Os testes têm o seu próprio "composition root" (os
fixtures do conftest, com os fakes) — por isso nada aqui aparece na suíte.
"""
from __future__ import annotations

from .clock import SystemClock
from .settings import Settings, load_settings
from .storage.connection import make_connection
from .storage.sql_repository import SqlTrajectoryRepository


class Container:
    """Segura as dependências construídas e a conexão viva do banco."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.clock = SystemClock()
        self.connection = make_connection(settings)
        self.repo = SqlTrajectoryRepository(self.connection)

    def youtube(self):
        # Import preguiçoso: só a produção precisa do cliente do Google.
        from .collect.youtube_api import YouTubeApiClient

        return YouTubeApiClient(self.settings.youtube_api_key)


def build(settings: Settings | None = None) -> Container:
    return Container(settings or load_settings())
