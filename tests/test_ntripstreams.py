#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for NtripStream request-header construction and response parsing.

Validated against RTCM 10410.1 (NTRIP 2.0). No network access required; the
response-parsing tests drive the methods with a small in-memory fake reader.
"""

import asyncio
import unittest

from ntripstreams.ntripstreams import NtripStream

URL = "http://caster.example.net:2101"


def header_lines(raw):
    return raw.decode("ISO-8859-1").split("\r\n")


class FakeReader:
    """Minimal asyncio.StreamReader stand-in backed by a byte buffer."""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    async def readline(self):
        idx = self._data.find(b"\n", self._pos)
        end = len(self._data) if idx == -1 else idx + 1
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    async def readuntil(self, sep=b"\n"):
        idx = self._data.find(sep, self._pos)
        if idx == -1:
            raise asyncio.IncompleteReadError(self._data[self._pos :], None)
        end = idx + len(sep)
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    async def readexactly(self, n):
        if self._pos + n > len(self._data):
            raise asyncio.IncompleteReadError(self._data[self._pos :], n)
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk


class TestStreamHeader(unittest.TestCase):
    def test_basic_get_request(self):
        ns = NtripStream()
        ns.setRequestStreamHeader(URL, "MOUNT1")
        lines = header_lines(ns.ntripRequestHeader)
        self.assertEqual(lines[0], "GET /MOUNT1 HTTP/1.1")
        self.assertIn("Host: caster.example.net:2101", lines)
        self.assertIn("Ntrip-Version: Ntrip/2.0", lines)
        self.assertTrue(ns.ntripRequestHeader.endswith(b"\r\n\r\n"))

    def test_basic_auth_header_present(self):
        ns = NtripStream()
        ns.setRequestStreamHeader(URL, "MOUNT1", "user", "pass")
        # base64("user:pass") == "dXNlcjpwYXNz"
        self.assertIn(
            "Authorization: Basic dXNlcjpwYXNz", header_lines(ns.ntripRequestHeader)
        )

    def test_no_auth_when_credentials_missing(self):
        ns = NtripStream()
        ns.setRequestStreamHeader(URL, "MOUNT1")
        self.assertNotIn("Authorization", ns.ntripRequestHeader.decode("ISO-8859-1"))

    def test_nmea_sent_as_ntrip_gga_header(self):
        # NTRIP 2.0 (sec. 2.1.3): the position is sent as an Ntrip-GGA header
        # line, not as a bare NMEA line inside the header block.
        nmea = "$GPGGA,120000.00,5540.00,N,01230.00,E,1,08,1.0,50,M,45,M,,*60"
        ns = NtripStream()
        ns.setRequestStreamHeader(URL, "MOUNT1", "user", "pass", nmeaString=nmea)
        lines = header_lines(ns.ntripRequestHeader)
        self.assertIn(f"Ntrip-GGA: {nmea}", lines)
        # The bare sentence must not appear as its own (nameless) header line.
        self.assertNotIn(nmea, lines)


class TestServerHeader(unittest.TestCase):
    def test_v2_post_with_auth(self):
        ns = NtripStream()
        ns.setRequestServerHeader(URL, "MOUNT1", "user", "pass")
        lines = header_lines(ns.ntripRequestHeader)
        self.assertEqual(lines[0], "POST /MOUNT1 HTTP/1.1")
        self.assertIn("Authorization: Basic dXNlcjpwYXNz", lines)

    def test_v2_without_credentials_does_not_raise(self):
        # Regression: unbound ntripAuth previously raised NameError here.
        ns = NtripStream()
        ns.setRequestServerHeader(URL, "MOUNT1")
        self.assertTrue(ns.ntripRequestHeader.startswith(b"POST /MOUNT1"))

    def test_v1_source_request_uses_plaintext_password(self):
        ns = NtripStream()
        ns.setRequestServerHeader(URL, "MOUNT1", None, "pass", ntripVersion=1)
        raw = ns.ntripRequestHeader.decode("ISO-8859-1")
        # NTRIP 1.0 (sec. 2.2): plaintext password after SOURCE, not Base64.
        self.assertEqual(raw.split("\r\n")[0], "SOURCE pass /MOUNT1 HTTP/1.1")
        self.assertNotIn("cGFzcw==", raw)  # base64("pass") must not appear

    def test_v1_without_password_does_not_raise(self):
        ns = NtripStream()
        ns.setRequestServerHeader(URL, "MOUNT1", ntripVersion=1)
        self.assertTrue(ns.ntripRequestHeader.startswith(b"SOURCE "))


class TestSourcetableHeaderAndParsing(unittest.TestCase):
    def test_sourcetable_header(self):
        ns = NtripStream()
        ns.setRequestSourceTableHeader(URL)
        self.assertTrue(ns.ntripRequestHeader.startswith(b"GET / HTTP/1.1"))

    def test_get_header_strings_from_bytes_and_list(self):
        ns = NtripStream()
        as_bytes = ns.getHeaderStrings(b"HTTP/1.1 200 OK\r\nHost: x\r\n\r\n")
        self.assertEqual(as_bytes[0], "HTTP/1.1 200 OK")
        as_list = ns.getHeaderStrings([b"HTTP/1.1 200 OK\r\n", b"Host: x\r\n"])
        self.assertEqual(as_list, ["HTTP/1.1 200 OK", "Host: x"])


class TestResponseParsing(unittest.IsolatedAsyncioTestCase):
    async def test_http_status_code_parsed(self):
        ns = NtripStream()
        ns.ntripReader = FakeReader(b"HTTP/1.1 200 OK\r\nServer: x\r\n\r\n")
        await ns.getNtripResponseHeader()
        self.assertEqual(ns.ntripResponseStatusCode, "200")

    async def test_v1_server_ok_reply_is_success(self):
        # NTRIP 1.0 (sec. 2.2): a bare "OK" acknowledges a server upload.
        ns = NtripStream()
        ns.ntripReader = FakeReader(b"OK\r\n\r\n")
        await ns.getNtripResponseHeader()
        self.assertEqual(ns.ntripResponseStatusCode, "200")
        self.assertTrue(ns.ntripResponseStatusOk())

    async def test_chunked_detection(self):
        ns = NtripStream()
        ns.ntripReader = FakeReader(
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        )
        await ns.getNtripResponseHeader()
        self.assertTrue(ns.ntripStreamChunked)

    async def test_read_chunked_body_decodes_and_strips_extension(self):
        # RTCM 10410.1 sec. 2.4: hex size lines, optional ;extension, 0 ends.
        ns = NtripStream()
        ns.ntripReader = FakeReader(b"5\r\nHELLO\r\n6;ext\r\n WORLD\r\n0\r\n\r\n")
        self.assertEqual(await ns._readChunkedBody(), b"HELLO WORLD")


if __name__ == "__main__":
    unittest.main()
