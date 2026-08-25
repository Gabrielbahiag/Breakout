"""Features de transcrição (legenda) — Motor B multimodal (Fase 5).

Heurísticas de texto simples (contagem de palavras, presença de pergunta,
etc.) — sem NLP pesado (embeddings, sentiment model): o texto já vem PRONTO
de `collect/transcript_api.py`, então isto é só extração de sinal barata,
mesmo estilo das features estáticas de título em `features.py`
(`title_has_number`, `title_has_question_mark`).

Como toda feature dinâmica/opcional do Motor B, nunca levanta: transcrição
ausente (vídeo sem legenda) só significa "sem essas features".
"""
from __future__ import annotations


def extract_transcript_features(transcript: str) -> dict[str, float]:
    """Extrai features do texto da transcrição. Dict com só
    `transcript_available=0.0` se `transcript` estiver vazio/ausente — as
    demais features não fazem sentido sem texto pra medir."""
    if not transcript:
        return {"transcript_available": 0.0}

    words = transcript.split()
    return {
        "transcript_available": 1.0,
        "transcript_word_count": float(len(words)),
        "transcript_has_question": float("?" in transcript),
        "transcript_has_exclamation": float("!" in transcript),
        "transcript_avg_word_length": float(sum(len(w) for w in words) / len(words)) if words else 0.0,
    }
