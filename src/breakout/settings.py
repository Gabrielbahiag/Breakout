"""Configuração central via pydantic-settings.

Lê de variáveis de ambiente (ou de um .env local em dev). Em produção, os valores
sensíveis vêm dos Secrets do GitHub Actions e do Streamlit — nunca do disco da
máquina do trabalho. Um campo vazio de Turso => cai pro SQLite local.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- credenciais (Secrets em produção) ---
    youtube_api_key: str = ""
    turso_database_url: str = ""     # vazio => usa SQLite local
    turso_auth_token: str = ""
    github_dispatch_token: str = ""  # vazio => botões de disparo no dashboard ficam desabilitados

    # --- repo alvo do disparo remoto (não é segredo, é config de produto) ---
    github_owner: str = "Gabrielbahiag"
    github_repo: str = "Breakout"

    # --- fallback de transcrição via Whisper (Fase 7) ---
    # desligado por padrão: legenda do YouTube é sempre a primeira tentativa
    # (grátis, sem download de mídia); Whisper só roda quando habilitado
    # explicitamente E não há legenda nenhuma (ver cli.py::_run_discover).
    whisper_fallback_enabled: bool = False

    # --- storage local (dev) ---
    local_db_path: str = "data/breakout.db"

    # --- política de cadência (substitui o APScheduler) ---
    hot_interval_h: float = 1.0      # vídeo jovem/quente: amostra de hora em hora
    cold_interval_h: float = 6.0     # vídeo frio: amostra a cada 6h
    hot_age_h: float = 24.0          # até esta idade, é considerado "quente"
    retire_after_h: float = 168.0    # aposenta da carteira após 7 dias

    # --- orçamento de cota ---
    daily_quota_units: int = 10_000
    max_search_calls_per_run: int = 5   # search.list custa 100 unidades cada


def load_settings() -> Settings:
    return Settings()
