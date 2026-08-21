"""Teste de integração do pipeline — ponta a ponta, 100% offline.

Costura tudo: o FakeYouTubeClient serve uma trajetória (gerada pelo sintético),
o coletor tira snapshots carimbando com o ManualClock, o repositório reconstrói
a curva, e o detector baseline dispara. Nada toca a rede. É o menor "sistema
inteiro" que prova que as fronteiras encaixam.
"""
from __future__ import annotations

import pytest

from breakout.collect.snapshots import SnapshotCollector
from breakout.engine_a.baseline import BaselineDetector
from breakout.engine_a.metrics import lead_time_hours
from breakout.engine_a.replay import run_detector
from breakout.synth.trajectories import VIRAL_THRESHOLD_DEFAULT, make_trajectory
from breakout.types import Archetype

pytestmark = pytest.mark.integration


def test_pipeline_reconstroi_trajetoria_e_detecta(fake_youtube, repo, manual_clock):
    # 1. Programa a fronteira de rede com uma curva de rocket conhecida.
    truth_traj, _ = make_trajectory(Archetype.ROCKET, seed=11)
    fake_youtube.set_series("vid1", truth_traj.views.tolist())

    # 2. Coleta hora a hora, avançando o relógio E o fake em sincronia.
    collector = SnapshotCollector(fake_youtube, repo, manual_clock)
    for _ in range(len(truth_traj.views)):
        n = collector.collect_once(["vid1"])
        assert n == 1
        manual_clock.advance(hours=1)
        fake_youtube.tick()

    # 3. O repositório reconstrói a mesma curva.
    traj = repo.get_trajectory("vid1")
    assert traj.views.size == truth_traj.views.size
    assert traj.views.tolist() == truth_traj.views.tolist()

    # 4. O detector dispara e a métrica de lead time é computável.
    hit = run_detector(BaselineDetector(), traj)
    assert hit is not None
    lt = lead_time_hours(hit, traj, threshold=VIRAL_THRESHOLD_DEFAULT)
    assert lt is not None   # sinal: o pipeline entrega o número-chave do projeto


def test_video_deletado_some_da_coleta(fake_youtube, repo, manual_clock):
    fake_youtube.set_series("vivo", [1, 2, 3])
    fake_youtube.set_series("morto", [1, 2, 3])
    fake_youtube.deleted.add("morto")

    collector = SnapshotCollector(fake_youtube, repo, manual_clock)
    collector.collect_once(["vivo", "morto"])

    assert repo.video_ids() == ["vivo"]   # deletado não entra no storage
