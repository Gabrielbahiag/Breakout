"""Testes do dashboard — Parte 2 do plano `dashboard-multimodal-e-coleta.md`
(Fase 7): botões "Disparar collect/discover agora" via API do GitHub.

`streamlit.testing.v1.AppTest` + `respx` mockando `httpx.post` (Princípio 3:
mockar só a fronteira externa real). Nunca testa contra a API real do GitHub.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("local_sqlite_env")]

DASHBOARD_PATH = str(Path(__file__).resolve().parents[2] / "src" / "breakout" / "dashboard.py")
DISPATCH_URL_COLLECT = (
    "https://api.github.com/repos/Gabrielbahiag/Breakout/actions/workflows/collect.yml/dispatches"
)


def _open():
    at = AppTest.from_file(DASHBOARD_PATH)
    at.run(timeout=30)
    return at


def _dispatch_button(at, label_substring: str):
    return next(b for b in at.sidebar.button if label_substring.lower() in b.label.lower())


def test_botoes_desabilitados_sem_secret():
    at = _open()
    assert list(at.exception) == []
    assert _dispatch_button(at, "collect agora").disabled is True
    assert _dispatch_button(at, "discover agora").disabled is True


@respx.mock
def test_disparo_collect_com_secret_mostra_sucesso(monkeypatch):
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "token-de-teste")
    respx.post(DISPATCH_URL_COLLECT).mock(return_value=httpx.Response(204))

    at = _open()
    _dispatch_button(at, "collect agora").click().run(timeout=30)

    assert list(at.exception) == []
    successes = [s.value for s in at.sidebar.success]
    assert any("enfileirad" in s.lower() for s in successes)


@respx.mock
def test_disparo_com_falha_da_api_mostra_erro(monkeypatch):
    monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "token-invalido")
    respx.post(DISPATCH_URL_COLLECT).mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )

    at = _open()
    _dispatch_button(at, "collect agora").click().run(timeout=30)

    assert list(at.exception) == []
    errors = [e.value for e in at.sidebar.error]
    assert any("401" in e or "credentials" in e.lower() for e in errors)
