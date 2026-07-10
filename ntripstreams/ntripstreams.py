#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Asynchronous NTRIP client/server communication.

Defines :class:`NtripStream`, an ``asyncio``-based class for connecting to an
NTRIP caster, requesting source tables and streams, publishing as a server, and
framing RTCM 3 messages from the received byte stream.

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
    """An asyncio NTRIP client and server connection.

    A single instance holds the connection to one caster and the state used
    while framing RTCM 3 messages. Typical client use is to call
    :meth:`requestSourcetable` to list mountpoints, or
    :meth:`requestNtripStream` followed by repeated :meth:`getRtcmFrame` calls
    to read the stream. Server use publishes with :meth:`requestNtripServer`
    and :meth:`sendRtcmFrame`.
    """

    def __init__(self):
        self.__CLIENTVERSION = __version__
        self.__CLIENTNAME = "Bedrock_Solutions_NtripClient/" + f"{self.__CLIENTVERSION}"
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
        """Open a TCP (or TLS) connection to an NTRIP caster.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
            The ``https`` scheme opens a TLS connection.

        Raises
        ------
        TimeoutError
            If the connection attempt times out.
        OSError
            If the connection cannot be established.

        Returns
        -------
        bool
            ``True`` once the connection is open and ready to write.
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
            logging.error(f"Connection to {casterUrl} timed out: {error}")
            raise TimeoutError(
                f"Connection to {casterUrl} timed out: {error}"
            ) from None
        except OSError as error:
            logging.error(f"Connection to {casterUrl} failed with: {error}")
            raise OSError(f"Connection to {casterUrl} failed with: {error}") from None
        logging.info(
            f"{self.ntripMountPoint}: Connection to {casterUrl} open. "
            "Ready to write."
        )
        return True

    def setRequestSourceTableHeader(self, casterUrl: str) -> None:
        """Build the request header used to fetch a caster's source table.

        The result is stored on ``self.ntripRequestHeader``.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
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
        """Build the request header used to consume an NTRIP stream (client).

        The result is stored on ``self.ntripRequestHeader``.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
        ntripMountPoint : str
            Mountpoint name, without the leading ``/``.
        ntripUser : str, optional
            Username for basic authentication. The default is None.
        ntripPassword : str, optional
            Password for basic authentication. The default is None.
        nmeaString : str, optional
            NMEA GGA sentence sent to request a virtual reference station.
            The default is None.
        """
        self.casterUrl = urlsplit(casterUrl)
        self.ntripMountPoint = ntripMountPoint
        timestamp = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
        if nmeaString:
            # NTRIP 2.0 (sec. 2.1.3): the position is sent as an Ntrip-GGA
            # header line, not as a bare NMEA line inside the header block.
            self.nmeaString = f"Ntrip-GGA: {nmeaString.rstrip(chr(13) + chr(10))}\r\n"
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
        """Build the request header used to publish a stream (server).

        The result is stored on ``self.ntripRequestHeader``. NTRIP version 2
        uses an HTTP ``POST`` with basic authentication; version 1 uses the
        legacy ``SOURCE`` request with the password only.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
        ntripMountPoint : str
            Mountpoint name, without the leading ``/``.
        ntripUser : str, optional
            Username for basic authentication (NTRIP 2 only). The default
            is None.
        ntripPassword : str, optional
            Password / upload token. The default is None.
        ntripVersion : int, optional
            NTRIP protocol version, 1 or 2. The default is 2.
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
            # NTRIP 1.0 (sec. 2.2): the SOURCE request carries the password in
            # clear text (no user name, not Base64) directly after SOURCE.
            sourcePassword = ntripPassword if ntripPassword else ""
            self.ntripRequestHeader = (
                f"SOURCE {sourcePassword} "
                f"/{ntripMountPoint} HTTP/1.1\r\n"
                "Source-Agent: NTRIP "
                f"{self.__CLIENTNAME}\r\n"
                "\r\n"
            ).encode("ISO-8859-1")

    def getHeaderStrings(self, rawHeader: Union[bytes, list]) -> list:
        """Decode a raw header into a list of stripped ISO-8859-1 lines.

        Parameters
        ----------
        rawHeader : bytes or list of bytes
            Either a single ``bytes`` blob (split on CRLF) or a list of raw
            header line ``bytes``.

        Returns
        -------
        list of str
            The decoded header lines with trailing whitespace removed.
        """
        if isinstance(rawHeader, bytes):
            headerStrings = rawHeader.decode("ISO-8859-1").split("\r\n")
        if isinstance(rawHeader, list):
            headerStrings = []
            for rawLine in rawHeader:
                headerStrings.append(rawLine.decode("ISO-8859-1").rstrip())
        return headerStrings

    async def getNtripResponseHeader(self) -> None:
        """Read and parse the caster's HTTP response header.

        Populates ``self.ntripResponseHeader``, ``self.ntripStreamChunked`` and
        ``self.ntripResponseStatusCode``.

        Raises
        ------
        ConnectionError
            If the connection fails while reading the response header.
        """
        self.ntripResponseHeader = []
        ntripResponseHeaderTimestamp = []
        rawHeader = []
        while True:
            try:
                line = await self.ntripReader.readline()
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as error:
                logging.error(f"Connection to {self.casterUrl} failed with: {error}")
                raise ConnectionError(
                    f"Connection to {self.casterUrl} failed with: {error}"
                ) from None
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
        if statusResponse[0] == "OK":
            # NTRIP 1.0 (sec. 2.2): an NtripServer upload is acknowledged with a
            # bare "OK" instead of a numeric status code.
            self.ntripResponseStatusCode = "200"
        elif len(statusResponse) > 1:
            self.ntripResponseStatusCode = statusResponse[1]
        else:
            self.ntripResponseStatusCode = 0

    def ntripResponseStatusOk(self) -> bool:
        """Check whether the caster returned HTTP status 200.

        Raises
        ------
        ConnectionError
            If the status code is not 200; the writer is closed first and the
            response header lines are logged.

        Returns
        -------
        bool
            ``True`` when the caster responded with status 200.
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
            self.ntripWriter.close()
            raise ConnectionError(
                f"{self.ntripMountPoint}: {self.ntripResponseHeader[0]}"
            )

    async def sendRequestHeader(self) -> None:
        """Send the prepared request header and read the caster's response.

        Writes ``self.ntripRequestHeader`` to the caster, then reads the
        response header and validates the status code.
        """
        self.ntripWriter.write(self.ntripRequestHeader)
        await self.ntripWriter.drain()
        logging.info(f"{self.ntripMountPoint}: Request sent.")
        await self.getNtripResponseHeader()
        if self.ntripResponseStatusOk():
            for line in self.ntripResponseHeader:
                logging.debug(f"TCP response: {line}")

    async def _readChunkedBody(self) -> bytes:
        """Read an HTTP chunked-transfer body and return the decoded bytes.

        Reads chunks until the terminating zero-length chunk or end of stream,
        stripping the hex size lines and any ``;extension`` (RTCM 10410.1
        sec. 2.4).

        Returns
        -------
        bytes
            The concatenated chunk payloads.
        """
        body = bytearray()
        while True:
            try:
                sizeLine = await self.ntripReader.readuntil(b"\r\n")
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                break
            sizeField = sizeLine[:-2].split(b";", 1)[0].strip()
            if not sizeField:
                continue
            try:
                length = int(sizeField, 16)
            except ValueError:
                break
            if length == 0:
                break
            try:
                chunk = await self.ntripReader.readexactly(length + 2)
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                break
            body += chunk[:-2]
        return bytes(body)

    async def requestSourcetable(self, casterUrl: str) -> list:
        """Connect to a caster and return its full source table.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.

        Raises
        ------
        ConnectionError
            If the connection fails while receiving the source table.

        Returns
        -------
        list of str
            The source table lines, ending with ``ENDSOURCETABLE``.
        """
        await self.openNtripConnection(casterUrl)
        self.setRequestSourceTableHeader(casterUrl)
        await self.sendRequestHeader()
        ntripSourcetable = []
        if self.ntripStreamChunked:
            # A caster may send the source table with chunked transfer encoding
            # (RTCM 10410.1 sec. 2.4); decode it before splitting into lines.
            body = await self._readChunkedBody()
            for line in body.decode("ISO-8859-1").splitlines():
                ntripSourcetable.append(line)
                if line == "ENDSOURCETABLE":
                    break
            self.ntripWriter.close()
            logging.info("Sourcetabel received.")
        else:
            while True:
                try:
                    line = await self.ntripReader.readline()
                except (
                    asyncio.IncompleteReadError,
                    asyncio.LimitOverrunError,
                ) as error:
                    logging.error(
                        f"Connection to {self.casterUrl} failed with: {error}"
                    )
                    raise ConnectionError(
                        f"Connection to {self.casterUrl} failed with: {error}"
                    ) from None
                if not line:
                    break
                line = line.decode("ISO-8859-1").rstrip()
                ntripSourcetable.append(line)
                if line == "ENDSOURCETABLE":
                    self.ntripWriter.close()
                    logging.info("Sourcetabel received.")
                    break
        return ntripSourcetable

    async def requestNtripServer(
        self,
        casterUrl: str,
        mountPoint: str,
        user: str = None,
        passwd: str = None,
        ntripVersion: int = 2,
    ) -> None:
        """Connect to a caster and send a server (upload) request header.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
        mountPoint : str
            Mountpoint name to publish to, without the leading ``/``.
        user : str, optional
            Username for basic authentication (NTRIP 2 only). The default
            is None.
        passwd : str, optional
            Password / upload token. The default is None.
        ntripVersion : int, optional
            NTRIP protocol version, 1 or 2. The default is 2.
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
        """Connect to a caster and send a client (stream) request header.

        Parameters
        ----------
        casterUrl : str
            Caster URL and port, e.g. ``http[s]://caster.hostname.net:port``.
        mountPoint : str
            Mountpoint name to consume, without the leading ``/``.
        user : str, optional
            Username for basic authentication. The default is None.
        passwd : str, optional
            Password for basic authentication. The default is None.
        """
        self.ntripMountPoint = mountPoint
        await self.openNtripConnection(casterUrl)
        self.setRequestStreamHeader(
            self.casterUrl.geturl(), self.ntripMountPoint, user, passwd
        )
        await self.sendRequestHeader()

    async def sendRtcmFrame(self, rtcmFrame: BitStream) -> None:
        """Send a single RTCM 3 frame to the caster.

        Parameters
        ----------
        rtcmFrame : bitstring.BitStream
            A complete RTCM 3 frame (preamble, payload and CRC). It is
            converted to bytes before being written.
        """
        self.ntripWriter.write(rtcmFrame.tobytes())
        await self.ntripWriter.drain()

    async def getRtcmFrame(self):
        """Read the next complete, CRC-validated RTCM 3 frame from the stream.

        Data is buffered until a frame preamble is found and the frame is
        CRC-24Q verified; on a CRC mismatch the buffer is realigned and the
        search continues.

        Raises
        ------
        ConnectionError
            If the connection fails while receiving data.
        IOError
            If a chunk is malformed or incomplete.

        Returns
        -------
        tuple of (bitstring.BitStream, float)
            The validated RTCM 3 frame and the Unix timestamp at which it was
            received.
        """
        rtcm3FramePreample = Bits(bin="0b11010011")
        rtcm3FrameHeaderFormat = "bin:8, pad:6, uint:10"
        rtcmFrameComplete = False
        while not rtcmFrameComplete:
            timeStamp = time()
            # Only read from the socket when the buffer is running low so it does
            # not grow faster than frames are consumed. The 16384-bit (2048-byte)
            # low-water mark stays well above the maximum RTCM3 frame size
            # (8232 bits) so any single frame can always be fully accumulated.
            if self.rtcmFrameBuffer.length < 16384:
                if self.ntripStreamChunked:
                    try:
                        rawLine = await self.ntripReader.readuntil(b"\r\n")
                        length = int(rawLine[:-2].decode("ISO-8859-1"), 16)
                        rawLine = await self.ntripReader.readexactly(length + 2)
                    except (
                        asyncio.IncompleteReadError,
                        asyncio.LimitOverrunError,
                    ) as error:
                        logging.error(
                            f"Connection to {self.casterUrl} failed with: {error}"
                            "during data reception."
                        )
                        raise ConnectionError(
                            f"Connection to {self.casterUrl} failed with: {error}"
                            "during data reception."
                        ) from None
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
                # Reset the read position before peeking: bitstring >= 4.1.0 no
                # longer guarantees pos == 0 after slicing/concatenating the
                # buffer, which would otherwise peek the header at a wrong offset.
                self.rtcmFrameBuffer.pos = 0
                rtcmPreAmple, rtcmPayloadLength = self.rtcmFrameBuffer.peeklist(
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
