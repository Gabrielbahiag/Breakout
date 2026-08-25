"""Contratos do sistema — os Protocols que definem as fronteiras.

Regra de ouro da camada de testes do Breakout:
    - Fronteira EXTERNA real (rede) -> MOCK.
    - Tudo que é dado/estado/algoritmo -> FAKE (implementação em memória).

Cada Protocol aqui é, ao mesmo tempo: (1) o alvo de um mock/fake e (2) um
contrato que a implementação real precisa honrar. Escrever o fake força a
fechar a interface — é assim que a arquitetura emerge dos testes.

Usamos typing.Protocol (structural typing) em vez de ABC: fakes e implementações
reais não precisam herdar de nada, só ter os métodos certos. `@runtime_checkable`
permite `isinstance(obj, Detector)` nos testes de contrato.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from .types import Detection, RawStats, Snapshot, Trajectory, VideoMetadata


@runtime_checkable
class Clock(Protocol):
    """Fonte de tempo injetável. Snapshots acontecem AO LONGO do tempo, então o
    tempo é uma dependência — nunca `datetime.now()` solto dentro do coletor."""

    def now(self) -> datetime: ...


@runtime_checkable
class YouTubeClient(Protocol):
    """Adaptador fino sobre a YouTube Data API. Mockamos ISTO, nunca o
    `google-api-python-client` cru (httplib2 é horrível de interceptar).

    A interface enxuta já expõe as funcionalidades da fronteira: busca de
    vídeos recentes, contagens ao vivo e metadados — com espaço para orçamento
    de cota, paginação e tratamento de vídeo deletado/privado nas implementações.
    """

    def search_recent(
        self, query: str, published_after: datetime, max_results: int = 50
    ) -> list[str]:
        """Devolve IDs de vídeos recentes (candidatos a entrar na coleta)."""
        ...

    def fetch_stats(self, video_ids: list[str]) -> list[RawStats]:
        """Contagens atuais (sem timestamp — quem carimba é o coletor)."""
        ...

    def fetch_metadata(self, video_ids: list[str]) -> list[VideoMetadata]:
        """Metadados quase-estáticos para o Motor B."""
        ...


@runtime_checkable
class TrajectoryRepository(Protocol):
    """Storage de trajetórias + metadados. Nos testes usamos um FAKE em memória
    (ou SQLite `:memory:` na integração), nunca o banco real."""

    def save_snapshot(self, snapshot: Snapshot) -> None: ...

    def save_metadata(self, metadata: VideoMetadata) -> None: ...

    def get_trajectory(self, video_id: str) -> Trajectory: ...

    def get_snapshots(self, video_id: str) -> list[Snapshot]:
        """Histórico bruto (com likes/comments), ordenado no tempo —
        `get_trajectory` só devolve views (o que o Motor A precisa); o Motor B
        usa isto pra engajamento inicial. Lista vazia se o vídeo não existe
        (diferente de `get_trajectory`, que levanta `KeyError`)."""
        ...

    def list_metadata(self) -> list[VideoMetadata]:
        """Metadados de TODOS os vídeos com metadata salva, numa query só —
        não toca em `snapshots`. Usado pelo dashboard pra popular o seletor
        por título sem N+1 round-trips contra o Turso remoto (o mesmo custo
        que `save_snapshot` já paga por chamada)."""
        ...

    def video_peak_views(self) -> dict[str, int]:
        """video_id -> maior contagem de views já registrada, numa query
        agregada só. Usado pelo dashboard pra destacar/filtrar vídeos virais
        sem carregar a trajetória inteira de cada um (mesmo motivo de
        `list_metadata`)."""
        ...

    def video_ids(self) -> list[str]: ...


@runtime_checkable
class Detector(Protocol):
    """Detector ONLINE de decolagem. Consome a série ponto-a-ponto (streaming) e
    devolve uma Detection quando dispara, ou None. `reset()` reinicia o estado
    para reprocessar outra trajetória.

    Este é o contrato do coração do Motor A: baseline, CUSUM, Kleinberg e BOCPD
    são todos implementações intercambiáveis deste mesmo Protocol — é o que
    torna possível o 'bake-off' de detectores na mesma bateria de curvas.
    """

    name: str

    def update(self, t_hours: float, views: float) -> Detection | None: ...

    def reset(self) -> None: ...
