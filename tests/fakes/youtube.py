"""FakeYouTubeClient — a fronteira de rede sob controle total.

Honra o Protocol `YouTubeClient`. Você PROGRAMA a série temporal de views de cada
vídeo e avança um ponteiro com `tick()` para simular a passagem do tempo. Também
registra chamadas (`.calls`) e simula vídeos deletados/privados — os casos de
borda que a implementação real vai ter que tratar.

Isto substitui a rede inteira: nenhum teste toca a API do Google.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from breakout.types import RawStats, VideoMetadata


class FakeYouTubeClient:
    def __init__(self) -> None:
        self._views: dict[str, list[int]] = {}
        self._likes: dict[str, list[int]] = {}
        self._ptr: dict[str, int] = defaultdict(int)
        self._meta: dict[str, VideoMetadata] = {}
        self.deleted: set[str] = set()
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    # ---- programação do fake (só nos testes) ----------------------------
    def set_series(self, video_id: str, views, likes=None) -> None:
        self._views[video_id] = [int(x) for x in views]
        self._likes[video_id] = [int(x) for x in (likes or [0] * len(views))]

    def set_metadata(self, metadata: VideoMetadata) -> None:
        self._meta[metadata.video_id] = metadata

    def tick(self) -> None:
        """Avança o tempo: o próximo fetch verá o ponto seguinte da série."""
        for vid, series in self._views.items():
            self._ptr[vid] = min(self._ptr[vid] + 1, len(series) - 1)

    # ---- interface YouTubeClient ---------------------------------------
    def search_recent(
        self,
        query: str,
        published_after: datetime,
        max_results: int = 50,
        language: str | None = None,
    ) -> list[str]:
        self.calls.append(("search_recent", (query, language)))
        return [v for v in self._views if v not in self.deleted][:max_results]

    def fetch_stats(self, video_ids: list[str]) -> list[RawStats]:
        self.calls.append(("fetch_stats", tuple(video_ids)))
        out: list[RawStats] = []
        for v in video_ids:
            if v in self.deleted or v not in self._views:
                continue  # vídeo deletado/privado some do resultado
            i = min(self._ptr[v], len(self._views[v]) - 1)
            out.append(RawStats(video_id=v, views=self._views[v][i], likes=self._likes[v][i]))
        return out

    def fetch_metadata(self, video_ids: list[str]) -> list[VideoMetadata]:
        self.calls.append(("fetch_metadata", tuple(video_ids)))
        return [self._meta[v] for v in video_ids if v in self._meta]
