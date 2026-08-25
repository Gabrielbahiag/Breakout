"""CLI do Breakout — pontos de entrada finos sobre o núcleo.

Cada subcomando é uma composição enxuta: monta o Container e delega. O GitHub
Actions chama `breakout collect --once`; você chama `breakout dashboard` local.

    breakout initdb                 aplica o schema no banco configurado
    breakout discover --query "..." descobre vídeos recentes e semeia a carteira
    breakout collect [--once]       tira uma rodada de snapshots dos vídeos vencidos
    breakout detect                 job offline: roda detectores e grava detecções
    breakout dashboard              sobe o Streamlit (replay ao vivo do Motor A)
"""
from __future__ import annotations

import typer

from . import composition
from .collect import policy
from .collect.snapshots import SnapshotCollector

app = typer.Typer(help="Breakout — detector de viralização de vídeos curtos.")


@app.command()
def initdb() -> None:
    """Aplica o schema (idempotente)."""
    c = composition.build()
    c.repo.init_schema()
    typer.echo("schema aplicado.")


@app.command()
def discover(query: str = typer.Option(..., help="termo de busca"), max_results: int = 50) -> None:
    """Descobre vídeos recentes e os semeia na carteira (gasta cota de search).

    Thumbnail vem de graça no `fetch_metadata` (Data API oficial). Legenda
    (Fase 5, Motor B multimodal) é buscada à parte via
    `collect/transcript_api.py` — mecanismo separado, não gasta cota da
    Data API, best-effort (vídeo sem legenda vira string vazia, não quebra).
    """
    import dataclasses
    from datetime import timedelta

    from .collect.transcript_api import fetch_transcript_text

    c = composition.build()
    c.repo.init_schema()
    yt = c.youtube()
    since = c.clock.now() - timedelta(hours=6)
    ids = yt.search_recent(query, published_after=since, max_results=max_results)
    for meta in yt.fetch_metadata(ids):
        transcript = fetch_transcript_text(meta.video_id) or ""
        meta = dataclasses.replace(meta, transcript=transcript)
        c.repo.save_metadata(meta)
        c.connection.execute(
            "UPDATE videos SET first_seen_at = COALESCE(first_seen_at, ?), active = 1 "
            "WHERE video_id = ?",
            (c.clock.now().isoformat(), meta.video_id),
        )
    c.connection.commit()
    typer.echo(f"descobertos e semeados: {len(ids)} vídeos.")


@app.command()
def collect(once: bool = typer.Option(True, help="uma rodada só (modo GitHub Actions)")) -> None:
    """Amostra os vídeos vencidos pela política de cadência."""
    c = composition.build()
    c.repo.init_schema()
    now = c.clock.now()
    started = now.isoformat()

    policy.retire_stale(c.connection, now, c.settings)
    due = policy.select_due(c.connection, now, c.settings)

    collector = SnapshotCollector(c.youtube(), c.repo, c.clock)
    written = collector.collect_once(due) if due else 0
    policy.mark_sampled(c.connection, due, now)

    c.connection.execute(
        "INSERT INTO collection_runs (started_at, finished_at, kind, videos_touched, "
        "snapshots_written, ok) VALUES (?, ?, 'sample', ?, ?, 1)",
        (started, c.clock.now().isoformat(), len(due), written),
    )
    c.connection.commit()
    typer.echo(f"amostrados {len(due)} vídeos, {written} snapshots gravados.")


@app.command()
def detect() -> None:
    """Job offline: roda o detector sobre as trajetórias e grava as detecções."""
    from .engine_a.baseline import BaselineDetector
    from .engine_a.replay import run_detector

    c = composition.build()
    c.repo.init_schema()
    det = BaselineDetector()
    n = 0
    for vid in c.repo.video_ids():
        traj = c.repo.get_trajectory(vid)
        hit = run_detector(det, traj)
        if hit is not None:
            c.connection.execute(
                "INSERT OR REPLACE INTO detections (video_id, detector, at_hours, score, "
                "computed_at) VALUES (?, ?, ?, ?, ?)",
                (vid, hit.detector, hit.at_hours, hit.score, c.clock.now().isoformat()),
            )
            n += 1
    c.connection.commit()
    typer.echo(f"detecções gravadas: {n}.")


@app.command()
def dashboard() -> None:
    """Sobe o dashboard Streamlit (replay ao vivo do Motor A)."""
    import subprocess
    from importlib import resources

    path = resources.files("breakout").joinpath("dashboard.py")
    subprocess.run(["streamlit", "run", str(path)], check=False)


if __name__ == "__main__":
    app()
