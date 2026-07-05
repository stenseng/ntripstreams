#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for NtripStream request-header construction (no network required)."""

import unittest

from ntripstreams.ntripstreams import NtripStream

URL = "http://caster.example.net:2101"


def header_lines(raw):
    return raw.decode("ISO-8859-1").split("\r\n")


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

    def test_nmea_string_is_crlf_terminated_and_encodable(self):
        # Regression: NMEA was previously encoded to bytes then concatenated
        # into a str header, raising TypeError.
        nmea = "$GPGGA,120000.00,5540.00,N,01230.00,E,1,08,1.0,50,M,45,M,,*60"
        ns = NtripStream()
        ns.setRequestStreamHeader(URL, "MOUNT1", "user", "pass", nmeaString=nmea)
        raw = ns.ntripRequestHeader  # must not raise
        self.assertIn(nmea, raw.decode("ISO-8859-1"))
        self.assertIn(nmea + "\r\n", raw.decode("ISO-8859-1"))


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

    def test_v1_source_request(self):
        ns = NtripStream()
        ns.setRequestServerHeader(URL, "MOUNT1", None, "pass", ntripVersion=1)
        first = header_lines(ns.ntripRequestHeader)[0]
        self.assertTrue(first.startswith("SOURCE "))
        self.assertIn("/MOUNT1 HTTP/1.1", first)

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


if __name__ == "__main__":
    unittest.main()
