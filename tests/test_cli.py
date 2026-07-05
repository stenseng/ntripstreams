#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for CLI argument parsing and NTRIP_* environment-variable fallbacks.

Priority for every option is: command line value > environment variable >
built-in default.
"""

import unittest
from unittest import mock

from ntripstreams.__main__ import parse_args

CASTER = "http://caster.example.net:2101"
ENV_CASTER = "http://env-caster.example.net:2101"


class TestCliEnvFallback(unittest.TestCase):
    def parse(self, argv, env=None):
        with mock.patch.dict("os.environ", env or {}, clear=True):
            return parse_args(argv)

    # --- url ---
    def test_url_from_command_line(self):
        self.assertEqual(self.parse([CASTER]).url, CASTER)

    def test_url_from_env(self):
        self.assertEqual(self.parse([], {"NTRIP_URL": ENV_CASTER}).url, ENV_CASTER)

    def test_command_line_url_overrules_env(self):
        args = self.parse([CASTER], {"NTRIP_URL": ENV_CASTER})
        self.assertEqual(args.url, CASTER)

    def test_missing_url_errors(self):
        with self.assertRaises(SystemExit):
            self.parse([])

    # --- mountpoint (append + comma-separated env) ---
    def test_mountpoint_from_env_comma_split(self):
        args = self.parse([], {"NTRIP_URL": ENV_CASTER, "NTRIP_MOUNTPOINT": "MP1, MP2"})
        self.assertEqual(args.mountpoint, ["MP1", "MP2"])

    def test_command_line_mountpoint_overrules_env(self):
        args = self.parse(
            [CASTER, "-m", "CLI1"],
            {"NTRIP_URL": ENV_CASTER, "NTRIP_MOUNTPOINT": "MP1,MP2"},
        )
        self.assertEqual(args.mountpoint, ["CLI1"])

    # --- user (same mechanism as passwd/logfile) ---
    def test_user_from_env(self):
        args = self.parse([CASTER], {"NTRIP_USER": "envuser"})
        self.assertEqual(args.user, "envuser")

    def test_command_line_user_overrules_env(self):
        args = self.parse([CASTER, "-u", "cliuser"], {"NTRIP_USER": "envuser"})
        self.assertEqual(args.user, "cliuser")

    def test_unset_option_defaults_to_none(self):
        # passwd/logfile share the env_default mechanism verified above for user.
        args = self.parse([CASTER])
        self.assertIsNone(args.user)
        self.assertIsNone(args.passwd)
        self.assertIsNone(args.logfile)

    # --- logfile ---
    def test_logfile_from_env(self):
        args = self.parse([CASTER], {"NTRIP_LOGFILE": "/tmp/ntrip.log"})
        self.assertEqual(args.logfile, "/tmp/ntrip.log")


if __name__ == "__main__":
    unittest.main()
