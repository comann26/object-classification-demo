"""Task 16: `python -m demo.setup --variant <cpu|cu12x|mac>` (docs/design.md §4)."""

import sys
import types

import pytest

from demo import models, setup
from demo.models import CLIP, LARGE, SMALL, SetupError


@pytest.fixture
def ensured(monkeypatch):
    calls = []
    monkeypatch.setattr(models, "ensure", lambda root, names: calls.append(list(names)))
    return calls


def _fake_torch(monkeypatch, cuda: bool):
    torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: cuda))
    monkeypatch.setitem(sys.modules, "torch", torch)


def test_setup_cuda_unavailable_exits_3(monkeypatch, ensured, capsys):
    _fake_torch(monkeypatch, cuda=False)
    assert setup.main(["--variant", "cu12x"]) == 3
    assert capsys.readouterr().out.strip() == "NVIDIA GPU not usable — continuing on CPU"
    assert ensured == []  # no large-model download for a GPU we will not use


@pytest.mark.parametrize(
    ("variant", "machine", "needed"),
    [
        ("cpu", "AMD64", [SMALL, CLIP]),
        ("cu12x", "AMD64", [SMALL, CLIP, LARGE]),
        ("mac", "arm64", [SMALL, CLIP, LARGE]),
        ("mac", "x86_64", [SMALL, CLIP]),
    ],
)
def test_setup_models_for_variant(monkeypatch, ensured, variant, machine, needed):
    _fake_torch(monkeypatch, cuda=True)
    monkeypatch.setattr(setup.platform, "machine", lambda: machine)
    assert setup.main(["--variant", variant]) == 0
    assert ensured == [needed]


def test_setup_error_prints_message_only(monkeypatch, capsys):
    def offline(root, names):
        raise SetupError(models.OFFLINE_MESSAGE)

    monkeypatch.setattr(models, "ensure", offline)
    assert setup.main(["--variant", "cpu"]) == 2
    out = capsys.readouterr()
    assert (out.out + out.err).strip() == models.OFFLINE_MESSAGE
