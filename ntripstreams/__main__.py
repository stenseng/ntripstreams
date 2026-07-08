#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command line entry point for ntripstreams.

Parses arguments (with ``NTRIP_*`` environment-variable fallbacks), then either
prints a caster's source table, streams and logs RTCM 3 messages from one or
more mountpoints, or prints a server request header. Installed as the
``ntripstreams`` console script.

@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import argparse
import asyncio
import logging
import os
from signal import SIGINT, SIGTERM, signal
from sys import exit
from types import FrameType
from typing import Optional

from ntripstreams.ntripstreams import NtripStream
from ntripstreams.rtcm3 import Rtcm3

ENV_PREFIX = "NTRIP_"


def env_default(name: str) -> Optional[str]:
    """Return the environment variable NTRIP_<name>, or None if unset/empty.

    Used as the argparse ``default`` so an explicit command line value takes
    precedence over the environment variable, which in turn takes precedence
    over the built-in default.
    """
    value = os.environ.get(ENV_PREFIX + name)
    return value if value else None


def procSigint(signum: int, frame: Optional[FrameType]) -> None:
    """Handle SIGINT: log a shutdown message and exit with status 3."""
    logging.warning("Received SIGINT. Shutting down, Adjø!")
    exit(3)


def procSigterm(signum: int, frame: Optional[FrameType]) -> None:
    """Handle SIGTERM: log a shutdown message and exit with status 4."""
    logging.warning("Received SIGTERM. Shutting down, Adjø!")
    exit(4)


async def procRtcmStream(
    url: str,
    mountPoint: str,
    user: str = None,
    passwd: str = None,
    fail: int = 0,
    retry: int = 5,
) -> None:
    """Stream a mountpoint and log decoded RTCM 3 messages, reconnecting on error.

    Runs until the stream ends or a frame cannot be decoded. Connection and I/O
    errors trigger reconnection with a backoff that grows once ``fail`` reaches
    ``retry`` (capped at 300 seconds).

    Parameters
    ----------
    url : str
        Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
    mountPoint : str
        Mountpoint name to consume, without the leading ``/``.
    user : str, optional
        Username for basic authentication. The default is None.
    passwd : str, optional
        Password for basic authentication. The default is None.
    fail : int, optional
        Initial consecutive-failure count, used for the reconnect backoff.
        The default is 0.
    retry : int, optional
        Failure count above which the longer backoff applies. The default is 5.
    """
    ntripstream = NtripStream()
    rtcmMessage = Rtcm3()
    while True:
        try:
            await ntripstream.requestNtripStream(url, mountPoint, user, passwd)
        except (OSError, ConnectionError) as error:
            fail += 1
            sleepTime = min(5 * fail, 300) if fail >= retry else 2
            logging.error(
                f"{mountPoint}:{fail} failed attempt to connect ({error}). "
                f"Will retry in {sleepTime} seconds!"
            )
            await asyncio.sleep(sleepTime)
            continue
        while True:
            try:
                rtcmFrame, timeStamp = await ntripstream.getRtcmFrame()
                fail = 0
            except (ConnectionError, IOError):
                fail += 1
                sleepTime = min(5 * fail, 300) if fail >= retry else 2
                logging.warning(
                    f"{mountPoint}:Reconnecting. Attempt no. {fail} "
                    f"in {sleepTime} seconds."
                )
                await asyncio.sleep(sleepTime)
                break
            try:
                messageType, data = rtcmMessage.decodeRtcmFrame(rtcmFrame)
                description = rtcmMessage.messageDescription(messageType)
            except Exception:
                logging.info("Failed to decode RTCM frame.")
                return
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
                    f"{mountPoint}:RTCM message #:{messageType},"
                    f" Constellation: {rtcmMessage.constellation(messageType)},"
                    f" GNSS: {data[0][2]},"
                    f" Sats: {len(data[1])},"
                    f" Signals: {numSignals},"
                    f" Signal Types: {signals}"
                )


