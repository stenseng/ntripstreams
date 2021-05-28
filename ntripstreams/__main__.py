#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

from asyncio import run
from time import time
from ntripstreams import NtripStream
from rtcm3 import rtcm3


async def procRtcmStream(url, stn, user, passwd):
    ntripstream = NtripStream()
    rtcmMessage = rtcm3()
    await ntripstream.requestNtripStream(url, stn, user, passwd)
    while True:
        rtcmFrame, timeStamp = await ntripstream.getRtcmFrame()
        rtcmMessesageNo = rtcmFrame.peeklist('pad:24, uint:12')
        description = rtcmMessage.messageDescription[rtcmMessesageNo[0]]
        print(f'{time():.6f}: RTCM message #: {rtcmMessesageNo[0]} ' +
              f'\"{description}\".')
        # Payloadlength: {rtcmPayloadLength}')
    return


def main():
    import sys

    argc = len(sys.argv)
    ntripstream = NtripStream()

    if argc == 1:
        header = ntripstream.setRequestServerHeader('http://gnsscaster.dk',
                                                    'PIP', 'otto', 'tystys', 2)
        for line in header.decode().split('\r\n'):
            print(f'Server header > {line}')
        header = ntripstream.setRequestServerHeader('http://gnsscaster.dk',
                                                    'PIP', 'otto', 'tystys', 1)
        for line in header.decode().split('\r\n'):
            print(f'Server header > {line}')
    elif argc == 2:
        url = sys.argv[1]
        sourceTable = run(ntripstream.requestSourcetable(url))
        for source in sourceTable:
            print(source)
    elif argc == 3:
        url = sys.argv[1]
        stn = sys.argv[2]
        run(ntripstream.requestNtripStream(url, stn))
    elif argc == 5:
        url = sys.argv[1]
        stn = sys.argv[2]
        user = sys.argv[3]
        passwd = sys.argv[4]
        run(procRtcmStream(url, stn, user, passwd))
        # run(ntripstream.requestNtripStream(url, stn, user, passwd))
        # while True:
        #     await ntripstream.getRtcmFrame()


if __name__ == '__main__':
    main()
