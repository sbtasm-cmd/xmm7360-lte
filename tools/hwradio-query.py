#!/usr/bin/env python3
# Run as root. READ-ONLY: asks the modem what it thinks the hardware radio switch
# (W_DISABLE) state is, via CsiHwRadioQueryReq (RPC id 0x1D6, found in Lenovo's
# WinIhvRil.dll). Stops ModemManager meanwhile and restarts it after.
import os, sys, signal, subprocess, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "xmm7360-rpc"))
import rpc, select
sys.stdout.reconfigure(line_buffering=True)

def done(*_):
    subprocess.run(["systemctl", "start", "ModemManager.service"])
    print("== ModemManager started again")
    os._exit(0)

subprocess.run(["systemctl", "stop", "ModemManager.service"], check=True)
time.sleep(2)
signal.signal(signal.SIGALRM, done)
signal.alarm(30)
r = rpc.XMMRPC()
print("== sanity check, FCC query (expect 0x0, 0x1, 0x1):")
r.execute('CsiFccLockQueryReq', is_async=True)
print("== CsiHwRadioQueryReq (0x1D6), async:")
# send without blocking forever: build the frame like rpc.execute does, then pump with a timeout
import struct
body = rpc.asn_int4(0)
tid = 0x11000101
total = len(body) + 16 + 6
hdr = struct.pack('<L', total) + rpc.asn_int4(total) + rpc.asn_int4(0x1D6) + struct.pack('>L', 0x11000100 | tid) + rpc.asn_int4(tid)
os.write(r.fp, hdr + body)
end = time.time() + 15
while time.time() < end:
    if select.select([r.fp], [], [], 1)[0]:
        m = r.pump()
        print("   type=%s code=0x%x content=%s" % (m['type'], m['code'], m['content']))
        if m['type'] == 'response' and m['code'] == 0x1D6:
            break
else:
    print("== no response to 0x1D6 within 15 s")
done()
