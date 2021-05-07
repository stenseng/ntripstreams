#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
from urllib.parse import urlsplit
import base64
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
        self.ntripMountPoint = None
        self.ntripUser = None
        self.ntripPassword = None
        self.ntripAuthStr = ''
        self.nmeaString = None
        
        self.ntripWriter = None
        self.ntripReader = None
        self.rtcmFrameBuffer = BitStream()
        self.rtcmMessage = rtcm3()

        
    async def openNtripConnection(self, casterUrl: str, 
                                  ntripMountPoint: str=None, 
                                  ntripUser: str=None, ntripPassword: str=None,
                                  nmeaGga: str=None):
        self.casterUrl = urlsplit(casterUrl)
        if casterUrl.scheme == 'https':
            self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                self.casterUrl.hostname, self.casterUrl.port, ssl=True)
        else:
            self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                self.casterUrl.hostname, self.casterUrl.port)
        return
    
    def getSourceTableHeader(self, casterUrl: str) -> str:
        casterUrl = urlsplit(casterUrl)
        ntripVersion = 2.0
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
    
        header = (f'GET / HTTP/1.1\r\n'
                  f'Host: {casterUrl.geturl()}\r\n'
                  f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
                  f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                  f'Date: {timestamp}\r\n'
                  f'Connection: close\r\n'
                  f'\r\n').encode('ISO-8859-1')
        return header
    
    
    def getNtripStreamHeader(self, casterUrl: str, ntripMountPoint: str, 
                             ntripUser: str=None, ntripPassword: str=None,
                             nmeaGga: str=None) -> str:
        casterUrl = urlsplit(casterUrl)
        ntripVersion = 2.0
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        
        if nmeaGga:
            nmeaGgaStr = nmeaGga.encode('ISO-8859-1')
        else:
            nmeaGgaStr = ''
        
        if ntripUser and ntripPassword:
            ntripAuth = base64.b64encode((ntripUser + ':' + 
                        ntripPassword).encode('ISO-8859-1')).decode()
            ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
        else:
            ntripAuthStr = ''
    
        header = (f'GET /{ntripMountPoint} HTTP/1.1\r\n'
                  f'Host: {casterUrl.geturl()}\r\n'
                  f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
                  f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                  + ntripAuthStr
                  + nmeaGgaStr +
                  f'Date: {timestamp}\r\n'
                  'Connection: close\r\n'
                  '\r\n').encode('ISO-8859-1')
        return header
    
    
    def getServerHeader(self, casterUrl: str, ntripMountPoint: str, 
                        ntripUser: str=None, ntripPassword: str=None,
                        ntripVersion: int=2) -> str:
        casterUrl = urlsplit(casterUrl)
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        
        if ntripVersion == 2:
            ntripAuth = base64.b64encode((ntripUser + ':' + 
                        ntripPassword).encode('ISO-8859-1')).decode()
            ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
            header = (f'POST /{ntripMountPoint} HTTP/1.1\r\n'
                      f'Host: {casterUrl.geturl()}\r\n'
                      f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
                      + ntripAuthStr +
                      f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                      f'Date: {timestamp}\r\n'
                      'Connection: close\r\n'
                      '\r\n').encode('ISO-8859-1')
        elif ntripVersion == 1:
            ntripAuth = base64.b64encode(ntripPassword.encode('ISO-8859-1')
                                         ).decode()
            ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
            header = (f'SOURCE {ntripAuth} /{ntripMountPoint} HTTP/1.1\r\n'
                      f'User-Agent: NTRIP {self.__CLIENTNAME}\r\n'
                      '\r\n').encode('ISO-8859-1')
        return header
    
    
    async def getNtripResponceHeader(self, ntripReader):
        ntripResponceHeader = []
        ntripResponceHeaderTimestamp = []
        endOfHeader = False
        while True:
            line = await ntripReader.readline()
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
        casterUrl = urlsplit(casterUrl)
        if casterUrl.scheme == 'https':
            reader, writer = await asyncio.open_connection(
                casterUrl.hostname, casterUrl.port, ssl=True)
        else:
            reader, writer = await asyncio.open_connection(
                casterUrl.hostname, casterUrl.port)
    
        print(f'{time():.6f}: Connection open. Ready to write.')
        header = self.getSourceTableHeader(casterUrl.geturl())
        for line in header.decode().split('\r\n'):
            print(f'{time():.6f}: Request header > {line}')
        writer.write(header)
        await writer.drain()
        print(f'{time():.6f}: Header sent.')
    
        ntripResponceSourcetable = []
        ntripResponceHeader, ntripStatusCode, ntripResponceHeaderTimestamp\
             = await self.getNtripResponceHeader(reader) 
        if ntripStatusCode != '200':
            print(f'Error! {ntripStatusCode}')
            for line in ntripResponceHeader:
                print(line)
            writer.close()
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.decode('ISO-8859-1').rstrip()
            if line == 'ENDSOURCETABLE':
                ntripResponceSourcetable.append(line)
                writer.close()
                print(f'{time():.6f}: Sourcetabel received.')
                break
            else: 
                print(f'{time():.6f}: Sourcetable > {line}')
                ntripResponceSourcetable.append(line)
        return ntripResponceSourcetable, ntripStatusCode, ntripResponceHeader
     
               
    async def getNtripStream(self, casterUrl: str, station:str, 
                             user: str=None, passwd: str=None):
        
        casterUrl = urlsplit(casterUrl)
        if casterUrl.scheme == 'https':
            reader, writer = await asyncio.open_connection(
                casterUrl.hostname, casterUrl.port, ssl=True)
        else:
            reader, writer = await asyncio.open_connection(
                casterUrl.hostname, casterUrl.port)
            reader, writer = await asyncio.open_connection(
                casterUrl.hostname, casterUrl.port)
        print(f'{time():.6f}: Connection open. Ready to write.')
        header = self.getNtripStreamHeader(casterUrl.geturl(), station, 
                                           user, passwd)
        writer.write(header)
        await writer.drain()
        print(f'{time():.6f}: Header sent.')
        ntripResponceHeader, ntripStatusCode, ntripResponceHeaderTimestamp \
            = await self.getNtripResponceHeader(reader)
        
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
            rtcmFrameBuffer = BitStream()
            while True:
                if ntripStreamChunked:
                    rawLine = await reader.readuntil(b'\r\n')
                    length = int(rawLine[:-2].decode('ISO-8859-1'), 16)
                rawLine = await reader.readuntil(b'\r\n')
                receivedBytes = BitStream(rawLine[:-2])
                if ntripStreamChunked and receivedBytes.length != length * 8:
                    print('Chunk incomplete.\n Closing connection!')
                    print(f'{time():.6f}: ' +
                          f'Chunk {receivedBytes.length}:{length * 8}')
                    break
          
                rtcmFrameBuffer += receivedBytes
                if not rtcmFrameAligned:
                    rtcmFramePos = rtcmFrameBuffer.find(rtcm3FramePreample, 
                                                           bytealigned=True)
                    if rtcmFramePos:
                        rtcmFrameBuffer = rtcmFrameBuffer[rtcmFramePos[0]:]
                        rtcmFramePreample = True
                    else:
                        rtcmFrameBuffer = BitStream()           
                if rtcmFramePreample and rtcmFrameBuffer.length >= 48:
                    (rtcmPreAmple, rtcmPayloadLength) \
                        = rtcmFrameBuffer.peeklist(rtcm3FrameHeader)
                    if rtcmFrameBuffer.length >= ((rtcmPayloadLength + 6) * 8):
                        rtcmFrame = rtcmFrameBuffer[:(rtcmPayloadLength + 6) * 8]
                        calcCrc = crc24q(rtcmFrame[:-24])
                        frameCrc = rtcmFrame[-24:].unpack('uint:24')
                        if calcCrc == frameCrc[0]:
                            rtcmFrameAligned = True
                            rtcmFrameBuffer \
                                = rtcmFrameBuffer[(rtcmPayloadLength + 6) * 8:]
                            print('CRC OK!')
                            rtcmMessesageNo = rtcmFrame.peeklist('pad:24, uint:12')
                            description = self.rtcmMessage.messageDescription[
                                rtcmMessesageNo[0]]
                            print(f'  {time():.6f}: ' +
                                  f'RTCM message number: {rtcmMessesageNo[0]} ' +
                                  f'\"{description}\". ' +
                                  f'Payloadlength: {rtcmPayloadLength}')
                        else:
                            rtcmFrameAligned = False
                            rtcmFrameBuffer = rtcmFrameBuffer[8:]
                            print('!!! Warning CRC mismatch realigning stream !!!')
                            print(f'  {time():.6f}: ' +
                                  f'   CRC: {hex(calcCrc)} {rtcmFrame[-24:]}')
    
                        
        else:
            print(f'Error! {ntripStatusCode}')
            for line in ntripResponceHeader:
                print(line)
        writer.close()
        return ntripResponceHeader
