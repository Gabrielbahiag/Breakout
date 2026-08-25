"""Testes de extração de features de transcrição (transcript.py).

Sem rede envolvida (o texto já chega pronto) — exemplos à mão, resposta
óbvia, mesmo espírito de test_metrics.py.
"""
from __future__ import annotations

import pytest

from breakout.engine_b.transcript import extract_transcript_features

pytestmark = pytest.mark.unit


def test_transcricao_vazia_so_marca_indisponivel():
    assert extract_transcript_features("") == {"transcript_available": 0.0}


def test_transcricao_ausente_none_tratado_como_vazio():
    assert extract_transcript_features(None) == {"transcript_available": 0.0}


def test_conta_palavras_e_pontuacao():
    feats = extract_transcript_features("Você já viu isso? Incrível!")
    assert feats["transcript_available"] == 1.0
    assert feats["transcript_word_count"] == 5.0
    assert feats["transcript_has_question"] == 1.0
    assert feats["transcript_has_exclamation"] == 1.0


def test_sem_pergunta_nem_exclamacao():
    feats = extract_transcript_features("um video qualquer sem nada de especial")
    assert feats["transcript_has_question"] == 0.0
    assert feats["transcript_has_exclamation"] == 0.0


def test_comprimento_medio_de_palavra():
    feats = extract_transcript_features("oi tudo bem")  # 2,4,3 letras -> media 3
    assert feats["transcript_avg_word_length"] == pytest.approx(3.0)
