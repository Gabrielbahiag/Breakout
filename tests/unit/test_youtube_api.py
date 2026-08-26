"""Teste do adaptador real da YouTube API (youtube_api.py) — só a lógica de
montar a chamada (quais parâmetros vão pra `search.list`), sem tocar o
`google-api-python-client` de verdade (nunca faz request real, Princípio 3).

Diferente do resto do `youtube_api.py` (que não tem teste direto — mockar o
cliente do Google é feio, prefere-se o `FakeYouTubeClient` no resto do
sistema), aqui vale a pena: um nome de parâmetro errado faria o filtro de
idioma (Fase 7) silenciosamente não fazer nada, sem nenhum teste acusando.
Stub só o `_service()` (nosso próprio método, não o cliente do Google cru).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from breakout.collect.youtube_api import YouTubeApiClient

pytestmark = pytest.mark.unit


class _FakeSearchList:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def list(self, **kwargs):
        self._captured.update(kwargs)
        return self

    def execute(self):
        return {"items": []}


class _FakeService:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def search(self):
        return _FakeSearchList(self._captured)


def test_search_recent_sem_idioma_nao_inclui_relevance_language():
    client = YouTubeApiClient(api_key="x")
    captured: dict = {}
    client._svc = _FakeService(captured)

    client.search_recent("valorant", published_after=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert "relevanceLanguage" not in captured
    assert captured["q"] == "valorant"
    assert captured["videoDuration"] == "short"


def test_search_recent_com_idioma_inclui_relevance_language():
    client = YouTubeApiClient(api_key="x")
    captured: dict = {}
    client._svc = _FakeService(captured)

    client.search_recent(
        "minecraft shorts",
        published_after=datetime(2026, 1, 1, tzinfo=timezone.utc),
        language="en",
    )

    assert captured["relevanceLanguage"] == "en"
