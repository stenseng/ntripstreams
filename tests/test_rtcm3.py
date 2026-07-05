#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the Rtcm3 decoder.

The fixtures under ``tests/data`` are real frames captured from the public
rtk2go.com caster, covering RTCM 3.0, 3.2 and 3.3 mountpoints:

* ``rtcm3_samples.json`` -- one representative frame (hex) per message type,
  with the expected message type as the key.
* ``samples/*.rtcm3``    -- the raw ~2 minute captures, used to exercise the
  decoder across many frames and varying satellite counts.
"""

import glob
import json
import os
import unittest

from bitstring import BitStream

from ntripstreams.rtcm3 import Rtcm3, _readfmt

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SAMPLES_JSON = os.path.join(DATA_DIR, "rtcm3_samples.json")
RAW_GLOB = os.path.join(DATA_DIR, "samples", "*.rtcm3")

# Message types the decoder parses field-by-field (the rest are recognised but
# fall through to "not implemented").
LEGACY = set(range(1001, 1005)) | set(range(1009, 1013))
MSM = set(range(1071, 1128))


def iter_raw_frames(path):
    """Yield each RTCM3 frame payload BitStream from a raw capture file."""
    raw = open(path, "rb").read()
    i = 0
    while i < len(raw):
        if raw[i] != 0xD3:
            i += 1
            continue
        if i + 3 > len(raw):
            break
        length = ((raw[i + 1] & 0x03) << 8) | raw[i + 2]
        flen = 3 + length + 3
        if i + flen > len(raw):
            break
        yield BitStream(raw[i + 3 : i + 3 + length])
        i += flen


class TestReadFmt(unittest.TestCase):
    def test_strips_name_labels(self):
        self.assertEqual(_readfmt("uint:12=messageType"), "uint:12")

    def test_strips_value_assertions(self):
        self.assertEqual(_readfmt("uint:12=1004"), "uint:12")

    def test_leaves_plain_tokens(self):
        self.assertEqual(_readfmt("uint:12, pad:6, bool"), "uint:12, pad:6, bool")


class TestSampleFrames(unittest.TestCase):
    """Decode one representative frame of every captured message type."""

    @classmethod
    def setUpClass(cls):
        with open(SAMPLES_JSON) as fh:
            cls.fixture = json.load(fh)
        cls.rtcm = Rtcm3()

    def test_message_type_matches_fixture_key(self):
        checked = 0
        for mount, d in self.fixture.items():
            for mt_str, hexstr in d["sample_frames_hex"].items():
                frame = BitStream(bytes.fromhex(hexstr))
                mtype, data = self.rtcm.decodeRtcmFrame(frame)
                self.assertEqual(
                    mtype, int(mt_str), f"{mount} type {mt_str} decoded as {mtype}"
                )
                checked += 1
        self.assertGreater(checked, 20)

    def test_description_known_for_all_types(self):
        for d in self.fixture.values():
            for mt_str in d["sample_frames_hex"]:
                desc = self.rtcm.messageDescription(int(mt_str))
                self.assertNotIn("not implemented", desc)

    def test_msm_constellation_and_signals(self):
        for d in self.fixture.values():
            for mt_str, hexstr in d["sample_frames_hex"].items():
                mtype = int(mt_str)
                if mtype not in MSM:
                    continue
                _, data = self.rtcm.decodeRtcmFrame(BitStream(bytes.fromhex(hexstr)))
                self.assertIn(
                    self.rtcm.constellation(mtype),
                    {"GPS", "GLONASS", "GALILEO", "SBAS", "QZSS", "BEIDOU"},
                )
                signals = self.rtcm.msmSignalTypes(mtype, data[0][10])
                self.assertIsInstance(signals, list)


class TestRawCaptures(unittest.TestCase):
    """Every frame in the raw captures decodes without error."""

    @classmethod
    def setUpClass(cls):
        cls.rtcm = Rtcm3()
        cls.files = sorted(glob.glob(RAW_GLOB))

    def test_fixture_files_present(self):
        self.assertTrue(self.files, "no raw capture fixtures found")

    def test_all_frames_decode(self):
        total = 0
        for path in self.files:
            for payload in iter_raw_frames(path):
                mtype = payload.peek("uint:12")
                self.rtcm.decodeRtcmMessage(payload)
                total += 1
                # Legacy observables are fully field-parsed, so they must
                # consume the payload up to at most 7 bits of RTCM
                # byte-alignment padding. (MSM decoding is not exhaustive and
                # legitimately leaves a larger remainder.)
                if mtype in LEGACY:
                    leftover = payload.len - payload.pos
                    self.assertTrue(
                        0 <= leftover < 8,
                        f"{os.path.basename(path)} type {mtype} "
                        f"leftover {leftover} bits",
                    )
        self.assertGreater(total, 100)


if __name__ == "__main__":
    unittest.main()
