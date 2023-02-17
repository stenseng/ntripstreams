#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  7 11:15:55 2021

@author: Lars Stenseng
@mail: lars@stenseng.net
"""

import logging
from time import time

from bitstring import Bits, pack


class Rtcm3:
    def __init__(self):
        pass

    def mjd(self, unixTimestamp):
        mjd = int(unixTimestamp / 86400.0 + 40587.0)
        return mjd

    def msmConstellation(self, messageType: int):
        constellation = self.__msmConstellations[int(messageType / 10) % 100]
        return constellation

    def constellation(self, messageType: int):
        if messageType >= 1001 and messageType <= 1004:
            constellation = self.__msmConstellations[7]
        elif messageType >= 1009 and messageType <= 1012:
            constellation = self.__msmConstellations[8]
        elif messageType >= 1071 and messageType <= 1127:
            constellation = self.msmConstellation(messageType)
        else:
            constellation = "GNSS"
        return constellation

    def msmSignalTypes(self, messageType: int, msmSignals):
        signals = [
            self.__msmSignalTypes[self.constellation(messageType)][i]
            for i, mask in enumerate(msmSignals)
            if mask == "1"
        ]
        return signals

    def encodeRtcmFrame(self, messageType: int, dataDict):
        message = self.encodeRtcmMessage(messageType, dataDict)
        rtcmFrame = message
        return rtcmFrame

    def decodeRtcmFrame(self, rtcmFrame):
        rtcmPayload = rtcmFrame[24:-24]
        messageType, data = self.decodeRtcmMessage(rtcmPayload)
        return messageType, data

    def encodeRtcmMessage(self, messageType: int, dataDict):
        if messageType == 1029:
            utfStr = "Default string"
            default = {
                "refStationId": 0,
                "mjd": self.mjd(time()),
                "utc": int(time() % 86400),
                "utfChars": 0,
                "charBytes": 0,
                "string": utfStr,
            }
            data = {key: dataDict.get(key, default[key]) for key in default}
            data["utfChars"] = len(data["string"])
            data["string"] = data["string"].encode()
            data["charBytes"] = len(data["string"])
            message = pack(self.__msg1029, **data)
            return message

    def __decodeMsmHeader(self, message):
        head = message.readlist(self.__msgMsmHead)
        numSats = Bits(bin=head[9]).bin.count("1")
        numSignals = Bits(bin=head[10]).bin.count("1")
        cellMask = message.read(f"bin:{numSats * numSignals}")
        head.append(cellMask)
        numCells = Bits(bin=head[11]).bin.count("1")
        if head[0] >= 1081 and head[0] <= 1087:
            glonassEpoch = message.unpack(self.__msgMsmHeadGlonassEpoch)
            head[2] = glonassEpoch[1]
            head.append(glonassEpoch[0])
        return head, numSats, numSignals, numCells

    def decodeRtcmMessage(self, message):
        data = []
        head = []
        satData = []
        signalData = []
        messageType = message.peek("uint:12")
        logging.debug(f"Decoding message type {messageType}")
        if messageType == 1001:
            head = message.readlist(self.__msg1001Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1001Obs))
        elif messageType == 1002:
            head = message.readlist(self.__msg1002Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1002Obs))
        elif messageType == 1003:
            head = message.readlist(self.__msg1003Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1003Obs))
        elif messageType == 1004:
            head = message.readlist(self.__msg1004Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1004Obs))

        elif messageType == 1009:
            head = message.readlist(self.__msg1009Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1009Obs))
        elif messageType == 1010:
            head = message.readlist(self.__msg1010Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1010Obs))
        elif messageType == 1011:
            head = message.readlist(self.__msg1011Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1011Obs))
        elif messageType == 1012:
            head = message.readlist(self.__msg1012Head)
            for _ in range(head[4]):
                satData.append(message.readlist(self.__msg1012Obs))

        elif (
            (messageType >= 1071 and messageType <= 1077)
            or (messageType >= 1081 and messageType <= 1087)
            or (messageType >= 1091 and messageType <= 1097)
            or (messageType >= 1101 and messageType <= 1107)
            or (messageType >= 1111 and messageType <= 1117)
            or (messageType >= 1121 and messageType <= 1127)
        ):
            head, numSats, numSignals, numCells = self.__decodeMsmHeader(message)
            if (
                (messageType % 10 == 1)
                or (messageType % 10 == 2)
                or (messageType % 10 == 3)
            ):
                for obs in self.__msgMsm123Sat:
                    satData.append(message.readlist(f"{numSats}*{obs}"))
            elif (messageType % 10 == 4) or (messageType % 10 == 6):
                for obs in self.__msgMsm46Sat:
                    satData.append(message.readlist(f"{numSats}*{obs}"))
            elif (messageType % 10 == 5) or (messageType % 10 == 7):
                for obs in self.__msgMsm57Sat:
                    satData.append(message.readlist(f"{numSats}*{obs}"))
            satData = [[row[i] for row in satData] for i in range(len(satData[0]))]

            if messageType % 10 == 1:
                for obs in self.__msgMsm1Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            elif messageType % 10 == 2:
                for obs in self.__msgMsm2Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            elif messageType % 10 == 3:
                for obs in self.__msgMsm3Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            elif messageType % 10 == 4:
                for obs in self.__msgMsm4Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            elif messageType % 10 == 5:
                for obs in self.__msgMsm5Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            elif messageType % 10 == 6:
                for obs in self.__msgMsm6Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            elif messageType % 10 == 7:
                for obs in self.__msgMsm7Signal:
                    signalData.append(message.readlist(f"{numCells}*{obs}"))
            signalData = [
                [row[i] for row in signalData] for i in range(len(signalData[0]))
            ]

        elif messageType == 1029:
            head = message.readlist(self.__msg1029)
        else:
            head = "Message type not implemented"
        data = [head, satData, signalData]
        return messageType, data

    def messageDescription(self, messageType: int):
        if messageType in self.messageDescriptionText:
            return self.messageDescriptionText[messageType]
        else:
            return f"Message type {messageType} currently not implemented"

    messageDescriptionText = {
        1001: "L1-Only GPS RTK Observables",
        1002: "Extended L1-Only GPS RTK Observables",
        1003: "L1 & L2 GPS RTK Observables",
        1004: "Extended L1 & L2 GPS RTK Observables",
        1005: "Stationary RTK Reference Station ARP",
        1006: "Stationary RTK Reference Station ARP with Antenna Height",
        1007: "Antenna Descriptor",
        1008: "Antenna Descriptor & Serial Number",
        1009: "L1-Only GLONASS RTK Observables",
        1010: "Extended L1-Only GLONASS RTK Observables",
        1011: "L1 & L2 GLONASS RTK Observables",
        1012: "Extended L1 & L2 GLONASS RTK Observables",
        1013: "System Parameters",
        1014: "Network Auxiliary Station Data",
        1015: "GPS Ionospheric Correction Differences",
        1016: "GPS Geometric Correction Differences",
        1017: "GPS Combined Geometric and Ionospheric Correction " + "Differences",
        1018: "RESERVED for Alternative Ionospheric Correction Difference " + "Message",
        1019: "GPS Ephemerides",
        1020: "GLONASS Ephemerides",
        1021: "Helmert / Abridged Molodenski Transformation Parameters",
        1022: "Molodenski-Badekas Transformation Parameters",
        1023: "Residuals, Ellipsoidal Grid Representation",
        1024: "Residuals, Plane Grid Representation",
        1025: "Projection Parameters, Projection Types other than "
        + "Lambert Conic Conformal (2 SP) and Oblique Mercator",
        1026: "Projection Parameters, Projection Type LCC2SP "
        + "(Lambert Conic Conformal (2 SP))",
        1027: "Projection Parameters, Projection Type OM " + "(Oblique Mercator)",
        1028: "(Reserved for Global to Plate-Fixed Transformation)",
        1029: "Unicode Text String",
        1030: "GPS Network RTK Residual Message",
        1031: "GLONASS Network RTK Residual Message",
        1032: "Physical Reference Station Position Message",
        1033: "Receiver and Antenna Descriptors",
        1034: "GPS Network FKP Gradient",
        1035: "GLONASS Network FKP Gradient",
        1037: "GLONASS Ionospheric Correction Differences",
        1038: "GLONASS Geometric Correction Differences",
        1039: "GLONASS Combined Geometric and Ionospheric Correction " + "Differences",
        1042: "BDS Satellite Ephemeris Data",
        1044: "QZSS Ephemerides",
        1045: "Galileo F/NAV Satellite Ephemeris Data",
        1046: "Galileo I/NAV Satellite Ephemeris Data",
        1057: "SSR GPS Orbit Correction",
        1058: "SSR GPS Clock Correction",
        1059: "SSR GPS Code Bias",
        1060: "SSR GPS Combined Orbit and Clock Corrections",
        1061: "SSR GPS URA",
        1062: "SSR GPS High Rate Clock Correction",
        1063: "SSR GLONASS Orbit Correction",
        1064: "SSR GLONASS Clock Correction",
        1065: "SSR GLONASS Code Bias",
        1066: "SSR GLONASS Combined Orbit and Clock Corrections",
        1067: "SSR GLONASS URA",
        1068: "SSR GLONASS High Rate Clock Correction",
        1070: "Reserved MSM",
        1071: "GPS MSM1",
        1072: "GPS MSM2",
        1073: "GPS MSM3",
        1074: "GPS MSM4",
        1075: "GPS MSM5",
        1076: "GPS MSM6",
        1077: "GPS MSM7",
        1078: "Reserved MSM",
        1079: "Reserved MSM",
        1080: "Reserved MSM",
        1081: "GLONASS MSM1",
        1082: "GLONASS MSM2",
        1083: "GLONASS MSM3",
        1084: "GLONASS MSM4",
        1085: "GLONASS MSM5",
        1086: "GLONASS MSM6",
        1087: "GLONASS MSM7",
        1088: "Reserved MSM",
        1089: "Reserved MSM",
        1090: "Reserved MSM",
        1091: "Galileo MSM1",
        1092: "Galileo MSM2",
        1093: "Galileo MSM3",
        1094: "Galileo MSM4",
        1095: "Galileo MSM5",
        1096: "Galileo MSM6",
        1097: "Galileo MSM7",
        1098: "Reserved MSM",
        1099: "Reserved MSM",
        1100: "Reserved MSM",
        1101: "SBAS MSM1",
        1102: "SBAS MSM2",
        1103: "SBAS MSM3",
        1104: "SBAS MSM4",
        1105: "SBAS MSM5",
        1106: "SBAS MSM6",
        1107: "SBAS MSM7",
        1108: "Reserved MSM",
        1109: "Reserved MSM",
        1110: "Reserved MSM",
        1111: "QZSS MSM1",
        1112: "QZSS MSM2",
        1113: "QZSS MSM3",
        1114: "QZSS MSM4",
        1115: "QZSS MSM5",
        1116: "QZSS MSM6",
        1117: "QZSS MSM7",
        1118: "Reserved MSM",
        1119: "Reserved MSM",
        1120: "Reserved MSM",
        1121: "BeiDou MSM1",
        1122: "BeiDou MSM2",
        1123: "BeiDou MSM3",
        1124: "BeiDou MSM4",
        1125: "BeiDou MSM5",
        1126: "BeiDou MSM6",
        1127: "BeiDou MSM7",
        1128: "Reserved MSM",
        1129: "Reserved MSM",
        1130: "Reserved MSM",
        1131: "IRNSS MSM1 (Experimental, not implemented)",
        1132: "IRNSS MSM2 (Experimental, not implemented)",
        1133: "IRNSS MSM3 (Experimental, not implemented)",
        1134: "IRNSS MSM4 (Experimental, not implemented)",
        1135: "IRNSS MSM5 (Experimental, not implemented)",
        1136: "IRNSS MSM6 (Experimental, not implemented)",
        1137: "IRNSS MSM7 (Experimental, not implemented)",
        1138: "Reserved MSM (Experimental)",
        1139: "Reserved MSM (Experimental)",
        1140: "Reserved MSM (Experimental)",
        1230: "GLONASS L1 and L2 Code-Phase Biases"
        # 4001-4095: "Proprietary Messages"
    }

    __framePreample = Bits(bin="0b11010011")
    __frameHeaderFormat = "bin:8, pad:6, uint:10, uint:12"
    __frameFormat = "bin:8, pad:6, uint:10"

    # GPS messages
    __msg1001_4Head = (
        "uint:12=refStationId, uint:30=tow, bool=syncGNSSFlag, "
        "uint:5=numSignalsObs, bool=divFreeSmootFlag, bin:3=smoothInterval"
    )
    __msg1001Head = "uint:12=1001, " + __msg1001_4Head
    __msg1002Head = "uint:12=1002, " + __msg1001_4Head
    __msg1003Head = "uint:12=1003, " + __msg1001_4Head
    __msg1004Head = "uint:12=1004, " + __msg1001_4Head
    __msg1001Obs = (
        "uint:6=satId, bool=l1CodeFlag, uint:24=l1PseudoRange, "
        "int:20=l1PhaserangeL1PseudorangeDiff, uint:7=l1LockTimeIndicator"
    )
    __msg1002Obs = __msg1001Obs + "uint:8=l1PseudorangeAmbiguity, uint:8=l1CNR"
    __msg1003Obs = (
        __msg1001Obs + "bool=l2CodeFlag, uint:24=l2L1PseudorangeDiff, "
        "int:20=l2PhaserangeL1PseudorangeDiff, uint:7=l2LockTimeIndicator"
    )
    __msg1004Obs = (
        __msg1002Obs + "bool=l2CodeFlag, uint:24=l2L1PseudorangeDiff, "
        "int:20=l2PhaserangeL1PseudorangeDiff, uint:7=l2LockTimeIndicator, "
        "uint:8=l2CNR"
    )

    # GLONASS messages
    __msg1009_12Head = (
        "uint:12=refStationId, uint:27=epochTime, bool=syncGNSSFlag, "
        "uint:5=numSignalsObs, bool=divFreeSmootFlag, bin:3=smoothInterval"
    )
    __msg1009Head = "uint:12=1009, " + __msg1009_12Head
    __msg1010Head = "uint:12=1010, " + __msg1009_12Head
    __msg1011Head = "uint:12=1011, " + __msg1009_12Head
    __msg1012Head = "uint:12=1012, " + __msg1009_12Head
    __msg1009Obs = (
        "uint:6=satId, bool=codeFlag, uint:5=freqChannelnum,  uint:24=l1Pseudorange, "
        "int:20=l1PhaserangeL1PseudorangeDiff, uint:7=l1LockTimeIndicator"
    )
    __msg1010Obs = __msg1009Obs + "uint:8=l1PseudorangeAmbiguity, uint:8=l1CNR"
    __msg1011Obs = (
        __msg1009Obs + "bool=l2CodeFlag, uint:24=l2L1PseudorangeDiff, "
        "int:20=l2PhaserangeL1PseudorangeDiff, uint:7=l2LockTimeIndicator"
    )
    __msg1012Obs = (
        __msg1010Obs + "bool=l2CodeFlag, uint:24=l2L1PseudorangeDiff, "
        "int:20=l2PhaserangeL1PseudorangeDiff, uint:7=l2LockTimeIndicator, "
        "uint:8=l2CNR"
    )

    # Other messages
    __msg1029 = (
        "uint:12=1029, uint:12=refStationId, uint:16=mjd, "
        "uint:17=utc, uint:7=utfChars, uint:8=charBytes, "
        "bytes=string"
    )

    # MSM messages
    __msgMsmHead = (
        "uint:12=messageType, uint:12=refStationId, uint:30=gnssEpochTime, "
        "bool=multiMessageFlag, uint:3=iods, pad:7, uint:2=clockSteringIndicator, "
        "uint:2=extClockIndicator, bool=divFreeSmootFlag, bin:3=smoothInterval, "
        "bin:64=gnssSatMask, bin:32=gnssSignalMask"
    )
    __msgMsmHeadGlonassEpoch = "pad:24, uint:3=dayOfWeek, uint:27=gnssEpochTime"
    __msgMsm123Sat = ["uint:10=roughRangeMod1ms"]
    __msgMsm46Sat = ["uint:8=numIntMsRoughRange", "uint:10=roughRangeMod1ms"]
    __msgMsm57Sat = [
        "uint:8=numIntMsRoughRange",
        "uint:4=extSatInfo",
        "uint:10=roughRangeMod1ms",
        "int:14=roughPhaseRangeRate",
    ]
    __msgMsm1Signal = ["int:15=signalFinePseudorange"]
    __msgMsm2Signal = [
        "int:22=signalFinePhaserange",
        "uint:4=phaserangeLockTimeIndicator",
        "bool=halfcycleAmbiguity",
    ]
    __msgMsm3Signal = __msgMsm1Signal + __msgMsm2Signal
    __msgMsm4Signal = __msgMsm3Signal + ["uint:6=signalCNR"]
    __msgMsm5Signal = __msgMsm4Signal + ["int:15=signalFinePhaserangeRate"]
    __msgMsm6Signal = [
        "int:20=signalFinePseudorangeExtRes",
        "int:24=signalFinePhaserangeExtRes",
        "uint:10=phaserangeLockTimeIndicatorExtRes",
        "bool=halfcycleAmbiguity",
        "uint:10=signalCNRExtRes",
    ]
    __msgMsm7Signal = __msgMsm6Signal + ["int:15=signalFinePhaserangeRate"]

    # MSM observation types
    __msmSignalTypes = {
        "GPS": [
            "Res",
            "L1C",
            "L1P",
            "L1W",
            "Res",
            "Res",
            "Res",
            "L2C",
            "L2P",
            "L2W",
            "Res",
            "Res",
            "Res",
            "Res",
            "L2S",
            "L2L",
            "L2X",
            "Res",
            "Res",
            "Res",
            "Res",
            "L5I",
            "L5Q",
            "L5X",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "L1S",
            "L1L",
            "L1X",
        ],
        "GLONASS": [
            "Res",
            "G1C",
            "G1P",
            "Res",
            "Res",
            "Res",
            "Res",
            "G2C",
            "G2P",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
        ],
        "GALILEO": [
            "Res",
            "E1C",
            "E1A",
            "E1B",
            "E1X",
            "E1Z",
            "Res",
            "E6C",
            "E6A",
            "E6B",
            "E6X",
            "E6Z",
            "Res",
            "E7I",
            "E7Q",
            "E7X",
            "Res",
            "E8I",
            "E8Q",
            "E8X",
            "Res",
            "E5I",
            "E5Q",
            "E5X",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
        ],
        "BEIDOU": [
            "Res",
            "B2I",
            "B2Q",
            "B2X",
            "Res",
            "Res",
            "Res",
            "B6I",
            "B6Q",
            "B6X",
            "Res",
            "Res",
            "Res",
            "B7I",
            "B7Q",
            "B7X",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
        ],
        "QZSS": [
            "Res",
            "L1C",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "L6S",
            "L6L",
            "L6X",
            "Res",
            "Res",
            "Res",
            "L2S",
            "L2L",
            "L2X",
            "Res",
            "Res",
            "Res",
            "Res",
            "L5I",
            "L5Q",
            "L5X",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "L1S",
            "L1L",
            "L1X",
        ],
        "SBAS": [
            "Res",
            "L1C",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "L5I",
            "L5Q",
            "L5X",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
            "Res",
        ],
    }

    # MSM constellations
    __msmConstellations = {
        7: "GPS",
        8: "GLONASS",
        9: "GALILEO",
        10: "SBAS",
        11: "QZSS",
        12: "BEIDOU",
    }
