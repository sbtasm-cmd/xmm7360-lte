#!/usr/bin/env python3
# Run as root. Replicates the xmm7360-pci bring-up in one RPC session with ModemManager
# stopped, logs every modem indication, then queries AT status. Restarts ModemManager at the end.
import os, sys, signal, time, select, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "xmm7360-rpc"))
import rpc, rpc_unsol_table

def at_queries():
    print("\n== AT status on wwan0at1")
    fd = os.open("/dev/wwan0at1", os.O_RDWR | os.O_NOCTTY)
    for cmd in ["ATE0", "AT+CFUN?", "AT+CPIN?", "AT+COPS?", "AT+CEREG?", "AT+CSQ", "AT+XCESQ?", "AT+XACT?", "AT+CEER"]:
        while select.select([fd], [], [], 0.2)[0]:
            os.read(fd, 65536)
        os.write(fd, (cmd + "\r\n").encode())
        buf, end = b"", time.time() + 4
        while time.time() < end and b"OK\r\n" not in buf and b"ERROR" not in buf:
            if select.select([fd], [], [], 0.5)[0]:
                buf += os.read(fd, 65536)
        print(f"{cmd:12} -> {buf.decode(errors='replace').strip().replace(chr(13)+chr(10), ' | ') or '(no answer)'}", flush=True)
    os.close(fd)

def finish(*_):
    try:
        at_queries()
    finally:
        subprocess.run(["systemctl", "start", "ModemManager.service"])
        print("== ModemManager started again")
        os._exit(0)

subprocess.run(["systemctl", "stop", "ModemManager.service"], check=True)
time.sleep(2)
signal.signal(signal.SIGALRM, finish)
signal.alarm(150)

r = rpc.XMMRPC()
for c in ['UtaMsSmsInit', 'UtaMsCbsInit', 'UtaMsNetOpen', 'UtaMsCallCsInit',
          'UtaMsCallPsInitialize', 'UtaMsSsInit', 'UtaMsSimOpenReq']:
    r.execute(c)
rpc.do_fcc_unlock(r)
rpc.UtaModeSet(r, 1)
print("== mode set OK; waiting up to 60 s for attach-allowed indication")
end = time.time() + 60
while time.time() < end and not r.attach_allowed:
    if select.select([r.fp], [], [], 1)[0]:
        r.pump()
print("== attach_allowed =", r.attach_allowed)
r.execute('UtaMsCallPsAttachApnConfigReq', rpc.pack_UtaMsCallPsAttachApnConfigReq('internet'), is_async=True)
attach = r.execute('UtaMsNetAttachReq', rpc.pack_UtaMsNetAttachReq(), is_async=True)
print("== attach status: 0x%x" % rpc.unpack('nn', attach['body'])[1])
end = time.time() + 20
while time.time() < end:
    if select.select([r.fp], [], [], 1)[0]:
        r.pump()
finish()
