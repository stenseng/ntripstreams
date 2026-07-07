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
import re
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


def format_bits(fmt):
    """Sum the bit width of a bitstring read format string (after _readfmt)."""
    total = 0
    for token in _readfmt(fmt).split(","):
        token = token.strip()
        match = re.search(r":(\d+)", token)
        if match:
            total += int(match.group(1))
        elif token == "bool":
            total += 1
    return total


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


class TestStationAndDescriptorMessages(unittest.TestCase):
    """Decode the stationary reference-station and descriptor messages."""

    @classmethod
    def setUpClass(cls):
        cls.rtcm = Rtcm3()
        cls.frames = {}  # message type -> decoded (head, sat, sig)
        for path in glob.glob(RAW_GLOB):
            for payload in iter_raw_frames(path):
                mt = payload.peek("uint:12")
                if (
                    mt in {1005, 1006, 1007, 1008, 1013, 1033, 1230}
                    and mt not in cls.frames
                ):
                    _, data = cls.rtcm.decodeRtcmMessage(payload)
                    cls.frames[mt] = (data, payload.len - payload.pos)

    def head(self, mt):
        self.assertIn(mt, self.frames, f"no captured {mt} frame")
        data, leftover = self.frames[mt]
        self.assertNotEqual(data[0], "Message type not implemented")
        self.assertTrue(0 <= leftover < 8, f"{mt} leftover {leftover} bits")
        return data

    def test_1005_arp_is_near_earth_surface(self):
        head = self.head(1005)[0]
        x, y, z = head[7], head[9], head[11]  # ECEF in 0.0001 m
        radius = (x**2 + y**2 + z**2) ** 0.5 * 1e-4
        self.assertTrue(6.3e6 < radius < 6.5e6, f"radius {radius:.0f} m off-Earth")

    def test_1006_has_antenna_height(self):
        head = self.head(1006)[0]
        self.assertEqual(len(head), 13)  # 1005 fields + antenna height

    def test_1007_antenna_descriptor_is_ascii(self):
        head = self.head(1007)[0]
        self.assertEqual(head[2], len(head[3]))  # counter matches string length
        self.assertTrue(head[3].isprintable())

    def test_1033_receiver_and_antenna_descriptors(self):
        head = self.head(1033)[0]
        # [type, refId, N, ant, setup, M, antSerial, I, rxType, J, rxFw, K, rxSerial]
        self.assertEqual(head[2], len(head[3]))  # antenna descriptor
        self.assertEqual(head[7], len(head[8]))  # receiver type descriptor
        self.assertTrue(head[8], "receiver type descriptor empty")

    def test_1013_announcements(self):
        head, sat, _ = self.head(1013)
        self.assertEqual(len(sat), head[4])  # Nm announcement sets
        for msgId, sync, interval in sat:
            self.assertTrue(1000 <= msgId <= 4095)

    def test_1230_bias_count_matches_mask(self):
        head, sat, _ = self.head(1230)
        self.assertEqual(len(sat), head[3].count("1"))


class TestLegacyRecordWidths(unittest.TestCase):
    """Per-satellite record widths must match the RTCM 10403.3 message tables.

    Guards the GLONASS field widths (DF041 = 25 bits, DF044 = 7 bits) whose
    two offsetting errors previously summed to the correct total, hiding a
    mis-alignment of the decoded L1 pseudorange/phaserange/lock/ambiguity.
    """

    # {constant suffix: (spec table, total bits per satellite record)}
    SPEC_BITS = {
        "1001Obs": 58,  # Table 3.5-2   GPS L1 basic
        "1002Obs": 74,  # Table 3.5-4   GPS L1 extended
        "1003Obs": 101,  # Table 3.5-6   GPS L1&L2 basic
        "1004Obs": 125,  # Table 3.5-8   GPS L1&L2 extended
        "1009Obs": 64,  # Table 3.5-11  GLONASS L1 basic
        "1010Obs": 79,  # Table 3.5-12  GLONASS L1 extended
        "1011Obs": 107,  # Table 3.5-13  GLONASS L1&L2 basic
        "1012Obs": 130,  # Table 3.5-14  GLONASS L1&L2 extended
    }

    def test_satellite_record_widths_match_spec(self):
        for suffix, expected in self.SPEC_BITS.items():
            fmt = getattr(Rtcm3, "_Rtcm3__msg" + suffix)
            self.assertEqual(
                format_bits(fmt), expected, f"{suffix} width != {expected} bits"
            )


if __name__ == "__main__":
    unittest.main()
