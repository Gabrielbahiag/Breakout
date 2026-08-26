"""Features de thumbnail via CV — Motor B multimodal (Fase 5 + Fase 7).

Baixa a imagem da thumbnail e extrai um punhado de heurísticas visuais
clássicas (brilho, saturação, "colorfulness", densidade de bordas) mais
contagem de rostos via rede neural leve (YuNet, Fase 7).

Nota histórica: a Fase 5 cogitou incluir contagem de rostos, mas descartou
porque o `opencv-python` 5.x removeu o `CascadeClassifier` (Haar cascade)
clássico — só sobrou `FaceDetectorYN`, que exige um modelo `.onnx` à parte, o
que na época pareceu contradizer a decisão de evitar download pesado de
modelo (mesmo motivo de usar legenda em vez de Whisper). Correção feita na
Fase 7: o modelo YuNet é pequeno (~230KB, nada comparável a Whisper) e vem
empacotado no repo como package data (`models/face_detection_yunet.onnx`,
licença MIT — ver `models/FACE_DETECTION_YUNET_LICENSE.txt`), carregado uma
vez (singleton em nível de módulo) e nunca baixado em runtime.

Como toda feature dinâmica do Motor B, isto é OPCIONAL e NUNCA levanta: URL
vazia, falha de rede, ou imagem corrompida só significam "sem essas
features" (dict vazio) — thumbnail é um bônus, nunca uma dependência dura do
pipeline (`features.py` decide o que fazer com o dict vazio).
"""
from __future__ import annotations

from importlib import resources

import cv2
import httpx
import numpy as np

_face_detector: cv2.FaceDetectorYN | None = None


def _get_face_detector(input_size: tuple[int, int]) -> cv2.FaceDetectorYN:
    """Carrega o detector uma vez (I/O de modelo é caro) e reajusta só o
    tamanho de entrada — nunca recria a instância por imagem."""
    global _face_detector
    if _face_detector is None:
        model_path = resources.files("breakout.engine_b.models").joinpath(
            "face_detection_yunet.onnx"
        )
        with resources.as_file(model_path) as path:
            _face_detector = cv2.FaceDetectorYN.create(str(path), "", input_size)
    _face_detector.setInputSize(input_size)
    return _face_detector


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

    height, width = image.shape[:2]
    detector = _get_face_detector((width, height))
    _, faces = detector.detect(image)
    face_count = 0.0 if faces is None else float(len(faces))

    return {
        "thumb_brightness": brightness,
        "thumb_saturation": saturation,
        "thumb_colorfulness": colorfulness,
        "thumb_edge_density": edge_density,
        "thumb_face_count": face_count,
    }
