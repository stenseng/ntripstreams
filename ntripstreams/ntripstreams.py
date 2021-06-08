#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import asyncio
import logging
from base64 import b64encode
from time import gmtime, strftime, time
from urllib.parse import urlsplit

from bitstring import Bits, BitStream

from .__version__ import __version__
from .crc import crc24q


class NtripStream:
    def __init__(self):
        self.__CLIENTVERSION = __version__
        self.__CLIENTNAME = "Bedrock Solutions NtripClient/" + f"{self.__CLIENTVERSION}"
        self.casterUrl = None
        self.ntripWriter = None
        self.ntripReader = None
        self.ntripVersion = 2
        self.ntripMountPoint = None
        self.ntripAuthString = ""
        self.ntripRequestHeader = ""
        self.ntripResponseHeader = []
        self.ntripResponseStatusCode = None
        self.ntripStreamChunked = False
        self.nmeaString = ""
        self.rtcmFrameBuffer = BitStream()
        self.rtcmFramePreample = False
        self.rtcmFrameAligned = False

    async def openNtripConnection(self, casterUrl: str):
        """
        Connects to a caste with url http[s]://caster.hostename.net:port
        """
        self.casterUrl = urlsplit(casterUrl)
        if self.casterUrl.scheme == "https":
            self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                self.casterUrl.hostname, self.casterUrl.port, ssl=True
            )
        else:
            self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                self.casterUrl.hostname, self.casterUrl.port
            )

    def setRequestSourceTableHeader(self, casterUrl: str):
        self.casterUrl = urlsplit(casterUrl)
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        self.ntripRequestHeader = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.casterUrl.geturl()}\r\n"
            f"Ntrip-Version: Ntrip/"
            f"{self.ntripVersion}.0\r\n"
            f"User-Agent: NTRIP {self.__CLIENTNAME}\r\n"
            f"Date: {timestamp}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("ISO-8859-1")

    def setRequestStreamHeader(
        self,
        casterUrl: str,
        ntripMountPoint: str,
        ntripUser: str = None,
        ntripPassword: str = None,
        nmeaString: str = None,
    ):
        self.casterUrl = urlsplit(casterUrl)
        self.ntripMountPoint = ntripMountPoint
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        if nmeaString:
            self.nmeaString = nmeaString.encode("ISO-8859-1")
        if ntripUser and ntripPassword:
            ntripAuth = b64encode(
                (ntripUser + ":" + ntripPassword).encode("ISO-8859-1")
            ).decode()
            self.ntripAuthString = f"Authorization: Basic {ntripAuth}\r\n"
        self.ntripRequestHeader = (
            f"GET /{ntripMountPoint} HTTP/1.1\r\n"
            f"Host: {self.casterUrl.geturl()}\r\n"
            "Ntrip-Version: Ntrip/"
            f"{self.ntripVersion}.0\r\n"
            f"User-Agent: NTRIP {self.__CLIENTNAME}\r\n"
            + self.ntripAuthString
            + self.nmeaString
            + f"Date: {timestamp}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ISO-8859-1")

    def setRequestServerHeader(
        self,
        casterUrl: str,
        ntripMountPoint: str,
        ntripUser: str = None,
        ntripPassword: str = None,
        ntripVersion: int = 2,
    ):
        self.casterUrl = urlsplit(casterUrl)
        if ntripVersion == 1:
            self.ntripVersion = 1
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())

        if self.ntripVersion == 2:
            if ntripUser and ntripPassword:
                ntripAuth = b64encode(
                    (ntripUser + ":" + ntripPassword).encode("ISO-8859-1")
                ).decode()
            self.ntripAuthString = f"Authorization: Basic {ntripAuth}\r\n"
            self.ntripRequestHeader = (
                f"POST /{ntripMountPoint} HTTP/1.1\r\n"
                f"Host: {self.casterUrl.geturl()}\r\n"
                "Ntrip-Version: Ntrip/"
                f"{self.ntripVersion}.0\r\n"
                + self.ntripAuthString
                + "User-Agent: NTRIP "
                f"{self.__CLIENTNAME}\r\n"
                f"Date: {timestamp}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode("ISO-8859-1")
        elif self.ntripVersion == 1:
            if ntripPassword:
                ntripAuth = b64encode(ntripPassword.encode("ISO-8859-1")).decode()
            self.ntripRequestHeader = (
                f"SOURCE {ntripAuth} "
                f"/{ntripMountPoint} HTTP/1.1\r\n"
                "Source-Agent: NTRIP "
                f"{self.__CLIENTNAME}\r\n"
                "\r\n"
            ).encode("ISO-8859-1")

    async def getNtripResponseHeader(self):
        self.ntripResponseHeader = []
        ntripResponseHeaderTimestamp = []
        endOfHeader = False
        while True:
            line = await self.ntripReader.readline()
            ntripResponseHeaderTimestamp.append(time())
            if not line:
                break
            line = line.decode("ISO-8859-1").rstrip()
            if line == "":
                endOfHeader = True
                break
            if not endOfHeader:
                self.ntripResponseHeader.append(line)
        statusResponse = self.ntripResponseHeader[0].split(" ")
        if len(statusResponse) > 1:
            self.ntripResponseStatusCode = statusResponse[1]
        else:
            self.ntripResponseStatusCode = 0

    def ntripResponseStatusOk(self):
        if self.ntripResponseStatusCode == "200":
            if "Transfer-Encoding: chunked" in self.ntripResponseHeader:
                logging.info(f"{self.ntripMountPoint}:Stream is chunked")
                self.ntripStreamChunked = True
            self.rtcmFramePreample = False
            self.rtcmFrameAligned = False
            return True
        else:
            logging.error(
                f"{self.ntripMountPoint}:Response error "
                f"{self.ntripResponseStatusCode}!"
            )
            for line in self.ntripResponseHeader:
                logging.error(f"{self.ntripMountPoint}:TCP response: {line}")
            raise ConnectionRefusedError(
                f"{self.ntripMountPoint}:" f"{self.ntripResponseHeader[0]}"
            )
            self.ntripWriter.close()
            return False

    async def requestSourcetable(self, casterUrl: str):
        await self.openNtripConnection(casterUrl)
        logging.info(f"Connection to {casterUrl} open. Ready to write.")
        self.setRequestSourceTableHeader(self.casterUrl.geturl())
        self.ntripWriter.write(self.ntripRequestHeader)
        await self.ntripWriter.drain()
        logging.info("Sourcetable request sent.")
        ntripSourcetable = []
        await self.getNtripResponseHeader()
        if self.ntripResponseStatusCode != "200":
            logging.error(f"Response error {self.ntripResponseStatusCode}!")
            for line in self.ntripResponseHeader:
                logging.error(f"TCP response: {line}")
            self.ntripWriter.close()
        while True:
            line = await self.ntripReader.readline()
            if not line:
                break
            line = line.decode("ISO-8859-1").rstrip()
            if line == "ENDSOURCETABLE":
                ntripSourcetable.append(line)
                self.ntripWriter.close()
                logging.info("Sourcetabel received.")
                break
            else:
                ntripSourcetable.append(line)
        return ntripSourcetable

    async def requestNtripServer(
        self,
        casterUrl: str,
        mountPoint: str,
        user: str = None,
        passwd: str = None,
        ntripVersion: int = 2,
    ):
        self.ntripVersion = ntripVersion
        await self.openNtripConnection(casterUrl)
        self.ntripMountPoint = mountPoint
        logging.info(
            f"{self.ntripMountPoint}:Connection to {casterUrl} open. " "Ready to write."
        )
        self.setRequestServerHeader(
            self.casterUrl.geturl(), self.ntripMountPoint, user, passwd
        )
        self.ntripWriter.write(self.ntripRequestHeader)
        await self.ntripWriter.drain()
        logging.info(f"{self.ntripMountPoint}:Request server header sent.")
        await self.getNtripResponseHeader()
        logging.debug(self.ntripResponseHeader)
        self.ntripResponseStatusOk()

    async def sendRtcmFrame(self, rtcmFrame):
        self.ntripWriter.write(rtcmFrame)
        await self.ntripWriter.drain()

    async def requestNtripStream(
        self, casterUrl: str, mountPoint: str, user: str = None, passwd: str = None
    ):
        await self.openNtripConnection(casterUrl)
        self.ntripMountPoint = mountPoint
        logging.info(
            f"{self.ntripMountPoint}:Connection to {casterUrl} open. " "Ready to write."
        )
        self.setRequestStreamHeader(
            self.casterUrl.geturl(), self.ntripMountPoint, user, passwd
        )
        self.ntripWriter.write(self.ntripRequestHeader)
        await self.ntripWriter.drain()
        logging.info(f"{self.ntripMountPoint}:Request stream header sent.")
        await self.getNtripResponseHeader()
        self.ntripResponseStatusOk()

    async def getRtcmFrame(self):
        rtcm3FramePreample = Bits(bin="0b11010011")
        rtcm3FrameHeaderFormat = "bin:8, pad:6, uint:10"
        rtcmFrameComplete = False
        while not rtcmFrameComplete:
            if self.ntripStreamChunked:
                rawLine = await self.ntripReader.readuntil(b"\r\n")
                length = int(rawLine[:-2].decode("ISO-8859-1"), 16)
            rawLine = await self.ntripReader.readuntil(b"\r\n")
            timeStamp = time()
            receivedBytes = BitStream(rawLine[:-2])
            if self.ntripStreamChunked and receivedBytes.length != length * 8:
                logging.error(
                    f"{self.ntripMountPoint}:Chunk incomplete "
                    f"{receivedBytes.length}:{length * 8}. "
                    "Closing connection! "
                )
                raise IOError("Chunk incomplete ")
            self.rtcmFrameBuffer += receivedBytes
            if not self.rtcmFrameAligned:
                rtcmFramePos = self.rtcmFrameBuffer.find(
                    rtcm3FramePreample, bytealigned=True
                )
                if rtcmFramePos:
                    self.rtcmFrameBuffer = self.rtcmFrameBuffer[rtcmFramePos[0] :]
                    self.rtcmFramePreample = True
                else:
                    self.rtcmFrameBuffer = BitStream()
            if self.rtcmFramePreample and self.rtcmFrameBuffer.length >= 48:
                (rtcmPreAmple, rtcmPayloadLength) = self.rtcmFrameBuffer.peeklist(
                    rtcm3FrameHeaderFormat
                )
                rtcmFrameLength = (rtcmPayloadLength + 6) * 8
                if self.rtcmFrameBuffer.length >= rtcmFrameLength:
                    rtcmFrame = self.rtcmFrameBuffer[:rtcmFrameLength]
                    calcCrc = crc24q(rtcmFrame[:-24])
                    frameCrc = rtcmFrame[-24:].unpack("uint:24")
                    if calcCrc == frameCrc[0]:
                        self.rtcmFrameAligned = True
                        self.rtcmFrameBuffer = self.rtcmFrameBuffer[rtcmFrameLength:]
                        rtcmFrameComplete = True
                    else:
                        self.rtcmFrameAligned = False
                        self.rtcmFrameBuffer = self.rtcmFrameBuffer[8:]
                        logging.warning(
                            f"{self.ntripMountPoint}:CRC mismatch "
                            f"{hex(calcCrc)} != {rtcmFrame[-24:]}."
                            f" Realigning!"
                        )
        return rtcmFrame, timeStamp
