#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
import urllib.parse
import base64
from time import time, strftime, gmtime
from bitstring import ConstBitArray, BitStream

from __version__ import __version__


__CLIENTVERSION = __version__
__CLIENTNAME = f'Bedrock Solutions NtripClient/{__CLIENTVERSION}'


def getSourceTableHeader(casterUrl: str) -> str:
    casterUrl = urllib.parse.urlsplit(casterUrl)
    ntripVersion = 2.0
    timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())

    header = (f'GET / HTTP/1.1\r\n'
              f'Host: {casterUrl.geturl()}\r\n'
              f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
              f'User-Agent: NTRIP {__CLIENTNAME}\r\n'
              f'Date: {timestamp}\r\n'
              f'Connection: close\r\n'
              f'\r\n').encode('ISO-8859-1')
    return header


def getNtripStreamHeader(casterUrl: str, ntripMountPoint: str, 
                         ntripUser: str=None, ntripPassword: str=None,
                         nmeaGga: str=None) -> str:
    casterUrl = urllib.parse.urlsplit(casterUrl)
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
              f'User-Agent: NTRIP {__CLIENTNAME}\r\n'
              + ntripAuthStr
              + nmeaGgaStr +
              f'Date: {timestamp}\r\n'
              'Connection: close\r\n'
              '\r\n').encode('ISO-8859-1')
    return header


def getServerHeader(casterUrl: str, ntripMountPoint: str, 
                    ntripUser: str=None, ntripPassword: str=None,
                    ntripVersion: int=2) -> str:
    casterUrl = urllib.parse.urlsplit(casterUrl)
    timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
    
    if ntripVersion == 2:
        ntripAuth = base64.b64encode((ntripUser + ':' + 
                    ntripPassword).encode('ISO-8859-1')).decode()
        ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
        header = (f'POST /{ntripMountPoint} HTTP/1.1\r\n'
                  f'Host: {casterUrl.geturl()}\r\n'
                  f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
                  + ntripAuthStr +
                  f'User-Agent: NTRIP {__CLIENTNAME}\r\n'
                  f'Date: {timestamp}\r\n'
                  'Connection: close\r\n'
                  '\r\n').encode('ISO-8859-1')
    elif ntripVersion == 1:
        ntripAuth = base64.b64encode(ntripPassword.encode('ISO-8859-1')
                                     ).decode()
        ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
        header = (f'SOURCE {ntripAuth} /{ntripMountPoint} HTTP/1.1\r\n'
                  f'User-Agent: NTRIP {__CLIENTNAME}\r\n'
                  '\r\n').encode('ISO-8859-1')
    return header


async def getNtripResponceHeader(ntripReader):
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
    return ntripResponceHeader, ntripStatusCode, ntripResponceHeaderTimestamp


async def getNtripSourcetable(casterUrl: str):
    casterUrl = urllib.parse.urlsplit(casterUrl)
    if casterUrl.scheme == 'https':
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port, ssl=True)
    else:
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port)

    print(f'{time():.6f}: Connection open. Ready to write.')
    header = getSourceTableHeader(casterUrl.geturl())
    for line in header.decode().split('\r\n'):
        print(f'{time():.6f}: Request header > {line}')
    writer.write(header)
    await writer.drain()
    print(f'{time():.6f}: Header sent.')

    ntripResponceSourcetable = []
    ntripResponceHeader, ntripStatusCode = await getNtripResponceHeader(reader) 
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
 
           
async def getNtripStream(casterUrl: str, station:str, 
                         user: str=None, passwd=None):
    rtcm3Preample = ConstBitArray('0b11010011')
    rtcm3FrameFormat = 'hex:8, bin:6, uint:10'
    
    casterUrl = urllib.parse.urlsplit(casterUrl)
    if casterUrl.scheme == 'https':
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port, ssl=True)
    else:
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port)
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port)
    print(f'{time():.6f}: Connection open. Ready to write.')
    
    header = getNtripStreamHeader(casterUrl.geturl(), station, user, passwd)
    writer.write(header)
    await writer.drain()
    print(f'{time():.6f}: Header sent.')
    
    ntripResponceHeader, ntripStatusCode, ntripResponceHeaderTimestamp \
        = await getNtripResponceHeader(reader) 
    if ntripStatusCode == '200':
        
        for count in range(0, 10):
            rawLine = await reader.readuntil(b'\r\n')
            length = int(rawLine[:-2].decode('ISO-8859-1'), 16)

            rawLine = await reader.readuntil(b'\r\n')
            rtcmBytes = BitStream(rawLine[:-2])
            print(f'{time():.6f}: chunk {int(rtcmBytes.length / 8)}:{length}')
            # print(f'{time():.6f}: data {len(rawLine)}:{length}> {bitLine.hex}')
            # print(rtcmBytes.unpack(rtcm3FrameFormat))
            rtcmFramePos = rtcmBytes.find(rtcm3Preample, bytealigned=True)
            if rtcmFramePos:
                rtcmFrameTemp = rtcmBytes[rtcmFramePos[0]:]
                preample, padding, size = rtcmFrameTemp.unpack(rtcm3FrameFormat)
                print(preample, padding, size)
    else:
        print(f'Error! {ntripStatusCode}')
        for line in ntripResponceHeader:
            print(line)
    writer.close()
    return ntripResponceHeader
