"""Testes de extração de features (features.py).

A propriedade mais importante aqui NÃO é "o valor está certo" (isso os
exemplos à mão já cobrem) — é a anti-vazamento: adicionar snapshots FUTUROS à
lista de entrada não pode mudar nenhuma feature dinâmica. Isso complementa
`test_no_leakage.py` (que testa a barreira em si) testando o usuário real
dela.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from breakout.engine_b.features import extract_features, extract_features_batch
from breakout.types import Snapshot, VideoMetadata

pytestmark = pytest.mark.unit

T0 = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)  # quinta-feira, 08h


def _meta(**kwargs) -> VideoMetadata:
    defaults = dict(
        video_id="v1",
        channel_id="c1",
        title="Como fazer 5 receitas rápidas?",
        duration_s=45,
        published_at=T0,
        channel_subscribers=10_000,
        tags=("comida", "receita"),
        category="22",
    )
    defaults.update(kwargs)
    return VideoMetadata(**defaults)


def _snap(hours, views, likes=0, comments=0):
    return Snapshot(video_id="v1", at=T0 + timedelta(hours=hours), views=views, likes=likes, comments=comments)


def test_features_estaticas_batem_com_os_metadados():
    feats = extract_features(_meta(), [], cutoff_hours=1.0)
    assert feats["title_length"] == len("Como fazer 5 receitas rápidas?")
    assert feats["title_word_count"] == 5
    assert feats["title_has_question_mark"] == 1.0
    assert feats["title_has_number"] == 1.0
    assert feats["duration_s"] == 45.0
    assert feats["tag_count"] == 2.0
    assert feats["published_hour_of_day"] == 8.0
    assert feats["published_day_of_week"] == 3.0  # quinta (Monday=0)
    assert feats["channel_subscribers"] == 10_000.0


def test_features_dinamicas_usam_o_ultimo_ponto_da_janela():
    snaps = [_snap(0, 10, 1, 0), _snap(2, 50, 5, 1), _snap(6, 300, 20, 4)]
    feats = extract_features(_meta(), snaps, cutoff_hours=2.0)
    assert feats["views_at_cutoff"] == 50.0
    assert feats["views_per_hour"] == pytest.approx(25.0)
    assert feats["likes_per_hour"] == pytest.approx(2.5)
    assert feats["comments_per_hour"] == pytest.approx(0.5)
    assert feats["n_snapshots_observed"] == 2.0


def test_sem_snapshots_dinamicas_ficam_em_zero():
    feats = extract_features(_meta(), [], cutoff_hours=5.0)
    assert feats["views_at_cutoff"] == 0.0
    assert feats["views_per_hour"] == 0.0
    assert feats["n_snapshots_observed"] == 0.0


def test_adicionar_snapshots_futuros_nao_muda_as_features():
    passado = [_snap(0, 10), _snap(2, 50)]
    futuro = [_snap(10, 5_000), _snap(20, 50_000)]
    so_passado = extract_features(_meta(), passado, cutoff_hours=2.0)
    com_futuro = extract_features(_meta(), passado + futuro, cutoff_hours=2.0)
    assert so_passado == com_futuro


def test_extract_features_batch_uma_linha_por_video():
    items = [
        (_meta(video_id="a"), [_snap(0, 10)]),
        (_meta(video_id="b"), [_snap(0, 999)]),
    ]
    df = extract_features_batch(items, cutoff_hours=1.0)
    assert list(df.index) == ["a", "b"]
    assert df.loc["a", "views_at_cutoff"] == 10.0
    assert df.loc["b", "views_at_cutoff"] == 999.0