async def rtcmStreamTasks(url: str, mountPoints: str, user: str, passwd: str) -> None:
    """Stream several mountpoints concurrently until all tasks finish.

    Parameters
    ----------
    url : str
        Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
    mountPoints : list of str
        Mountpoint names to stream concurrently, each without a leading ``/``.
    user : str
        Username for basic authentication.
    passwd : str
        Password for basic authentication.
    """
    tasks = {}
    for mountPoint in mountPoints:
        tasks[mountPoint] = asyncio.create_task(
            procRtcmStream(url, mountPoint, user, passwd)
        )
    for mountPoint in mountPoints:
        await tasks[mountPoint]


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse command line arguments, falling back to NTRIP_* environment vars.

    Resolution priority for each option is: command line value, then the
    matching environment variable, then the built-in default.
    """
    parser = argparse.ArgumentParser(
        epilog="Most options fall back to environment variables when omitted: "
        "NTRIP_URL, NTRIP_MOUNTPOINT (comma separated), NTRIP_USER, "
        "NTRIP_PASSWORD and NTRIP_LOGFILE. A command line value always "
        "overrules the environment variable."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=env_default("URL"),
        help="Ntripcaster url and port. (e.g. http[s]://caster.hostname.net:2101) "
        "[env: NTRIP_URL]",
    )
    parser.add_argument(
        "-m",
        "--mountpoint",
        action="append",
        help="Name of mountpoint without leading / (e.g. PNT1). May be repeated. "
        "[env: NTRIP_MOUNTPOINT, comma separated]",
    )
    parser.add_argument(
        "-u",
        "--user",
        default=env_default("USER"),
        help="Username to access Ntrip caster. [env: NTRIP_USER]",
    )
    parser.add_argument(
        "-p",
        "--passwd",
        default=env_default("PASSWORD"),
        help="Password to access Ntrip caster. [env: NTRIP_PASSWORD]",
    )
    parser.add_argument(
        "-s",
        "--server",
        action="store_true",
        help="Send data to Ntrip caster as a server.",
    )
    parser.add_argument(
        "-1", "--ntrip1", action="store_true", help="Use Ntrip 1 protocol."
    )
    parser.add_argument(
        "-l",
        "--logfile",
        default=env_default("LOGFILE"),
        help="Log to file. Default output is terminal. [env: NTRIP_LOGFILE]",
    )
    parser.add_argument(
        "-v", "--verbosity", action="count", default=0, help="Increase verbosity level."
    )
    args = parser.parse_args(argv)

    # -m/--mountpoint uses action="append", so fall back to the environment
    # only when no mountpoint was given on the command line (comma separated).
    if not args.mountpoint:
        env_mountpoints = env_default("MOUNTPOINT")
        if env_mountpoints:
            args.mountpoint = [
                mount.strip() for mount in env_mountpoints.split(",") if mount.strip()
            ]

    if not args.url:
        parser.error("a caster url is required (positional argument or NTRIP_URL)")
    return args


def main() -> None:
    """Run the ntripstreams command line tool.

    Installs the signal handlers, parses arguments (including ``NTRIP_*``
    environment fallbacks), configures logging, and dispatches to the
    requested action: print the source table (no mountpoint), print a server
    request header (``--server``), or stream the given mountpoints.
    """
    signal(SIGINT, procSigint)
    signal(SIGTERM, procSigterm)
    args = parse_args()

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
        logging.basicConfig(
            level=logLevel, format="%(asctime)s;%(levelname)s;%(message)s"
        )
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
            elif not args.ntrip1 and args.user and args.passwd:
                ntripstream.setRequestServerHeader(
                    args.url, args.mountpoint[0], args.user, args.passwd
                )
            else:
                print(
                    "Password needed for Ntrip version 1, "
                    "user and password needed for Ntrip version 2."
                )
        else:
            asyncio.run(
                rtcmStreamTasks(args.url, args.mountpoint, args.user, args.passwd)
            )


if __name__ == "__main__":
    main()
