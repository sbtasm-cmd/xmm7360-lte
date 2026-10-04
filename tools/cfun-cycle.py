#!/usr/bin/env python3
# Run as root. With ModemManager stopped: radio off/on via AT+CFUN, then automatic
# network selection, polling signal/registration. Nothing persistent is changed.
import os, select, time, subprocess

def ask(fd, cmd, timeout=5):
    while select.select([fd], [], [], 0.2)[0]:
        os.read(fd, 65536)
    os.write(fd, (cmd + "\r\n").encode())
    buf, end = b"", time.time() + timeout
    while time.time() < end and b"OK\r\n" not in buf and b"ERROR" not in buf:
        if select.select([fd], [], [], 0.5)[0]:
            buf += os.read(fd, 65536)
    out = buf.decode(errors="replace").strip().replace("\r\n", " | ") or "(no answer)"
    print(f"{time.strftime('%H:%M:%S')} {cmd:14} -> {out}", flush=True)

subprocess.run(["systemctl", "stop", "ModemManager.service"], check=True)
time.sleep(2)
fd = os.open("/dev/wwan0at1", os.O_RDWR | os.O_NOCTTY)
try:
    for c in ["ATE0", "AT+CMEE=2", "AT+CEREG=2", "AT+CFUN=4"]:
        ask(fd, c, 15)
    time.sleep(5)
    ask(fd, "AT+CFUN=1", 30)
    time.sleep(10)
    ask(fd, "AT+COPS=0", 90)
    for _ in range(6):
        time.sleep(10)
        for c in ["AT+CEREG?", "AT+XCESQ?", "AT+COPS?"]:
            ask(fd, c)
    ask(fd, "AT+CEER")
finally:
    os.close(fd)
    subprocess.run(["systemctl", "start", "ModemManager.service"])
    print("== ModemManager started again")
