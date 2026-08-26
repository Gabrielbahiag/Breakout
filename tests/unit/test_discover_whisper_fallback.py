"""Testes de `cli.py::_run_discover` — fallback de transcrição via Whisper
(Fase 7, `planning/transcricao-whisper.md`).

Propriedade crítica a travar: legenda (grátis, sem download de mídia) é
SEMPRE a primeira tentativa; Whisper só roda quando não há legenda E o
fallback está habilitado. `faster-whisper`/`yt-dlp` (extra `[whisper]`) não
estão instalados neste ambiente de teste — isso é usado a favor do teste:
se o código importasse `whisper_transcribe` fora da hora certa, o teste
quebraria com `ModuleNotFoundError` de verdade, provando que o import é
condicional/preguiçoso.
"""
from __future__ import annotations

import sqlite3
import sys
import types
from datetime import datetime, timezone

import pytest

import breakout.collect.transcript_api as transcript_api
from breakout.cli import _run_discover
from breakout.settings import Settings
from breakout.storage.sql_repository import SqlTrajectoryRepository
from breakout.types import VideoMetadata
from tests.fakes.clock import ManualClock
from tests.fakes.youtube import FakeYouTubeClient

pytestmark = pytest.mark.unit

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeContainer:
    def __init__(self, yt, repo, conn, clock, settings):
        self._yt = yt
        self.repo = repo
        self.connection = conn
        self.clock = clock
        self.settings = settings

    def youtube(self):
        return self._yt


@pytest.fixture
def container():
    conn = sqlite3.connect(":memory:")
    repo = SqlTrajectoryRepository(conn)
    repo.init_schema()
    yt = FakeYouTubeClient()
    yt.set_series("v1", [10])
    yt.set_metadata(
        VideoMetadata(video_id="v1", channel_id="c1", title="t", duration_s=30, published_at=T0)
    )
    return _FakeContainer(yt, repo, conn, ManualClock(T0), Settings(whisper_fallback_enabled=False))


def _saved_metadata(container) -> VideoMetadata:
    return container.repo.list_metadata()[0]


def test_legenda_disponivel_nunca_aciona_whisper(container, monkeypatch):
    monkeypatch.setattr(transcript_api, "fetch_transcript_text", lambda video_id: "texto da legenda")

    _run_discover(container, "query", 50)

    meta = _saved_metadata(container)
    assert meta.transcript == "texto da legenda"
    assert meta.transcript_source == "caption"


def test_sem_legenda_e_fallback_desligado_nao_importa_whisper(container, monkeypatch):
    monkeypatch.setattr(transcript_api, "fetch_transcript_text", lambda video_id: None)
    assert container.settings.whisper_fallback_enabled is False

    _run_discover(container, "query", 50)  # não pode levantar ModuleNotFoundError

    meta = _saved_metadata(container)
    assert meta.transcript == ""
    assert meta.transcript_source == ""


def test_sem_legenda_e_fallback_ligado_usa_whisper(container, monkeypatch):
    monkeypatch.setattr(transcript_api, "fetch_transcript_text", lambda video_id: None)
    container.settings = Settings(whisper_fallback_enabled=True)

    calls: list[str] = []
    fake_module = types.ModuleType("breakout.collect.whisper_transcribe")
    fake_module.transcribe_via_whisper = lambda video_id: (calls.append(video_id) or "texto via whisper")
    monkeypatch.setitem(sys.modules, "breakout.collect.whisper_transcribe", fake_module)

    _run_discover(container, "query", 50)

    assert calls == ["v1"]
    meta = _saved_metadata(container)
    assert meta.transcript == "texto via whisper"
    assert meta.transcript_source == "whisper"


def test_sem_legenda_whisper_tambem_falha_source_fica_vazio(container, monkeypatch):
    monkeypatch.setattr(transcript_api, "fetch_transcript_text", lambda video_id: None)
    container.settings = Settings(whisper_fallback_enabled=True)

    fake_module = types.ModuleType("breakout.collect.whisper_transcribe")
    fake_module.transcribe_via_whisper = lambda video_id: None
    monkeypatch.setitem(sys.modules, "breakout.collect.whisper_transcribe", fake_module)

    _run_discover(container, "query", 50)

    meta = _saved_metadata(container)
    assert meta.transcript == ""
    assert meta.transcript_source == ""
