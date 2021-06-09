#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  9 09:33:07 2021

@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import unittest

from bitstring import BitStream
from ntripstreams.crc import crc24q, crcNmea, genLookup


class TestCrcFunctions(unittest.TestCase):

    def test_crcNmea(self):
        nmeaStr = (
            "$GPGGA,092751.000,5321.6802,N,00630.3371,W,1,8,1.03,61.7,M,55.3,M,,*75"
        )
        nmeaBits = BitStream(nmeaStr[1:-3].encode())
        nmeaCrcBits = BitStream("0x" + nmeaStr[-2:])
        self.assertEqual(crcNmea(nmeaBits), BitStream(nmeaCrcBits))

    def test_crc24q(self):
        rtcmBits = BitStream("0xD300133ED7D30202980EDEEF34B4BD62AC0941986F33360B98")
        rtcmCrcBits = rtcmBits[-24:].unpack("uint:24")[0]
        self.assertEqual(crc24q(rtcmBits[:-24]), rtcmCrcBits)

    def test_genLookup(self):
        remTab = genLookup()
        self.assertEqual(remTab[0], 0x000000)
        self.assertEqual(remTab[1], 0x864CFB)
        self.assertEqual(remTab[-2], 0x5BC9C3)
        self.assertEqual(remTab[-1], 0xDD8538)
