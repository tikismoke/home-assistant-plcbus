# -*- coding: utf-8 -*-

""" This file is part of B{Domogik} project (U{http://www.domogik.org}).

License
=======

B{Domogik} is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

B{Domogik} is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Domogik. If not, see U{http://www.gnu.org/licenses}.

Plugin purpose
==============

Get event from PLCBUS and send them on Xpl

Implements
==========

- serialHandler

@author: Yoann HINARD <yoann.hinard@gmail.com>
@copyright: (C) 2007-2016 Domogik project
@license: GPL(v3)
@organization: Domogik
"""

import logging
import queue
import threading
import time
from binascii import hexlify

import serial

_LOGGER = logging.getLogger(__name__)


def _to_hex_str(message):
    """Return a Python 3 hex string from serial bytes or an existing hex str."""
    if isinstance(message, bytes):
        return hexlify(message).decode("ascii")
    return message


class serialHandler(threading.Thread):
    """
    Threaded class to handle serial port in PLCbus communication
    Send PLCBUS frames when available in the send_queue and manage
    retransmission if needed
    Put received frames in the receveive_queue (to be sent on the MQ network
    """

    def __init__(self, serial_port_no, command_cb, message_cb):
        """Initialize threaded PLCBUS manager."""
        threading.Thread.__init__(self, daemon=True)
        self._ack = threading.Event()
        self._need_answer = ["1D", "1C"]
        self._stop = threading.Event()
        self._has_message_to_send = threading.Event()
        self._serial = None
        try:
            self._serial = serial.Serial(
                serial_port_no,
                9600,
                timeout=0.4,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=0,
            )
        except serial.SerialException:
            _LOGGER.error("can not open serial port %s", serial_port_no)
            raise
        self._send_queue = queue.Queue()
        self._answer_queue = queue.Queue()
        self._cb = command_cb
        self._msg_cb = message_cb
        self._waited_ack = None

    def explicit_message(self, message):
        """Parse a frame."""
        message = _to_hex_str(message)
        if not isinstance(message, str) or len(message) < 16 or len(message) % 2:
            raise ValueError("PLCBUS frame is truncated")
        if any(char not in "0123456789abcdefABCDEF" for char in message):
            raise ValueError("PLCBUS frame contains non-hexadecimal data")
        if message[:2].lower() != "02":
            raise ValueError("PLCBUS frame has an invalid start byte")

        cmdplcbus = {
            "00": "ALL_UNITS_OFF",
            "01": "ALL_LIGHTS_ON",
            "22": "ON",
            "23": "OFF",
            "24": "DIM",
            "25": "BRIGHT",
            "06": "ALL_LIGHTS_OFF",
            "07": "ALL_USER_LTS_ON",
            "08": "ALL_USER_UNIT_OFF",
            "09": "ALL_USER_LIGHT_OFF",
            "2a": "BLINK",
            "2b": "FADE_STOP",
            "2c": "PRESET_DIM",
            "0d": "STATUS_ON",
            "0e": "STATUS_OFF",
            "0f": "STATUS_REQUEST",
            "30": "REC_MASTER_ADD_SETUP",
            "31": "TRA_MASTER_ADD_SETUP",
            "12": "SCENE_ADR_SETUP",
            "13": "SCENE_ADR_ERASE",
            "34": "ALL_SCENES_ADD_ERASE",
            "15": "FOR FUTURE",
            "16": "FOR FUTURE",
            "17": "FOR FUTURE",
            "18": "GET_SIGNAL_STRENGTH",
            "19": "GET_NOISE_STRENGTH",
            "1a": "REPORT_SIGNAL_STREN",
            "1b": "REPORT_NOISE_STREN",
            "1c": "GET_ALL_ID_PULSE",
            "1d": "GET_ALL_ON_ID_PULSE",
            "1e": "REPORT_ALL_ID_PULSE",
            "1f": "REPORT_ONLY_ON_PULSE",
        }
        home = "ABCDEFGHIJKLMNOP"
        r = {}
        r["start_bit"] = message[0:2]
        r["data_length"] = int(message[2:4], 16)
        if r["data_length"] < 5:
            raise ValueError("PLCBUS frame does not contain all required fields")
        int_length = r["data_length"] * 2
        data_end = 4 + int_length
        if len(message) < data_end + 2:
            raise ValueError("PLCBUS frame is shorter than its declared data length")
        r["data"] = message[4:data_end]
        r["d_user_code"] = r["data"][0:2]
        house_index = int(r["data"][2:3], 16)
        if house_index >= len(home):
            raise ValueError("PLCBUS frame contains an invalid house code")
        r["d_home_unit"] = "%s%s" % (
            home[house_index],
            int(r["data"][3:4], 16) + 1,
        )
        command_key = r["data"][4:6].lower()
        r["d_command"] = cmdplcbus.get(command_key, command_key)
        r["d_data1"] = int(r["data"][6:8], 16)
        r["d_data2"] = int(r["data"][8:10], 16)
        if r["data_length"] == 6:
            r["rx_tw_switch"] = r["data"][11:]
        r["end_bit"] = message[-2:]
        return r

    def _send(self, plcbus_frame):
        """Send a frame and wait for ACK when required."""
        explicit_frame = self.explicit_message(plcbus_frame)
        if (int(plcbus_frame[8:10], 16) >> 5) & 1:
            ACK_received = 0
            time1 = time.time()
            while not self._stop.isSet():
                self._needs_ack_for(plcbus_frame)
                self._basic_write(plcbus_frame)
                time.sleep(0.6)
                _LOGGER.debug("time before wait : %s" % time.time())
                for i in range(3):
                    self.receive()
                    if self._ack.isSet():
                        _LOGGER.debug("got ack in first read")
                        break
                _LOGGER.debug("time after wait : %s" % time.time())
                if self._ack.isSet():
                    _LOGGER.debug("%s : Ack set", plcbus_frame)
                    ACK_received = 1
                    self._ack.clear()
                    self._cb(self.explicit_message(plcbus_frame))
                    break

                if ACK_received == 1:
                    break
                elif time1 + 3.1 < time.time():
                    _LOGGER.error(
                        "WARN : Message %s sent, but ack never received", plcbus_frame
                    )
                    break
        elif explicit_frame["d_command"] not in [
            "GET_ALL_ID_PULSE",
            "GET_ALL_ON_ID_PULSE",
        ]:
            self._basic_write(plcbus_frame)
            _LOGGER.debug("explicit_frame= %s", explicit_frame)
            self._cb(explicit_frame)
        else:
            self._basic_write(plcbus_frame)

    def add_to_send_queue(self, trame):
        _LOGGER.debug("add_to_send_queue : %s", trame)
        self._send_queue.put(trame)

    def get_from_answer_queue(self, timeout=2):
        """Return the next answer frame, or None if none arrives."""
        try:
            return self._answer_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def receive(self):
        """Read available frames from the adapter."""
        if self._stop.isSet() or self._serial is None:
            return
        waiting = self._serial.in_waiting if hasattr(self._serial, "in_waiting") else self._serial.inWaiting()
        if waiting < 9:
            time.sleep(0.4)
            return
        while True:
            waiting = (
                self._serial.in_waiting
                if hasattr(self._serial, "in_waiting")
                else self._serial.inWaiting()
            )
            if waiting < 9:
                break
            try:
                message = self._serial.read(9)
            except (OSError, serial.SerialException, TypeError):
                return
            if not message:
                continue
            m_string = _to_hex_str(message)
            _LOGGER.debug("str : %s", m_string)
            try:
                parsed_message = self.explicit_message(m_string)
            except ValueError as err:
                _LOGGER.warning("Ignoring malformed PLCBUS frame %s: %s", m_string, err)
                continue
            if self._is_from_myself(m_string):
                _LOGGER.debug("from myself")
                continue
            if self._is_answer(m_string):
                _LOGGER.debug("ANSWER : %s", m_string)
                self._answer_queue.put(m_string)
                self._cb(parsed_message)
            elif self._is_ack(m_string):
                if self._waited_ack is not None:
                    _LOGGER.debug(
                        "IS ACK : %s, waited ack : %s", m_string, self._waited_ack
                    )
                    if self._is_ack_for_message(m_string, self._waited_ack):
                        self._waited_ack = None
                        self._ack.set()
                else:
                    _LOGGER.debug("Ack not attend send from another programs?")
                    self._cb(parsed_message)
            else:
                _LOGGER.debug("QUEUE : %s", m_string)
                self._cb(parsed_message)

    def stop(self):
        """Ask the thread to stop and close the serial port."""
        self._stop.set()
        if self._serial is not None:
            try:
                self._serial.close()
            except OSError:
                pass

    def run(self):
        """Serial handler main thread."""
        while not self._stop.isSet():
            try:
                item = self._send_queue.get_nowait()
            except queue.Empty:
                pass
            else:
                self._send(item)
            self.receive()
            time.sleep(1)

    def _needs_ack_for(self, frame):
        """Let the reader know that an ACK is waited."""
        self._waited_ack = frame

    def _is_ack(self, message):
        """Check if a message is an ack."""
        message = _to_hex_str(message)
        return int(message[14:16], 16) & 0x20

    def _is_from_myself(self, message):
        """Check if a message is sent by the adapter itself."""
        message = _to_hex_str(message)
        return int(message[14:16], 16) & 0x10

    def _is_ack_for_message(self, m1, m2):
        m1 = _to_hex_str(m1)
        m2 = _to_hex_str(m2)
        _LOGGER.debug("ACK check  %s %s ", m1, m2)
        if (m1[4:8].upper() == m2[4:8].upper()) and (
            m1[8:10].upper() == m2[8:10].upper()
        ):
            _LOGGER.debug("housecode and usercode OK")
            return int(m1[14:16], 16) & 0x20
        return False

    def _is_answer(self, message):
        message = _to_hex_str(message).upper()
        if (int(message[14:15], 16) >> 2 & 1) and message[8:10] in ["1C", "1D"]:
            return True
        return False

    def _basic_write(self, frame):
        """Write a frame on serial port."""
        if self._serial is None:
            _LOGGER.error("Serial port is not open")
            return
        _LOGGER.debug("SEND : %s", frame)
        try:
            self._serial.write(bytes.fromhex(frame))
        except (OSError, serial.SerialException, TypeError, ValueError) as err:
            _LOGGER.error("Failed to write PLCBUS frame %s: %s", frame, err)
