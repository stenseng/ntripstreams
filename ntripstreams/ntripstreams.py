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
from typing import Union
from urllib.parse import urlsplit

from bitstring import Bits, BitStream
from ntripstreams.__version__ import __version__
from ntripstreams.crc import crc24q


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

    async def openNtripConnection(self, casterUrl: str) -> bool:
        """
        Connects to a caster.

        Parameters
        ----------
        casterUrl : str
            http[s]://caster.hostname.net:port.

        Raises
        ------
        TimeoutError
            DESCRIPTION.
        OSError
            DESCRIPTION.

        Returns
        -------
        bool
            DESCRIPTION.

        """
        self.casterUrl = urlsplit(casterUrl)
        try:
            if self.casterUrl.scheme == "https":
                self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                    self.casterUrl.hostname, self.casterUrl.port, ssl=True
                )
            else:
                self.ntripReader, self.ntripWriter = await asyncio.open_connection(
                    self.casterUrl.hostname, self.casterUrl.port
                )
        except TimeoutError as error:
            raise TimeoutError(
                f"Connection to {casterUrl} timed out: {error}"
            ) from None
            logging.error(f"Connection to {casterUrl} timed out: {error}")
            return False
        except OSError as error:
            raise OSError(f"Connection to {casterUrl} failed with: {error}") from None
            logging.error(f"Connection to {casterUrl} failed with: {error}")
            return False
        logging.info(
            f"{self.ntripMountPoint}: Connection to {casterUrl} open. "
            "Ready to write."
        )
        return True

    def setRequestSourceTableHeader(self, casterUrl: str) -> None:
        """


        Parameters
        ----------
        casterUrl : str
            DESCRIPTION.

        Returns
        -------
        None
            DESCRIPTION.

        """
        self.casterUrl = urlsplit(casterUrl)
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        self.ntripRequestHeader = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.casterUrl.netloc}\r\n"
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
    ) -> None:
        """


        Parameters
        ----------
        casterUrl : str
            DESCRIPTION.
        ntripMountPoint : str
            DESCRIPTION.
        ntripUser : str, optional
            DESCRIPTION. The default is None.
        ntripPassword : str, optional
            DESCRIPTION. The default is None.
        nmeaString : str, optional
            DESCRIPTION. The default is None.
         : TYPE
            DESCRIPTION.

        Returns
        -------
        None
            DESCRIPTION.

        """
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
            f"Host: {self.casterUrl.netloc}\r\n"
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
    ) -> None:
        """


        Parameters
        ----------
        casterUrl : str
            DESCRIPTION.
        ntripMountPoint : str
            DESCRIPTION.
        ntripUser : str, optional
            DESCRIPTION. The default is None.
        ntripPassword : str, optional
            DESCRIPTION. The default is None.
        ntripVersion : int, optional
            DESCRIPTION. The default is 2.
         : TYPE
            DESCRIPTION.

        Returns
        -------
        None
            DESCRIPTION.

        """
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
                f"Host: {self.casterUrl.netloc}\r\n"
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

    def getHeaderStrings(self, rawHeader: Union[bytes, list]) -> str:
        """


        Parameters
        ----------
        rawHeader : [bytes, list]
            DESCRIPTION.

        Returns
        -------
        str
            DESCRIPTION.

        """
        if isinstance(rawHeader, bytes):
            headerStrings = rawHeader.decode("ISO-8859-1").split("\r\n")
        if isinstance(rawHeader, list):
            headerStrings = []
            for rawLine in rawHeader:
                headerStrings.append(rawLine.decode("ISO-8859-1").rstrip())
        return headerStrings

    async def getNtripResponseHeader(self) -> None:
        """


        Raises
        ------
        ConnectionError
            DESCRIPTION.

        Returns
        -------
        None
            DESCRIPTION.

        """
        self.ntripResponseHeader = []
        ntripResponseHeaderTimestamp = []
        rawHeader = []
        while True:
            try:
                line = await self.ntripReader.readline()
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as error:
                raise ConnectionError(
                    f"Connection to {self.casterUrl} failed with: {error}"
                ) from None
                logging.error(f"Connection to {self.casterUrl} failed with: {error}")
            ntripResponseHeaderTimestamp.append(time())
            if not line:
                break
            rawHeader.append(line)
            if line.decode("ISO-8859-1").rstrip() == "":
                break
        self.ntripResponseHeader = self.getHeaderStrings(rawHeader)
        if "Transfer-Encoding: chunked".lower() in [
            line.lower() for line in self.ntripResponseHeader
        ]:
            self.ntripStreamChunked = True
            logging.info(f"{self.ntripMountPoint}: Stream is chunked")
        statusResponse = self.ntripResponseHeader[0].split(" ")
        if len(statusResponse) > 1:
            self.ntripResponseStatusCode = statusResponse[1]
        else:
            self.ntripResponseStatusCode = 0

    def ntripResponseStatusOk(self) -> bool:
        """


        Raises
        ------
        ConnectionError
            DESCRIPTION.

        Returns
        -------
        bool
            DESCRIPTION.

        """
        if self.ntripResponseStatusCode == "200":
            self.rtcmFramePreample = False
            self.rtcmFrameAligned = False
            return True
        else:
            logging.error(
                f"{self.ntripMountPoint}: Response error "
                f"{self.ntripResponseStatusCode}!"
            )
            for line in self.ntripResponseHeader:
                logging.error(f"{self.ntripMountPoint}: TCP response: {line}")
            raise ConnectionError(
                f"{self.ntripMountPoint}: {self.ntripResponseHeader[0]}"
            )
            self.ntripWriter.close()
            return False

    async def sendRequestHeader(self) -> None:
        """


        Returns
        -------
        None
            DESCRIPTION.

        """
        self.ntripWriter.write(self.ntripRequestHeader)
        await self.ntripWriter.drain()
        for line in self.getHeaderStrings(self.ntripRequestHeader):
            logging.debug(f"TCP request: {line}")
        logging.info(f"{self.ntripMountPoint}: Request sent.")
        await self.getNtripResponseHeader()
        if self.ntripResponseStatusOk():
            for line in self.ntripResponseHeader:
                logging.debug(f"TCP response: {line}")

    async def requestSourcetable(self, casterUrl: str) -> list:
        """


        Parameters
        ----------
        casterUrl : str
            DESCRIPTION.

        Raises
        ------
        ConnectionError
            DESCRIPTION.

        Returns
        -------
        list
            DESCRIPTION.

        """
        await self.openNtripConnection(casterUrl)
        self.setRequestSourceTableHeader(casterUrl)
        await self.sendRequestHeader()
        ntripSourcetable = []
        while True:
            try:
                line = await self.ntripReader.readline()
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as error:
                raise ConnectionError(
                    f"Connection to {self.casterUrl} failed with: {error}"
                ) from None
                logging.error(f"Connection to {self.casterUrl} failed with: {error}")
                return []
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
    ) -> None:
        """


        Parameters
        ----------
        casterUrl : str
            DESCRIPTION.
        mountPoint : str
            DESCRIPTION.
        user : str, optional
            DESCRIPTION. The default is None.
        passwd : str, optional
            DESCRIPTION. The default is None.
        ntripVersion : int, optional
            DESCRIPTION. The default is 2.
         : TYPE
            DESCRIPTION.

        Returns
        -------
        None
            DESCRIPTION.

        """
        self.ntripVersion = ntripVersion
        self.ntripMountPoint = mountPoint
        await self.openNtripConnection(casterUrl)
        self.setRequestServerHeader(
            self.casterUrl.geturl(), self.ntripMountPoint, user, passwd
        )
        await self.sendRequestHeader()

    async def requestNtripStream(
        self, casterUrl: str, mountPoint: str, user: str = None, passwd: str = None
    ) -> None:
        """


        Parameters
        ----------
        casterUrl : str
            DESCRIPTION.
        mountPoint : str
            DESCRIPTION.
        user : str, optional
            DESCRIPTION. The default is None.
        passwd : str, optional
            DESCRIPTION. The default is None.

        Returns
        -------
        None
            DESCRIPTION.

        """
        self.ntripMountPoint = mountPoint
        await self.openNtripConnection(casterUrl)
        self.setRequestStreamHeader(
            self.casterUrl.geturl(), self.ntripMountPoint, user, passwd
        )
        await self.sendRequestHeader()

    async def sendRtcmFrame(self, rtcmFrame: BitStream) -> None:
        self.ntripWriter.write(rtcmFrame)
        await self.ntripWriter.drain()

    async def getRtcmFrame(self):
        rtcm3FramePreample = Bits(bin="0b11010011")
        rtcm3FrameHeaderFormat = "bin:8, pad:6, uint:10"
        rtcmFrameComplete = False
        while not rtcmFrameComplete:
            if self.ntripStreamChunked:
                try:
                    rawLine = await self.ntripReader.readuntil(b"\r\n")
                    length = int(rawLine[:-2].decode("ISO-8859-1"), 16)
                    rawLine = await self.ntripReader.readexactly(length + 2)
                except (
                    asyncio.IncompleteReadError,
                    asyncio.LimitOverrunError,
                ) as error:
                    raise ConnectionError(
                        f"Connection to {self.casterUrl} failed with: {error}"
                        "during data reception."
                    ) from None
                    logging.error(
                        f"Connection to {self.casterUrl} failed with: {error}"
                        "during data reception."
                    )
                if rawLine[-2:] != b"\r\n":
                    logging.error(
                        f"{self.ntripMountPoint}:Chunk malformed. "
                        "Expected \r\n as ending. Closing connection!"
                    )
                    raise IOError("Chunk malformed ")
                receivedBytes = BitStream(rawLine[:-2])
                logging.debug(f"Chunk {receivedBytes.length}:{length * 8}. ")
            else:
                rawLine = await self.ntripReader.read(2048)
                receivedBytes = BitStream(rawLine)
            timeStamp = time()
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
                    firstFrame = rtcmFramePos[0]
                    self.rtcmFrameBuffer = self.rtcmFrameBuffer[firstFrame:]
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
