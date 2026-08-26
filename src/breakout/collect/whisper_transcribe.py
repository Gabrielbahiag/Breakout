"""Adaptador fino sobre `faster-whisper` + `yt-dlp` — transcrição via Whisper.

Fallback da Fase 7 (`planning/transcricao-whisper.md`): só existe pro caso em
que o vídeo NÃO TEM legenda nenhuma (`transcript_api.py::fetch_transcript_text`
devolveu `None`). A legenda continua sendo sempre a primeira tentativa —
grátis, sem baixar mídia — este módulo só é chamado, e só é IMPORTADO, quando
`Settings.whisper_fallback_enabled` está ligado (ver `cli.py::_run_discover`)
E não havia legenda. Isso mantém o custo (dependências pesadas, tempo de
download+inferência) fora do caminho comum do `discover`.

`faster-whisper` (CTranslate2), não `openai-whisper`: evita a dependência de
`torch` — mais rápido em CPU, sem GPU disponível no GitHub Actions free tier.
Extra `[whisper]` (não `[prod]`): `yt-dlp` baixa só o ÁUDIO (nunca o vídeo
inteiro), o arquivo temporário é sempre apagado (nunca persiste mídia —
Princípio 1 do CLAUDE.md, snapshots são a única verdade append-only; áudio
baixado é lixo de processamento, não dado).

Best-effort por natureza, igual `transcript_api.py`/`youtube_api.py`: `None`
é a resposta normal pra qualquer falha (rede, vídeo indisponível, `yt-dlp`
quebrado por mudança do YouTube, modelo não carregou) — nunca levanta, nunca
derruba o `discover`.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

_model: Any = None


def _get_model(model_size: str) -> Any:
    """Carrega o modelo Whisper uma vez só (I/O e RAM caros) e reaproveita
    entre chamadas — nunca recriar por vídeo."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


def transcribe_via_whisper(video_id: str, *, model_size: str = "tiny") -> str | None:
    """Baixa só o áudio de `video_id` via `yt-dlp`, transcreve com
    `faster-whisper`, apaga o áudio. `None` se qualquer etapa falhar."""
    try:
        import yt_dlp

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_template = str(Path(tmp_dir) / f"{video_id}.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": out_template,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            audio_files = list(Path(tmp_dir).glob(f"{video_id}.*"))
            if not audio_files:
                return None

            model = _get_model(model_size)
            segments, _info = model.transcribe(str(audio_files[0]))
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return text or None
    except Exception:  # noqa: BLE001 — rede/yt-dlp/modelo são best-effort aqui
        return None
