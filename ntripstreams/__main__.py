#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

from ntripstreams import NtripStream
from rtcm3 import rtcm3
from signal import signal, SIGINT, SIGTERM
import logging


def procSigint(signum, frame):
    logging.warning('Received SIGINT. Shutting down, Adjø!')
    exit(3)


def procSigterm(signum, frame):
    logging.warning('Received SIGTERM. Shutting down, Adjø!')
    exit(4)


signal(SIGINT, procSigint)
signal(SIGTERM, procSigterm)


async def procRtcmStream(url, mountPoint, user=None, passwd=None,
                         fail=0, retry=5):
    ntripstream = NtripStream()
    rtcmMessage = rtcm3()
    try:
        await ntripstream.requestNtripStream(url, mountPoint, user, passwd)
    except ConnectionRefusedError:
        exit(1)
    while True:
        try:
            rtcmFrame, timeStamp = await ntripstream.getRtcmFrame()
            rtcmMessesageNo = rtcmFrame.peeklist('pad:24, uint:12')
            description = rtcmMessage.messageDescription[rtcmMessesageNo[0]]
            logging.debug(f'{mountPoint}:RTCM message #:{rtcmMessesageNo[0]} '
                          f'\"{description}\".')
        except IOError:
            if fail >= retry:
                logging.error(f'{mountPoint}:{fail} failed attempt to '
                              'reconnect. Bailing out!')
                exit(2)
            else:
                fail += 1
                logging.warning(f'{mountPoint}:Reconnecting. '
                                f'Attempt no. {fail}.')
                await procRtcmStream(url, mountPoint, user, passwd, fail)


def main():
    from asyncio import run
    import argparse
    logging.basicConfig(format='%(asctime)s;%(levelname)s;%(message)s',
                        level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='Ntripcaster url and port. '
                        '(e.g. http[s]://caster.hostename.net:2101)')
    parser.add_argument('-m', '--mountpoint', action='append',
                        help='Name of mountpoint without'
                        ' leading / (e.g. PNT1).')
    parser.add_argument('-u', '--user', help='Username to access Ntrip '
                        'caster.')
    parser.add_argument('-p', '--passwd', help='Password  to access Ntrip '
                        'caster.')
    parser.add_argument('-s', '--server', action='store_true',
                        help='Send data to Ntrip caster as a server.')
    parser.add_argument('-1', '--ntrip1', action='store_true',
                        help='Use Ntrip 1 protocol.')
    args = parser.parse_args()
    ntripstream = NtripStream()

    if not args.mountpoint:
        sourceTable = run(ntripstream.requestSourcetable(args.url))
        for source in sourceTable:
            print(source)
    else:
        if args.server:
            if args.ntrip1 and args.passwd:
                ntripstream.setRequestServerHeader(args.url,
                                                   args.mountpoint[0],
                                                   None, args.passwd,
                                                   ntripVersion=1)
                print(ntripstream.ntripRequestHeader.decode())
            elif args.user and args.passwd:
                ntripstream.setRequestServerHeader(args.url,
                                                   args.mountpoint[0],
                                                   args.user, args.passwd)
                print(args.user)
                print(ntripstream.ntripRequestHeader.decode())
            else:
                print('Password needed for Ntrip version 1, '
                      'user and password needed for Ntrip version 2.')
        else:
            print(args.mountpoint)
            for mountPoint in args.mountpoint:
                print(mountPoint)
                run(procRtcmStream(args.url, mountPoint,
                                   args.user, args.passwd))


if __name__ == '__main__':
    main()
