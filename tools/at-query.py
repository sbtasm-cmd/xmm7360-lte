#!/usr/bin/env python3
# Run as root. Sends read-only AT queries to the spare AT port (wwan0at0, unused by ModemManager).
import os, select, time
QUERIES = [("ATE0", 3), ("AT+CFUN?", 3), ("AT+XSIMSTATE?", 3), ("AT+CPIN?", 3),
           ("AT+COPS?", 3), ("AT+CREG?", 3), ("AT+CEREG?", 3), ("AT+CSQ", 3),
           ("AT+XCESQ?", 3), ("AT+XACT?", 3), ("AT+XBANDSEL?", 3), ("AT+CEER", 3),
           ("AT+XLEC?", 3), ("AT+GTSET?", 3), ("AT+COPS=?", 180)]
fd = os.open("/dev/wwan0at0", os.O_RDWR | os.O_NOCTTY)
def ask(cmd, timeout):
    os.read(fd, 65536) if select.select([fd], [], [], 0.2)[0] else None
    os.write(fd, (cmd + "\r").encode())
    buf, end = b"", time.time() + timeout
    while time.time() < end:
        if select.select([fd], [], [], 0.5)[0]:
            buf += os.read(fd, 65536)
            if any(t in buf for t in (b"\r\nOK\r\n", b"ERROR")):
                break
    return buf.decode(errors="replace").strip().replace("\r\n", " | ")
for cmd, t in QUERIES:
    print(f"{cmd:16} -> {ask(cmd, t) or '(no answer)'}", flush=True)
