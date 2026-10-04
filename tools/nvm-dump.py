#!/usr/bin/env python3
# Run as root. READ-ONLY: queries modem settings (no '=' set commands, no store_nvm).
# Output is also saved to nvm-dump.txt next to this script.
import os, select, time, subprocess
QUERIES = ["ATI", "AT+CGMR", "AT+GTUSBMODE?", "AT+XACT?", "AT+XBANDSEL?", "AT+GTSET?",
           "AT+COPS?", "AT+COPS=3,2", "AT+CFUN?", "AT+CGDCONT?", "AT+XCESQ?", "AT+CSQ",
           "AT@nvm:fix_cat_fcclock.fcclock_mode?", "AT@nvm:fix_cat_fcclock.fcclock_state?",
           "AT@nvm:fix_cat_fcclock?", "AT+XSIMSTATE?", "AT+XLEMA?", "AT+GTCAINFO?",
           "AT+XNWSELECT?", "AT+XSYSINFO?", "AT+CREG?", "AT+CEREG?", "AT+CGATT?",
           "AT+XCMODE?", "AT+XRFS?", "AT+GTDUALSIM?", "AT+GTFCCLOCK?", "AT+GTSAR?",
           "AT+XSAR?", "AT+GTANT?", "AT+GTCELLINFO?"]
out = []
subprocess.run(["systemctl", "stop", "ModemManager.service"], check=True)
time.sleep(2)
fd = os.open("/dev/wwan0at1", os.O_RDWR | os.O_NOCTTY)
try:
    for cmd in ["ATE0"] + QUERIES:
        while select.select([fd], [], [], 0.2)[0]:
            os.read(fd, 65536)
        os.write(fd, (cmd + "\r\n").encode())
        buf, end = b"", time.time() + 5
        while time.time() < end and b"OK\r\n" not in buf and b"ERROR" not in buf:
            if select.select([fd], [], [], 0.5)[0]:
                buf += os.read(fd, 65536)
        line = f"{cmd:42} -> {buf.decode(errors='replace').strip().replace(chr(13)+chr(10), ' | ') or '(no answer)'}"
        print(line, flush=True); out.append(line)
finally:
    os.close(fd)
    subprocess.run(["systemctl", "start", "ModemManager.service"])
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nvm-dump.txt"), "w").write("\n".join(out) + "\n")
    print("== saved nvm-dump.txt; ModemManager started again")
