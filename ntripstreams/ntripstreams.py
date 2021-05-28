#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
from urllib.parse import urlsplit
from base64 import b64encode
from time import time, strftime, gmtime
from bitstring import Bits, BitStream
from crc import crc24q
from rtcm3 import rtcm3

from __version__ import __version__


class NtripStream:

    def __init__(self):
        self.__CLIENTVERSION = __version__
        self.__CLIENTNAME = ('Bedrock Solutions NtripClient/'
                             + f'{self.__CLIENTVERSION}')
        self.casterUrl = None
        self.ntripVersion = 2
        self.ntripMountPoint = None
        self.ntripAuthStr = ''
        self.nmeaStr = ''
        self.ntripWriter = None
        self.ntripReader = None
        self.rtcmFrameBuffer = BitStream()
        self.rtcmMessage = rtcm3()

    async def openNtripConnection(self, casterUrl: str):
        """
        Connects to a caste with url http[s]://caster.hostename.net:port
        """
        self.casterUrl = urlsplit(casterUrl)
        if self.casterUrl.scheme == 'https':
            self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                self.casterUrl.hostname, self.casterUrl.port, ssl=True)
        else:
            self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                self.casterUrl.hostname, self.casterUrl.port)
        return

    def getSourceTableHeader(self, casterUrl: str) -> str:
        self.casterUrl = urlsplit(casterUrl)
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        header = (f'GET / HTTP/1.1\r\n'
                  f'Host: {self.casterUrl.geturl()}\r\n'
                  f'Ntrip-Version: Ntrip/{self.ntripVersion}.0\r\n'
                  f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                  f'Date: {timestamp}\r\n'
                  f'Connection: close\r\n'
                  f'\r\n').encode('ISO-8859-1')
        return header

    def getNtripStreamHeader(self, casterUrl: str, ntripMountPoint: str,
                             ntripUser: str = None, ntripPassword: str = None,
                             nmeaStr: str = None) -> str:
        self.casterUrl = urlsplit(casterUrl)
        self.ntripMountPoint = ntripMountPoint
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        if nmeaStr:
            self.nmeaStr = nmeaStr.encode('ISO-8859-1')
        if ntripUser and ntripPassword:
            ntripAuth = b64encode((ntripUser + ':' +
                                   ntripPassword).encode('ISO-8859-1')
                                  ).decode()
            self.ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
        header = (f'GET /{ntripMountPoint} HTTP/1.1\r\n'
                  f'Host: {self.casterUrl.geturl()}\r\n'
                  f'Ntrip-Version: Ntrip/{self.ntripVersion}.0\r\n'
                  f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                  + self.ntripAuthStr
                  + self.nmeaStr +
                  f'Date: {timestamp}\r\n'
                  'Connection: close\r\n'
                  '\r\n').encode('ISO-8859-1')
        return header

    def getServerHeader(self, casterUrl: str, ntripMountPoint: str,
                        ntripUser: str = None, ntripPassword: str = None,
                        ntripVersion: int = 2) -> str:
        self.casterUrl = urlsplit(casterUrl)
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())

        if ntripVersion >= 2.0:
            ntripAuth = b64encode((ntripUser + ':' +
                                   ntripPassword).encode('ISO-8859-1')
                                  ).decode()
            self.ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
            header = (f'POST /{ntripMountPoint} HTTP/1.1\r\n'
                      f'Host: {self.casterUrl.geturl()}\r\n'
                      f'Ntrip-Version: Ntrip/{self.ntripVersion}.0\r\n'
                      + self.ntripAuthStr +
                      f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                      f'Date: {timestamp}\r\n'
                      'Connection: close\r\n'
                      '\r\n').encode('ISO-8859-1')
        elif ntripVersion == 1.0:
            ntripAuth = b64encode(ntripPassword.encode('ISO-8859-1')).decode()
            header = (f'SOURCE {ntripAuth} /{ntripMountPoint} '
                      'HTTP/1.1\r\n'
                      f'Source-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                      '\r\n').encode('ISO-8859-1')
        return header

    async def getNtripResponceHeader(self):
        ntripResponceHeader = []
        ntripResponceHeaderTimestamp = []
        endOfHeader = False
        while True:
            line = await self.ntripReader.readline()
            ntripResponceHeaderTimestamp.append(time())
            if not line:
                break
            line = line.decode('ISO-8859-1').rstrip()
            if line == '':
                endOfHeader = True
                break
            if not endOfHeader:
                ntripResponceHeader.append(line)
        ntripStatusCode = ntripResponceHeader[0].split(' ')[1]
        return ntripResponceHeader, ntripStatusCode, \
            ntripResponceHeaderTimestamp

    async def getNtripSourcetable(self, casterUrl: str):
        await self.openNtripConnection(casterUrl)
        print(f'{time():.6f}: Connection open. Ready to write.')
        header = self.getSourceTableHeader(self.casterUrl.geturl())
        for line in header.decode().split('\r\n'):
            print(f'{time():.6f}: Request header > {line}')
        self.ntripWriter.write(header)
        await self.ntripWriter.drain()
        print(f'{time():.6f}: Header sent.')

        ntripResponceSourcetable = []
        ntripResponceHeader, ntripStatusCode, ntripResponceHeaderTimestamp \
            = await self.getNtripResponceHeader()
        if ntripStatusCode != '200':
            print(f'Error! {ntripStatusCode}')
            for line in ntripResponceHeader:
                print(line)
            self.ntripWriter.close()
        while True:
            line = await self.ntripReader.readline()
            if not line:
                break
            line = line.decode('ISO-8859-1').rstrip()
            if line == 'ENDSOURCETABLE':
                ntripResponceSourcetable.append(line)
                self.ntripWriter.close()
                print(f'{time():.6f}: Sourcetabel received.')
                break
            else:
                print(f'{time():.6f}: Sourcetable > {line}')
                ntripResponceSourcetable.append(line)
        return ntripResponceSourcetable, ntripStatusCode, ntripResponceHeader

    async def getNtripStream(self, casterUrl: str, mountPoint: str,
                             user: str = None, passwd: str = None):
        await self.openNtripConnection(casterUrl)
        self.ntripMountPoint = mountPoint
        print(f'{time():.6f}: Connection open. Ready to write.')
        header = self.getNtripStreamHeader(self.casterUrl.geturl(),
                                           self.ntripMountPoint,
                                           user, passwd)
        self.ntripWriter.write(header)
        await self.ntripWriter.drain()
        print(f'{time():.6f}: Header sent.')
        ntripResponceHeader, ntripStatusCode, ntripResponceHeaderTimestamp \
            = await self.getNtripResponceHeader()

        rtcm3FramePreample = Bits(bin='0b11010011')
        rtcm3FrameHeader = 'bin:8, pad:6, uint:10'

        if ntripStatusCode == '200':
            if 'Transfer-Encoding: chunked' in ntripResponceHeader:
                print('Stream is chunked')
                ntripStreamChunked = True
            else:
                ntripStreamChunked = False
            rtcmFramePreample = False
            rtcmFrameAligned = False
            while True:
                if ntripStreamChunked:
                    rawLine = await self.ntripReader.readuntil(b'\r\n')
                    length = int(rawLine[:-2].decode('ISO-8859-1'), 16)
                rawLine = await self.ntripReader.readuntil(b'\r\n')
                receivedBytes = BitStream(rawLine[:-2])
                if ntripStreamChunked and receivedBytes.length != length * 8:
                    print('Chunk incomplete.\n Closing connection!')
                    print(f'{time():.6f}: '
                          f'Chunk {receivedBytes.length}:{length * 8}')
                    break

                self.rtcmFrameBuffer += receivedBytes
                if not rtcmFrameAligned:
                    rtcmFramePos = self.rtcmFrameBuffer.find(
                        rtcm3FramePreample, bytealigned=True)
                    if rtcmFramePos:
                        self.rtcmFrameBuffer \
                            = self.rtcmFrameBuffer[rtcmFramePos[0]:]
                        rtcmFramePreample = True
                    else:
                        self.rtcmFrameBuffer = BitStream()
                if rtcmFramePreample and self.rtcmFrameBuffer.length >= 48:
                    (rtcmPreAmple, rtcmPayloadLength) \
                        = self.rtcmFrameBuffer.peeklist(rtcm3FrameHeader)
                    rtcmFrameLength = (rtcmPayloadLength + 6) * 8
                    if self.rtcmFrameBuffer.length >= rtcmFrameLength:
                        rtcmFrame = self.rtcmFrameBuffer[:rtcmFrameLength]
                        calcCrc = crc24q(rtcmFrame[:-24])
                        frameCrc = rtcmFrame[-24:].unpack('uint:24')
                        if calcCrc == frameCrc[0]:
                            rtcmFrameAligned = True
                            self.rtcmFrameBuffer \
                                = self.rtcmFrameBuffer[rtcmFrameLength:]
                            rtcmMessesageNo \
                                = rtcmFrame.peeklist('pad:24, uint:12')
                            description = self.rtcmMessage.messageDescription[
                                rtcmMessesageNo[0]]
                            print(f'  {time():.6f}: ' +
                                  f'RTCM message #: {rtcmMessesageNo[0]} ' +
                                  f'\"{description}\". ' +
                                  f'Payloadlength: {rtcmPayloadLength}')
                        else:
                            rtcmFrameAligned = False
                            self.rtcmFrameBuffer = self.rtcmFrameBuffer[8:]
                            print('!!! Warning CRC mismatch realigning!!!')
                            print(f'  {time():.6f}: ' +
                                  f'   CRC: {hex(calcCrc)} {rtcmFrame[-24:]}')
        else:
            print(f'Error! {ntripStatusCode}')
            for line in ntripResponceHeader:
                print(line)
        self.ntripWriter.close()
        return ntripResponceHeader
