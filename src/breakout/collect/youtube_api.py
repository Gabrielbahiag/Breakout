"""Adaptador real da YouTube Data API — a implementação de produção do contrato
`YouTubeClient`. É o ÚNICO lugar que fala o dialeto do Google; o resto do sistema
só conhece o Protocol.

Importa o cliente do Google de forma preguiçosa (dentro dos métodos) para que a
suíte de testes — que usa o FakeYouTubeClient — nunca precise da dependência.

Custos de cota (2026): search.list = 100 unidades; videos.list = 1 unidade e
aceita lote de 50 IDs. Por isso descobrir é caro e amostrar é barato.
"""
from __future__ import annotations

from datetime import datetime

from ..types import RawStats, VideoMetadata


class QuotaExceeded(RuntimeError):
    """403 quotaExceeded — a cota diária acabou. Pare até o reset (meia-noite PT)."""


class RateLimited(RuntimeError):
    """429 rateLimitExceeded — limite por minuto. Faça backoff e tente de novo."""


def _iso8601_duration_to_seconds(dur: str) -> int:
    # PT1M30S -> 90. Implementação mínima; robustez fica p/ a fase de features.
    import re

    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


class YouTubeApiClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._svc = None

    def _service(self):
        if self._svc is None:
            from googleapiclient.discovery import build  # import preguiçoso

            self._svc = build("youtube", "v3", developerKey=self._api_key, cache_discovery=False)
        return self._svc

    def _raise_for_quota(self, error) -> None:
        from googleapiclient.errors import HttpError

        if isinstance(error, HttpError):
            status = getattr(error.resp, "status", None)
            reason = str(error)
            if status == 403 and "quota" in reason.lower():
                raise QuotaExceeded(reason) from error
            if status == 429 or "rateLimit" in reason:
                raise RateLimited(reason) from error
        raise error

    def search_recent(self, query: str, published_after: datetime, max_results: int = 50) -> list[str]:
        try:
            resp = (
                self._service()
                .search()
                .list(
                    q=query,
                    part="id",
                    type="video",
                    order="date",
                    publishedAfter=published_after.isoformat().replace("+00:00", "Z"),
                    maxResults=min(max_results, 50),
                )
                .execute()
            )
        except Exception as e:  # noqa: BLE001 — reclassifica p/ quota/rate
            self._raise_for_quota(e)
            raise
        return [item["id"]["videoId"] for item in resp.get("items", []) if item["id"].get("videoId")]

    def fetch_stats(self, video_ids: list[str]) -> list[RawStats]:
        out: list[RawStats] = []
        for i in range(0, len(video_ids), 50):          # lote de 50 = 1 unidade
            chunk = video_ids[i : i + 50]
            try:
                resp = (
                    self._service()
                    .videos()
                    .list(part="statistics", id=",".join(chunk))
                    .execute()
                )
            except Exception as e:  # noqa: BLE001
                self._raise_for_quota(e)
                raise
            for item in resp.get("items", []):
                st = item.get("statistics", {})
                out.append(
                    RawStats(
                        video_id=item["id"],
                        views=int(st.get("viewCount", 0)),
                        likes=int(st.get("likeCount", 0)),
                        comments=int(st.get("commentCount", 0)),
                    )
                )
        return out

    def fetch_metadata(self, video_ids: list[str]) -> list[VideoMetadata]:
        out: list[VideoMetadata] = []
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            try:
                resp = (
                    self._service()
                    .videos()
                    .list(part="snippet,contentDetails", id=",".join(chunk))
                    .execute()
                )
            except Exception as e:  # noqa: BLE001
                self._raise_for_quota(e)
                raise
            for item in resp.get("items", []):
                sn = item.get("snippet", {})
                cd = item.get("contentDetails", {})
                out.append(
                    VideoMetadata(
                        video_id=item["id"],
                        channel_id=sn.get("channelId", ""),
                        title=sn.get("title", ""),
                        duration_s=_iso8601_duration_to_seconds(cd.get("duration", "")),
                        published_at=datetime.fromisoformat(
                            sn.get("publishedAt", "").replace("Z", "+00:00")
                        ),
                        tags=tuple(sn.get("tags", []) or ()),
                        category=sn.get("categoryId", "unknown"),
                    )
                )
        return out
