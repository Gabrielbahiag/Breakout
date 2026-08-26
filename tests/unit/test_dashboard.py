"""Testes do dashboard (dashboard.py) — Fase 7: editor de nichos do discover
automático (`discover_topics`), a ÚNICA escrita que o dashboard faz (exceção
documentada ao "dashboard read-only" — Seção 5 do CLAUDE.md).

Usa `streamlit.testing.v1.AppTest` (framework oficial, roda o script sem
navegador) contra um SQLite local TEMPORÁRIO — nunca toca o Turso real, nem
o `.env` de dev (as env vars são sobrescritas pela fixture abaixo).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("local_sqlite_env")]

DASHBOARD_PATH = str(Path(__file__).resolve().parents[2] / "src" / "breakout" / "dashboard.py")


def test_dashboard_sobe_sem_excecao_com_banco_vazio():
    at = AppTest.from_file(DASHBOARD_PATH)
    at.run(timeout=30)
    assert list(at.exception) == []


def test_adiciona_pausa_e_remove_nicho():
    at = AppTest.from_file(DASHBOARD_PATH)
    at.run(timeout=30)

    query_input = next(ti for ti in at.sidebar.text_input if ti.label == "Novo nicho/palavra-chave")
    query_input.set_value("minecraft shorts")
    lang_select = next(sb for sb in at.sidebar.selectbox if sb.label == "Idioma")
    lang_select.set_value("en")
    add_button = next(b for b in at.sidebar.button if b.label == "Adicionar")
    add_button.click().run(timeout=30)
    assert list(at.exception) == []

    labels = [w.value for w in at.sidebar.get("markdown")]
    assert "minecraft shorts (en)" in labels

    toggle_button = next(b for b in at.sidebar.button if b.key and b.key.startswith("toggle_topic_"))
    toggle_button.click().run(timeout=30)
    assert list(at.exception) == []
    labels = [w.value for w in at.sidebar.get("markdown")]
    assert "~~minecraft shorts (en)~~" in labels  # pausado -> riscado

    delete_button = next(b for b in at.sidebar.button if b.key and b.key.startswith("del_topic_"))
    delete_button.click().run(timeout=30)
    assert list(at.exception) == []
    labels = [w.value for w in at.sidebar.get("markdown")]
    assert labels == []


def test_nicho_persiste_entre_reruns_do_dashboard():
    # A prova de que é o BANCO, não session_state — uma instância nova do
    # AppTest (equivalente a recarregar a página) precisa ver o nicho salvo
    # pela instância anterior.
    at1 = AppTest.from_file(DASHBOARD_PATH)
    at1.run(timeout=30)
    query_input = next(ti for ti in at1.sidebar.text_input if ti.label == "Novo nicho/palavra-chave")
    query_input.set_value("valorant")
    add_button = next(b for b in at1.sidebar.button if b.label == "Adicionar")
    add_button.click().run(timeout=30)

    at2 = AppTest.from_file(DASHBOARD_PATH)
    at2.run(timeout=30)
    labels = [w.value for w in at2.sidebar.get("markdown")]
    assert "valorant" in labels
