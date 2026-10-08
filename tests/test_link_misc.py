"""Enlaces de emparejamiento, WAV, detector de voz y almacen de tokens."""

from __future__ import annotations

import math
import os
import stat
from array import array

import pytest
from gmini_link.pairlink import PairInfo, normalize_base_url, parse_pair_input
from gmini_link.tokens import Credentials, TokenStore
from gmini_link.vad import EnergyVad, VadEvent
from gmini_link.wav import Pcm, decode_wav, encode_wav, level, resample, split_levels, tone


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("482913", PairInfo("482913")),
        (" 482 913 ", PairInfo("482913")),
        ("482-913", PairInfo("482913")),
        ("gmini://pair?host=100.64.0.10&port=8765&code=482913", PairInfo("482913", "100.64.0.10", 8765)),
        ("GMINI://pair?code=111222&host=tv-server", PairInfo("111222", "tv-server", 0)),
    ],
)
def test_parse_pair_input(text: str, expected: PairInfo) -> None:
    assert parse_pair_input(text) == expected


@pytest.mark.parametrize("text", ["48291", "4829134", "abc123", "gmini://pair?code=12", "gmini://x?code=123456",
                                  "gmini://pair?code=123456&port=99999", "gmini://pair?code=123456&host=a b"])
def test_parse_pair_input_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_pair_input(text)


def test_normalize_base_url() -> None:
    assert normalize_base_url("192.168.1.20") == "http://192.168.1.20:8765"
    assert normalize_base_url("tv-server:9000/") == "http://tv-server:9000"
    assert normalize_base_url("https://gmini.example.com") == "https://gmini.example.com"
    assert normalize_base_url("http://h:80") == "http://h"
    assert PairInfo("123456", "tv-server").base_url == "http://tv-server:8765"
    for bad in ("", "ftp://x", "http://ho st"):
        with pytest.raises(ValueError):
            normalize_base_url(bad)


def test_wav_roundtrip_resample_and_levels() -> None:
    pcm = tone(440, 300, rate=16000)
    wav = encode_wav(pcm)
    back = decode_wav(wav)
    assert back == Pcm(pcm, 16000, 1)
    assert back.seconds == pytest.approx(0.3, abs=0.001)
    up = resample(Pcm(tone(440, 300, rate=22050), 22050, 1), 16000)
    assert up.rate == 16000 and abs(up.frames - 4800) <= 2
    assert 0.6 < level(pcm) <= 1.0
    assert level(b"\x00\x00" * 320) == 0.0
    levels = split_levels(back, 40)
    assert len(levels) == 8 and all(0 <= v <= 1 for v in levels)
    with pytest.raises(ValueError):
        decode_wav(b"no es un wav")


def _block(amp: int, n: int = 320, phase: int = 0) -> bytes:
    return array("h", (int(amp * math.sin((phase + i) * 0.05)) for i in range(n))).tobytes()


def test_vad_start_end() -> None:
    vad = EnergyVad(16000)
    events = [vad.feed(_block(40)) for _ in range(50)]
    assert set(events) == {VadEvent.NONE}
    events = [vad.feed(_block(4000, phase=i * 320)) for i in range(40)]
    assert events.count(VadEvent.SPEECH_START) == 1 and vad.in_speech
    events = [vad.feed(_block(40)) for _ in range(50)]
    assert events.count(VadEvent.SPEECH_END) == 1 and not vad.in_speech


def test_token_store_file_backend(tmp_path) -> None:
    store = TokenStore("pruebas", path=tmp_path / "credentials.json", use_keyring=False)
    assert store.load("http://a:8765") is None
    creds = Credentials(base_url="http://a:8765", token="gm_dev_1", device_id="dev_1", agent_name="G-Mini")
    store.save(creds)
    store.save(Credentials(base_url="http://b:8765", token="gm_dev_2"))
    assert store.load("http://a:8765") == creds
    assert store.last().token == "gm_dev_2"
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(store.path).st_mode) == 0o600
    assert store.delete("http://a:8765") and store.load("http://a:8765") is None
    other_app = TokenStore("otra", path=tmp_path / "credentials.json", use_keyring=False)
    assert other_app.load("http://b:8765") is None
