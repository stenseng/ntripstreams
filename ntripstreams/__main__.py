#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

from asyncio import run
from ntripstreams import NtripStream
from rtcm3 import rtcm3
import logging


async def procRtcmStream(url, stn, user=None, passwd=None, fail=0):
    ntripstream = NtripStream()
    rtcmMessage = rtcm3()
    try:
        await ntripstream.requestNtripStream(url, stn, user, passwd)
    except ConnectionRefusedError:
        exit(1)
    except KeyboardInterrupt:
        print('Adjø!')
        exit(3)
    while True:
        try:
            rtcmFrame, timeStamp = await ntripstream.getRtcmFrame()
            rtcmMessesageNo = rtcmFrame.peeklist('pad:24, uint:12')
            description = rtcmMessage.messageDescription[rtcmMessesageNo[0]]
            logging.debug(f'RTCM message #:{rtcmMessesageNo[0]} '
                          f'\"{description}\".')
        except IOError:
            if fail >= 5:
                exit(2)
                logging.error('Failed to reconnect!')
            else:
                logging.warning('Reconnecting!')
                await procRtcmStream(url, stn, user, passwd, fail=fail + 1)
        except KeyboardInterrupt:
            print('Adjø!')
            exit(3)


def main():
    import sys

    logging.basicConfig(format='%(asctime)s;%(levelname)s;%(message)s',
                        level=logging.DEBUG)
    argc = len(sys.argv)
    ntripstream = NtripStream()

    if argc == 1:
        ntripstream.setRequestServerHeader('http://gnsscaster.dk',
                                           'PIP', 'otto', 'tystys', 2)
        print(ntripstream.ntripRequestHeader.decode())
        ntripstream.setRequestServerHeader('http://gnsscaster.dk',
                                           'PIP', 'otto', 'tystys', 1)
        print(ntripstream.ntripRequestHeader.decode())
    elif argc == 2:
        url = sys.argv[1]
        sourceTable = run(ntripstream.requestSourcetable(url))
        for source in sourceTable:
            print(source)
    elif argc == 3:
        url = sys.argv[1]
        stn = sys.argv[2]
        # run(ntripstream.requestNtripStream(url, stn))
        run(procRtcmStream(url, stn))
    elif argc == 5:
        url = sys.argv[1]
        stn = sys.argv[2]
        user = sys.argv[3]
        passwd = sys.argv[4]
        run(procRtcmStream(url, stn, user, passwd))


if __name__ == '__main__':
    main()
