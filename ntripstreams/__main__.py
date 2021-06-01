#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

from ntripstreams import NtripStream
from rtcm3 import Rtcm3
from signal import signal, SIGINT, SIGTERM
import logging
import asyncio


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
    rtcmMessage = Rtcm3()
    try:
        await ntripstream.requestNtripStream(url, mountPoint, user, passwd)
    except ConnectionRefusedError:
        exit(1)
    while True:
        try:
            rtcmFrame, timeStamp = await ntripstream.getRtcmFrame()
            rtcmMessesageType = rtcmFrame.peeklist('pad:24, uint:12')
            description = rtcmMessage.messageDescription[rtcmMessesageType[0]]
            logging.debug(f'{mountPoint}:RTCM message #:{rtcmMessesageType[0]}'
                          f' \"{description}\".')
            fail = 0
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


async def rtcmStreamTasks(url, mountPoints, user, passwd):
    tasks = {}
    for mountPoint in mountPoints:
        tasks[mountPoint] = asyncio.create_task(procRtcmStream(url, mountPoint,
                                                               user, passwd))
    for mountPoint in mountPoints:
        await tasks[mountPoint]


def main():
    import argparse
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
    parser.add_argument('-l', '--logfile', help='Log to file. Default output '
                        'is terminal.')
    parser.add_argument('-v', '--verbosity', action='count', default=0,
                        help='Increase verbosity level.')
    args = parser.parse_args()

    logLevel = logging.ERROR
    if args.verbosity == 1:
        logLevel = logging.WARNING
    elif args.verbosity == 2:
        logLevel = logging.INFO
    elif args.verbosity > 2:
        logLevel = logging.DEBUG
    if args.logfile:
        logging.basicConfig(level=logLevel, filename=args.logfile,
                            format='%(asctime)s;%(levelname)s;%(message)s')
    else:
        logging.basicConfig(level=logLevel,
                            format='%(asctime)s;%(levelname)s;%(message)s')
    ntripstream = NtripStream()
    if not args.mountpoint:
        sourceTable = asyncio.run(ntripstream.requestSourcetable(args.url))
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
            elif not args.ntrip1 and args.user and args.passwd:
                ntripstream.setRequestServerHeader(args.url,
                                                   args.mountpoint[0],
                                                   args.user, args.passwd)
                print(ntripstream.ntripRequestHeader.decode())
            else:
                print('Password needed for Ntrip version 1, '
                      'user and password needed for Ntrip version 2.')
        else:
            asyncio.run(rtcmStreamTasks(args.url, args.mountpoint,
                                        args.user, args.passwd))


if __name__ == '__main__':
    main()
