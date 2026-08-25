"""Adaptador fino sobre `youtube-transcript-api` — legendas do YouTube.

Decisão da Fase 5: transcrição via LEGENDA (auto-gerada ou manual), não via
Whisper. Baixar áudio/vídeo e rodar um modelo de transcrição pesado (precisa
de torch) seria lento e frágil demais pro GitHub Actions free tier — usar a
legenda que o YouTube já tem é ordens de magnitude mais leve: sem download de
mídia, sem modelo, e nem gasta cota da Data API (é um mecanismo totalmente
separado, não usa `YOUTUBE_API_KEY`).

Igual ao `youtube_api.py`: é o ÚNICO lugar que fala o dialeto dessa
biblioteca. Best-effort por natureza — nem todo vídeo tem legenda (Shorts
muito novos, principalmente), então `None` é uma resposta normal, não um erro.
"""
from __future__ import annotations

from youtube_transcript_api import YouTubeTranscriptApi


def fetch_transcript_text(video_id: str) -> str | None:
    """Texto concatenado da PRIMEIRA legenda disponível (qualquer idioma,
    manual ou auto-gerada — nesta ordem de preferência, é o que
    `TranscriptList` já prioriza). `None` se o vídeo não tem legenda
    nenhuma, ou se a busca falhar por qualquer motivo (rede, vídeo privado,
    biblioteca mudou de API, etc.) — nunca levanta. `except Exception` largo
    de propósito aqui: erro de terceiro (rede, parsing) não pode derrubar
    `discover`, e o "tipo certo" de exceção dessa lib mudou entre versões
    maiores no passado."""
    try:
        transcript_list = YouTubeTranscriptApi().list(video_id)
        transcript = next(iter(transcript_list), None)
        if transcript is None:
            return None
        fetched = transcript.fetch()
        text = " ".join(snippet.text for snippet in fetched).strip()
        return text or None
    except Exception:  # noqa: BLE001
        return None
