#!/usr/bin/env python3
# Run as root. Replays the Windows driver's radio-on sequence (from Lenovo WinIhvRil.dll,
# FUN_MODE_STACK_ON): UtaMsCpsSetStackModeConfiguration(sim0, 1) + UtaMsCpsSetModeReq(sim0, ON).
# Runtime RPCs only (no NVM writes). Stops ModemManager meanwhile, restarts it at the end.
import os, sys, time, select, struct, subprocess
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "xmm7360-rpc"))
import rpc, rpc_unsol_table
I = rpc.asn_int4

def send(r, cmd, body, wait=8, label=""):
    """Sync RPC: write frame, pump with timeout, print everything until the response."""
    total = len(body) + 16
    hdr = struct.pack('<L', total) + I(total) + I(cmd) + struct.pack('>L', 0x11000100)
    print(f"--> {label or hex(cmd)} body={body.hex()}")
    os.write(r.fp, hdr + body)
    end = time.time() + wait
    while time.time() < end:
        if select.select([r.fp], [], [], 0.5)[0]:
            m = r.pump()
            if m['type'] == 'response':
                return m
    print("    (no response)")

def listen(r, secs):
    end = time.time() + secs
    while time.time() < end:
        if select.select([r.fp], [], [], 0.5)[0]:
            r.pump()

def at(cmds):
    fd = os.open("/dev/wwan0at1", os.O_RDWR | os.O_NOCTTY)
    for c in cmds:
        while select.select([fd], [], [], 0.2)[0]:
            os.read(fd, 65536)
        os.write(fd, (c + "\r\n").encode())
        buf, end = b"", time.time() + (90 if c.startswith("AT+COPS=") else 5)
        while time.time() < end and b"OK\r\n" not in buf and b"ERROR" not in buf:
            if select.select([fd], [], [], 0.5)[0]:
                buf += os.read(fd, 65536)
        print(f"AT {c:12} -> {buf.decode(errors='replace').strip().replace(chr(13)+chr(10), ' | ')}")
    os.close(fd)

subprocess.run(["systemctl", "stop", "ModemManager.service"], check=True)
time.sleep(2)
try:
    r = rpc.XMMRPC()
    for c in ['UtaMsSmsInit', 'UtaMsCbsInit', 'UtaMsNetOpen', 'UtaMsCallCsInit',
              'UtaMsCallPsInitialize', 'UtaMsSsInit', 'UtaMsSimOpenReq']:
        send(r, rpc.rpc_call_ids.call_ids[c], I(0), label=c)
    send(r, 0x12F, I(0) + I(15) + I(1), label="UtaModeSetReq(1)")
    listen(r, 5)
    print("== Windows FUN_MODE_STACK_ON:")
    send(r, 0x20, I(1) + I(0), label="UtaMsCpsSetStackModeConfiguration(sim0, 1)")
    send(r, 0x1F, I(0x10) + I(0) + I(0) + I(1) + I(0), label="UtaMsCpsSetModeReq(sim0, ON)")
    print("== listening 40 s for indications (SetModeIndCb, attach-allowed, signal, registration)...")
    listen(r, 40)
    at(["ATE0", "AT+CMEE=2", "AT+CEREG=2", "AT+COPS?"])
    print("== automatic network selection (what Windows does after SetModeIndCb):")
    at(["AT+COPS=0"])
    for _ in range(6):
        listen(r, 10)
        at(["AT+CEREG?", "AT+XCESQ?", "AT+COPS?"])
    print("== RPC network attach with APN 'internet':")
    r.execute('UtaMsCallPsAttachApnConfigReq', rpc.pack_UtaMsCallPsAttachApnConfigReq('internet'), is_async=True)
    a = r.execute('UtaMsNetAttachReq', rpc.pack_UtaMsNetAttachReq(), is_async=True)
    print("== attach status: 0x%x" % rpc.unpack('nn', a['body'])[1])
    listen(r, 10)
    at(["AT+CEREG?", "AT+XCESQ?", "AT+COPS?", "AT+CGATT?"])
finally:
    subprocess.run(["systemctl", "start", "ModemManager.service"])
    print("== ModemManager started again")
