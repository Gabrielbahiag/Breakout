"""Testes de extração de features de thumbnail (thumbnail.py).

Mocka a fronteira externa real (o download HTTP via respx — Princípio 3 do
CLAUDE.md: mockar só a rede, nunca o código interno). As imagens de teste são
geradas na hora (preto/branco/colorida) via cv2.imencode, sem depender de
nenhum arquivo externo.
"""
from __future__ import annotations

import cv2
import httpx
import numpy as np
import pytest
import respx

from breakout.engine_b.thumbnail import extract_thumbnail_features

pytestmark = pytest.mark.unit

URL = "https://i.ytimg.com/vi/abc123/hqdefault.jpg"


def _jpeg_bytes(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", image)
    assert ok
    return buf.tobytes()


def test_url_vazia_devolve_dict_vazio():
    assert extract_thumbnail_features("") == {}


@respx.mock
def test_falha_de_rede_devolve_dict_vazio():
    respx.get(URL).mock(return_value=httpx.Response(404))
    assert extract_thumbnail_features(URL) == {}


@respx.mock
def test_bytes_invalidos_nao_decodificam_devolve_dict_vazio():
    respx.get(URL).mock(return_value=httpx.Response(200, content=b"isso nao e uma imagem"))
    assert extract_thumbnail_features(URL) == {}


@respx.mock
def test_imagem_preta_tem_brilho_baixo_e_poucas_bordas():
    black = np.zeros((120, 120, 3), dtype=np.uint8)
    respx.get(URL).mock(return_value=httpx.Response(200, content=_jpeg_bytes(black)))
    feats = extract_thumbnail_features(URL)
    assert feats["thumb_brightness"] < 0.05
    assert feats["thumb_edge_density"] < 0.05


@respx.mock
def test_imagem_branca_tem_brilho_alto():
    white = np.full((120, 120, 3), 255, dtype=np.uint8)
    respx.get(URL).mock(return_value=httpx.Response(200, content=_jpeg_bytes(white)))
    feats = extract_thumbnail_features(URL)
    assert feats["thumb_brightness"] > 0.9


@respx.mock
def test_todas_as_features_esperadas_presentes():
    img = np.random.default_rng(0).integers(0, 255, size=(120, 120, 3), dtype=np.uint8)
    respx.get(URL).mock(return_value=httpx.Response(200, content=_jpeg_bytes(img)))
    feats = extract_thumbnail_features(URL)
    assert set(feats) == {
        "thumb_brightness",
        "thumb_saturation",
        "thumb_colorfulness",
        "thumb_edge_density",
    }
    assert 0.0 <= feats["thumb_brightness"] <= 1.0
    assert 0.0 <= feats["thumb_saturation"] <= 1.0
    assert 0.0 <= feats["thumb_edge_density"] <= 1.0
