"""Features de thumbnail via CV — Motor B multimodal (Fase 5).

Baixa a imagem da thumbnail e extrai um punhado de heurísticas visuais
clássicas (brilho, saturação, "colorfulness", densidade de bordas) — nada de
modelo pesado ou deep learning.

Nota: cogitamos incluir contagem de rostos, mas o `opencv-python` 5.x REMOVEU
o `CascadeClassifier` (Haar cascade) clássico — só sobrou `FaceDetectorYN`,
que exige baixar um modelo ONNX à parte. Isso contradiz o motivo de usarmos
legendas em vez de Whisper nesta mesma fase (evitar download de modelo
pesado), então deixamos rosto de fora por ora.

Como toda feature dinâmica do Motor B, isto é OPCIONAL e NUNCA levanta: URL
vazia, falha de rede, ou imagem corrompida só significam "sem essas
features" (dict vazio) — thumbnail é um bônus, nunca uma dependência dura do
pipeline (`features.py` decide o que fazer com o dict vazio).
"""
from __future__ import annotations

import cv2
import httpx
import numpy as np


def extract_thumbnail_features(thumbnail_url: str, *, timeout: float = 10.0) -> dict[str, float]:
    """Baixa `thumbnail_url` e extrai features visuais. Dict vazio se a URL
    estiver vazia, o download falhar, ou a imagem não puder ser decodificada."""
    if not thumbnail_url:
        return {}
    try:
        resp = httpx.get(thumbnail_url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        image = _decode_image(resp.content)
    except Exception:  # noqa: BLE001 — rede/decodificação são best-effort aqui
        return {}
    if image is None:
        return {}
    return _features_from_image(image)


def _decode_image(raw_bytes: bytes) -> np.ndarray | None:
    array = np.frombuffer(raw_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _features_from_image(image: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    brightness = float(gray.mean()) / 255.0
    saturation = float(hsv[:, :, 1].mean()) / 255.0

    # "Colorfulness" de Hasler & Süsstrunk (2003) — quão vibrante/variada é a
    # paleta, num espaço de cor oponente simples (RG / YB).
    b, g, r = (c.astype("float32") for c in cv2.split(image))
    rg = r - g
    yb = 0.5 * (r + g) - b
    colorfulness = float(
        np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    )

    edges = cv2.Canny(gray, 100, 200)
    edge_density = float((edges > 0).mean())

    return {
        "thumb_brightness": brightness,
        "thumb_saturation": saturation,
        "thumb_colorfulness": colorfulness,
        "thumb_edge_density": edge_density,
    }
