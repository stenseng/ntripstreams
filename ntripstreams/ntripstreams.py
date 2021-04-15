#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
import urllib.parse
import base64
import time

from __version__ import __version__


CLIENTVERSION = __version__
CLIENTNAME = f'Bedrock Solutions NtripClient/{CLIENTVERSION}'


def getSourceTableHeader(casterUrl: str) -> str:
    casterUrl = urllib.parse.urlsplit(casterUrl)
    ntripVersion = 2.0

    header = (f'GET / HTTP/1.1\r\n'
              f'Host: {casterUrl.geturl()}\r\n'
              f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
              f'User-Agent: NTRIP {CLIENTNAME}\r\n'
              f'Connection: close\r\n'
              f'\r\n').encode('ISO-8859-1')
    return header

def getNtripStreamHeader(casterUrl: str, ntripMountPoint: str, 
                         ntripUser: str, ntripPassword: str) -> str:
    casterUrl = urllib.parse.urlsplit(casterUrl)
    ntripVersion = 2.0
    
    if ntripUser and ntripPassword:
        ntripAuth = base64.b64encode((ntripUser + ':' + 
                    ntripPassword).encode('ISO-8859-1')).decode()
        ntripAuthStr = f'Authorization: Basic {ntripAuth}\r\n'
    else:
        ntripAuthStr = ''

    header = (f'GET /{ntripMountPoint} HTTP/1.1\r\n'
              f'Host: {casterUrl.geturl()}\r\n'
              f'Ntrip-Version: Ntrip/{ntripVersion}\r\n'
              f'User-Agent: NTRIP {CLIENTNAME}\r\n'
              + ntripAuthStr +
              'Connection: close\r\n'
              '\r\n').encode('ISO-8859-1')
    return header

async def getNtripSourcetable(casterUrl):
    casterUrl = urllib.parse.urlsplit(casterUrl)
    if casterUrl.scheme == 'https':
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port, ssl=True)
    else:
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port)

    print(f'{time.time():.6f}: Connection open. Ready to write.')
    header = getSourceTableHeader(casterUrl.geturl())
    for line in header.decode().split('\r\n'):
        print(f'{time.time():.6f}: Request header > {line}')
    writer.write(header)
    await writer.drain()
    print(f'{time.time():.6f}: Header sent.')

    endOfHeader = False
    ntripResponceHeader = []
    ntripResponceSourcetable = []
    while True:
        line = await reader.readline()
        if not line:
            break
        line = line.decode('ISO-8859-1').rstrip()
        if endOfHeader and line != 'ENDSOURCETABLE': 
            print(f'{time.time():.6f}: Sourcetable > {line}')
            ntripResponceSourcetable.append(line)
        if line == 'ENDSOURCETABLE':
            ntripResponceSourcetable.append(line)
            writer.close()
            print(f'{time.time():.6f}: Sourcetabel received.')
            break
        if line == '':
            endOfHeader = True
        if not endOfHeader:
            ntripResponceHeader.append(line)
            print(f'{time.time():.6f}: NTRIP header> {line}')
            
async def getNtripStream(casterUrl, station, user=None, passwd=None):
    casterUrl = urllib.parse.urlsplit(casterUrl)
    if casterUrl.scheme == 'https':
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port, ssl=True)
    else:
        reader, writer = await asyncio.open_connection(
            casterUrl.hostname, casterUrl.port)

    print(f'{time.time():.6f}: Connection open. Ready to write.')
    header = getNtripStreamHeader(casterUrl.geturl(), station, user, passwd)
    for line in header.decode().split('\r\n'):
        print(f'{time.time():.6f}: Request header > {line}')
    writer.write(header)
    await writer.drain()
    print(f'{time.time():.6f}: Header sent.')

    endOfHeader = False
    firstLine = True
    ntripResponceHeader = []
    ntripResponceSourcetable = []
    while not endOfHeader:
        line = await reader.readline()
        if not line:
            break
        line = line.decode('ISO-8859-1').rstrip()
        if firstLine:
            casterResponse = line.split(' ')
            firstLine = False
        if line == '':
            endOfHeader = True
            print(f'{time.time():.6f}: Header received.')
        if not endOfHeader:
            ntripResponceHeader.append(line)
            print(f'{time.time():.6f}: NTRIP header> {line}')
        if casterResponse[1] == '200':
            line = await reader.readline()
            print(f'{time.time():.6f}: data> {base64.b64encode(line)}')
            line = await reader.readline()
            print(f'{time.time():.6f}: data> {base64.b64encode(line)}')
            break
        
    writer.close()
    return (ntripResponceSourcetable, ntripResponceHeader)


if __name__ == '__main__':
    import sys
    
    argc = len(sys.argv)
    if argc > 1:
        url = sys.argv[1]
        asyncio.run(getNtripSourcetable(url))
    else: 
        exit(-1)
    if argc > 4:
        stn = sys.argv[2]
        user = sys.argv[3]
        passwd = sys.argv[4]
        asyncio.run(getNtripStream(url, stn, user, passwd))
    elif argc > 2:
        stn = sys.argv[2]
        asyncio.run(getNtripStream(url, stn))
