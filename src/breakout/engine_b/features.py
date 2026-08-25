"""Extração de features do Motor B.

Três famílias, tratadas diferente de propósito:

  - **Estáticas** (metadados do upload — título, duração, tags, horário,
    tamanho do canal): não têm corte de tempo, porque já existem por inteiro
    ANTES de qualquer snapshot ser coletado.
  - **Dinâmicas** (engajamento inicial — velocidade de views/likes/comments):
    passam OBRIGATORIAMENTE por `windows.py::snapshots_before` — a barreira
    anti-vazamento. Nenhum ponto depois de `cutoff_hours` pode influenciar o
    valor de uma feature.
  - **Multimodal** (thumbnail via CV, transcrição via legenda — Fase 5):
    OPCIONAL (`with_multimodal=False` por padrão). Thumbnail baixa uma
    imagem pela rede a cada chamada — `extract_features` é usada em lote
    (treino, sweep de cutoff), então ligar isso por padrão tornaria toda
    chamada lenta e dependente de rede sem o caller pedir.

Tudo aqui é puro dado→número; a definição de rótulo (`label.py`) e o modelo
(`model.py`) são deliberadamente módulos separados.
"""
from __future__ import annotations

import pandas as pd

from .thumbnail import extract_thumbnail_features
from .transcript import extract_transcript_features
from .windows import snapshots_before
from ..types import Snapshot, VideoMetadata


def extract_features(
    metadata: VideoMetadata,
    snapshots: list[Snapshot],
    *,
    cutoff_hours: float,
    with_multimodal: bool = False,
) -> dict[str, float]:
    """Monta o vetor de features de UM vídeo, visível só até `cutoff_hours`.

    `with_multimodal=True` soma as features de thumbnail (baixa a imagem) e
    transcrição (já armazenada, sem rede) — ver módulo `thumbnail.py` e
    `transcript.py`. Ambas nunca levantam; vídeo sem thumbnail/legenda só
    contribui menos chaves ao dict.
    """
    window = snapshots_before(snapshots, cutoff_hours)
    last = window[-1] if window else None

    feats = {
        # estáticas — fixas no upload, sem corte de tempo.
        "title_length": float(len(metadata.title)),
        "title_word_count": float(len(metadata.title.split())),
        "title_has_question_mark": float("?" in metadata.title),
        "title_has_number": float(any(ch.isdigit() for ch in metadata.title)),
        "duration_s": float(metadata.duration_s),
        "tag_count": float(len(metadata.tags)),
        "published_hour_of_day": float(metadata.published_at.hour),
        "published_day_of_week": float(metadata.published_at.weekday()),
        "channel_subscribers": float(metadata.channel_subscribers),
        # dinâmicas — só o que já era visível em `cutoff_hours`.
        "views_at_cutoff": float(last.views) if last else 0.0,
        "views_per_hour": float(last.views / cutoff_hours) if last and cutoff_hours > 0 else 0.0,
        "likes_per_hour": float(last.likes / cutoff_hours) if last and cutoff_hours > 0 else 0.0,
        "comments_per_hour": float(last.comments / cutoff_hours) if last and cutoff_hours > 0 else 0.0,
        "n_snapshots_observed": float(len(window)),
    }

    if with_multimodal:
        feats.update(extract_thumbnail_features(metadata.thumbnail_url))
        feats.update(extract_transcript_features(metadata.transcript))

    return feats


def extract_features_batch(
    items: list[tuple[VideoMetadata, list[Snapshot]]],
    *,
    cutoff_hours: float,
    with_multimodal: bool = False,
) -> pd.DataFrame:
    """`extract_features` sobre vários vídeos — uma linha por vídeo, mesmo
    `cutoff_hours` pra todos (comparar features calculadas em janelas
    diferentes por vídeo não faz sentido)."""
    rows = [
        extract_features(meta, snaps, cutoff_hours=cutoff_hours, with_multimodal=with_multimodal)
        for meta, snaps in items
    ]
    return pd.DataFrame(rows, index=[meta.video_id for meta, _ in items])
