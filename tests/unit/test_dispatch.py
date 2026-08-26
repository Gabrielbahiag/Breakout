"""Testes de `collect/dispatch.py` — Parte 2 do plano
`dashboard-multimodal-e-coleta.md` (Fase 7): disparar `collect`/`discover`
pelo dashboard via a API de `workflow_dispatch` do GitHub, preservando o
princípio "dashboard read-only" (o dashboard nunca escreve no Turso direto —
ele só pede pro GitHub Actions rodar, exatamente como um clique manual em
"Run workflow" já faz).

`build_dispatch_request` é pura (monta URL/headers/payload, sem rede) —
Princípio 3 do CLAUDE.md, mockar só a fronteira externa real. `trigger_workflow`
é o adaptador fino sobre `httpx.post`, testado com `respx`.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from breakout.collect.dispatch import build_dispatch_request, trigger_workflow

pytestmark = pytest.mark.unit


def test_build_dispatch_request_monta_url_headers_e_payload():
    req = build_dispatch_request(
        token="meu-token",
        owner="Gabrielbahiag",
        repo="Breakout",
        workflow_file="collect.yml",
        ref="main",
    )
    assert req.url == (
        "https://api.github.com/repos/Gabrielbahiag/Breakout/"
        "actions/workflows/collect.yml/dispatches"
    )
    assert req.headers["Authorization"] == "Bearer meu-token"
    assert req.headers["Accept"] == "application/vnd.github+json"
    assert req.json == {"ref": "main"}


def test_build_dispatch_request_ref_default_e_main():
    req = build_dispatch_request(
        token="t", owner="o", repo="r", workflow_file="discover.yml"
    )
    assert req.json == {"ref": "main"}


@respx.mock
def test_trigger_workflow_sucesso():
    route = respx.post(
        "https://api.github.com/repos/o/r/actions/workflows/collect.yml/dispatches"
    ).mock(return_value=httpx.Response(204))

    ok, mensagem = trigger_workflow(
        token="t", owner="o", repo="r", workflow_file="collect.yml"
    )

    assert route.called
    assert ok is True
    assert "enfileirad" in mensagem.lower()


@respx.mock
def test_trigger_workflow_token_invalido_nao_levanta():
    respx.post(
        "https://api.github.com/repos/o/r/actions/workflows/collect.yml/dispatches"
    ).mock(return_value=httpx.Response(401, json={"message": "Bad credentials"}))

    ok, mensagem = trigger_workflow(
        token="t-invalido", owner="o", repo="r", workflow_file="collect.yml"
    )

    assert ok is False
    assert "401" in mensagem or "credentials" in mensagem.lower()


def test_trigger_workflow_sem_token_nao_faz_rede():
    ok, mensagem = trigger_workflow(
        token="", owner="o", repo="r", workflow_file="collect.yml"
    )
    assert ok is False
    assert "token" in mensagem.lower()


@respx.mock
def test_trigger_workflow_erro_de_rede_nao_levanta():
    respx.post(
        "https://api.github.com/repos/o/r/actions/workflows/collect.yml/dispatches"
    ).mock(side_effect=httpx.ConnectError("boom"))

    ok, mensagem = trigger_workflow(
        token="t", owner="o", repo="r", workflow_file="collect.yml"
    )

    assert ok is False
    assert mensagem
