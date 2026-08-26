"""Disparo remoto de workflows do GitHub Actions (`workflow_dispatch`).

Adaptador fino sobre a API REST do GitHub, no mesmo espírito de
`youtube_api.py`/`transcript_api.py`: uma função PURA que monta a requisição
(`build_dispatch_request`, sem rede — testável sozinha) e uma função
best-effort que a executa (`trigger_workflow`, nunca levanta — mesmo padrão
de `fetch_transcript_text`).

Existe pro dashboard poder disparar `collect`/`discover` sem nunca escrever
direto no Turso (Seção 5 do CLAUDE.md, "dashboard read-only") — ele só pede
pro GitHub Actions fazer o trabalho, exatamente como um clique manual em
"Run workflow" já faz hoje.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

_API_BASE = "https://api.github.com"
_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class DispatchRequest:
    url: str
    headers: dict[str, str]
    json: dict[str, str]


def build_dispatch_request(
    *, token: str, owner: str, repo: str, workflow_file: str, ref: str = "main"
) -> DispatchRequest:
    """Monta a requisição de `workflow_dispatch` — sem tocar rede."""
    url = f"{_API_BASE}/repos/{owner}/{repo}/actions/workflows/{workflow_file}/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    return DispatchRequest(url=url, headers=headers, json={"ref": ref})


def trigger_workflow(
    *, token: str, owner: str, repo: str, workflow_file: str, ref: str = "main"
) -> tuple[bool, str]:
    """Dispara o workflow via API. Best-effort: nunca levanta, sempre devolve
    (sucesso, mensagem) — a API de dispatch só confirma enfileiramento, nunca
    o resultado do workflow em si."""
    if not token:
        return False, "Secret GITHUB_DISPATCH_TOKEN não configurado."

    req = build_dispatch_request(
        token=token, owner=owner, repo=repo, workflow_file=workflow_file, ref=ref
    )
    try:
        resp = httpx.post(req.url, headers=req.headers, json=req.json, timeout=_TIMEOUT_S)
    except httpx.HTTPError as exc:
        return False, f"Falha de rede ao disparar '{workflow_file}': {exc}"

    if resp.status_code == 204:
        return True, f"'{workflow_file}' enfileirado com sucesso no GitHub Actions."
    return False, f"GitHub respondeu {resp.status_code}: {resp.text[:200]}"
