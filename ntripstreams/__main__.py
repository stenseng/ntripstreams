#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import argparse
import asyncio
import logging
from signal import SIGINT, SIGTERM, signal

from ntripstreams.ntripstreams import NtripStream
from ntripstreams.rtcm3 import Rtcm3


def procSigint(signum, frame):
    logging.warning("Received SIGINT. Shutting down, Adjø!")
    exit(3)


def procSigterm(signum, frame):
    logging.warning("Received SIGTERM. Shutting down, Adjø!")
    exit(4)


signal(SIGINT, procSigint)
signal(SIGTERM, procSigterm)


async def procRtcmStream(url, mountPoint, user=None, passwd=None, fail=0, retry=5):
    ntripstream = NtripStream()
    rtcmMessage = Rtcm3()
    try:
        await ntripstream.requestNtripStream(url, mountPoint, user, passwd)
    except OSError as error:
        logging.error(error)
        return
    while True:
        try:
            rtcmFrame, timeStamp = await ntripstream.getRtcmFrame()
            fail = 0
        except (ConnectionError, IOError):
            if fail >= retry:
                fail += 1
                sleepTime = 5 * fail
                if sleepTime > 300:
                    sleepTime = 300
                logging.error(
                    f"{mountPoint}:{fail} failed attempt to reconnect. "
                    f"Will retry in {sleepTime} seconds!"
                )
                await asyncio.sleep(sleepTime)
                await procRtcmStream(url, mountPoint, user, passwd, fail)
            else:
                fail += 1
                logging.warning(f"{mountPoint}:Reconnecting. Attempt no. {fail}.")
                await asyncio.sleep(2)
                await procRtcmStream(url, mountPoint, user, passwd, fail)
        else:
            try:
                messageType, data = rtcmMessage.decodeRtcmFrame(rtcmFrame)
                description = rtcmMessage.messageDescription(messageType)
            except Exception:
                logging.info("Failed to decode RTCM frame.")
                break
            logging.debug(
                f"{mountPoint}:RTCM message #:{messageType}" f' "{description}".'
            )
            if (
                (messageType >= 1001 and messageType <= 1004)
                or (messageType >= 1009 and messageType <= 1012)
                or (messageType >= 1071 and messageType <= 1077)
                or (messageType >= 1081 and messageType <= 1087)
                or (messageType >= 1091 and messageType <= 1097)
                or (messageType >= 1101 and messageType <= 1107)
                or (messageType >= 1111 and messageType <= 1117)
                or (messageType >= 1121 and messageType <= 1127)
            ):
                numSignals = len(data[1])
                signals = ""
                if messageType >= 1071 and messageType <= 1127:
                    signals = rtcmMessage.msmSignalTypes(messageType, data[0][10])
                    numSignals = len(data[2])
                logging.info(
                    f"{mountPoint}:RTCM message #:{messageType}"
                    f" Constellation: {rtcmMessage.msmConstellation(messageType)}"
                    f" Sats: {len(data[1])}"
                    f" Signals: {numSignals}"
                    f" Signal Types: {signals}"
                )


async def rtcmStreamTasks(url, mountPoints, user, passwd):
    tasks = {}
    for mountPoint in mountPoints:
        tasks[mountPoint] = asyncio.create_task(
            procRtcmStream(url, mountPoint, user, passwd)
        )
    for mountPoint in mountPoints:
        await tasks[mountPoint]


parser = argparse.ArgumentParser()
parser.add_argument(
    "url", help="Ntripcaster url and port. (e.g. http[s]://caster.hostname.net:2101)"
)
parser.add_argument(
    "-m",
    "--mountpoint",
    action="append",
    help="Name of mountpoint without leading / (e.g. PNT1).",
)
parser.add_argument("-u", "--user", help="Username to access Ntrip " "caster.")
parser.add_argument("-p", "--passwd", help="Password  to access Ntrip caster.")
parser.add_argument(
    "-s", "--server", action="store_true", help="Send data to Ntrip caster as a server."
)
parser.add_argument("-1", "--ntrip1", action="store_true", help="Use Ntrip 1 protocol.")
parser.add_argument("-l", "--logfile", help="Log to file. Default output is terminal.")
parser.add_argument(
    "-v", "--verbosity", action="count", default=0, help="Increase verbosity level."
)
args = parser.parse_args()

logLevel = logging.ERROR
if args.verbosity == 1:
    logLevel = logging.WARNING
elif args.verbosity == 2:
    logLevel = logging.INFO
elif args.verbosity > 2:
    logLevel = logging.DEBUG
if args.logfile:
    logging.basicConfig(
        level=logLevel,
        filename=args.logfile,
        format="%(asctime)s;%(levelname)s;%(message)s",
    )
else:
    logging.basicConfig(level=logLevel, format="%(asctime)s;%(levelname)s;%(message)s")
ntripstream = NtripStream()
if not args.mountpoint:
    try:
        sourceTable = asyncio.run(ntripstream.requestSourcetable(args.url))
        for source in sourceTable:
            print(source)
    except OSError as error:
        logging.error(error)
else:
    if args.server:
        if args.ntrip1 and args.passwd:
            ntripstream.setRequestServerHeader(
                args.url, args.mountpoint[0], None, args.passwd, ntripVersion=1
            )
            print(ntripstream.ntripRequestHeader.decode())
        elif not args.ntrip1 and args.user and args.passwd:
            ntripstream.setRequestServerHeader(
                args.url, args.mountpoint[0], args.user, args.passwd
            )
            print(ntripstream.ntripRequestHeader.decode())
        else:
            print(
                "Password needed for Ntrip version 1, "
                "user and password needed for Ntrip version 2."
            )
    else:
        asyncio.run(rtcmStreamTasks(args.url, args.mountpoint, args.user, args.passwd))
