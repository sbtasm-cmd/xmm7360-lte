# Reverse-engineering notes

Source: Lenovo package `nz4wj14w` (Fibocom L850-GL WWAN driver for the
ThinkPad X1 Yoga Gen 5 / X1 Carbon Gen 8), file `UDEDriver/WinIhvRil.dll`
(x64, image base `0x180000000`). The driver binaries are not redistributed
here; download the package from Lenovo support to reproduce. Addresses below
are RVAs in that DLL.

## Method

1. Extract the Inno Setup installer with `innoextract`.
2. Collect RPC names from strings (`Uta*`, `Csi*`) and compare them with the
   calls used by ModemManager and xmm7360-pci. These calls appear only in
   Windows: `CsiHwRadio*`, `UtaMsCpsSetModeReq`,
   `UtaMsCpsSetStackModeConfiguration`, `UtaMsCpsSetSimModeConfiguration`,
   `UtaModeInitialSwitchComplete*`.
3. Find each `Rem<Call>` stub through the RIP-relative `lea` of its name
   string, and read the RPC ID from the `mov edx/ecx, imm` before the send.
   Validated on `RemCsiFccLockQueryReq`, which gives `0x18E`, the known ID.
4. Find the call site and its arguments through the log string
   `"%s: case FUN_MODE_STACK_ON"` (function `0x193e50`).

## IDs found

| Call | ID | Stub RVA |
|---|---|---|
| `UtaMsCpsSetModeReq` | `0x1F` | `0x2c38b0` |
| `UtaMsCpsSetStackModeConfiguration` | `0x20` | `0x2c3fe0` |
| `UtaMsCpsSetSimModeConfiguration` | `0x21` | `0x2c3b60` |
| `CsiHwRadioQueryReq` | `0x1D6` | `0x2b6330` |

`CsiHwRadioQueryReq` (async, empty body) returns `[0, hw_state]` in its
async ack (code `2000 + 0x1D6`). On the affected laptop it returned
`hw_state = 1`, so the hardware radio switch (W_DISABLE) was **not** the
cause.

## Radio-on sequence (`phone_functionality_operation_state`, `FUN_MODE_STACK_ON`)

```
UtaMsCpsSetStackModeConfiguration(sim, 1)
UtaMsCpsSetModeReq(sim, 1, 0, callback, ctx)    -> UtaMsCpsSetModeRsp, UtaMsCpsSetModeIndCb
```

`FUN_MODE_STACK_OFF` reverses it: `SetModeReq(sim, 0)`, then
`SetStackModeConfiguration(sim, 0)` and `SetSimModeConfiguration(sim, 0)`.
If `UtaMsCpsSetModeIndCb` doesn't arrive in time, the driver logs
*"Modem is in airplane mode. Send Radio OFF response to OS"*.

## Message encoding

Each stub serializes its arguments through a per-message table of field
encoders (`{encode, decode, flags}`, 0x18 bytes per entry), then writes the
4-byte transaction word (`0x2d9560`) and the header (`0x2d94a0`). The encoders
write **backwards** from the end of a 0x8000-byte buffer, so the order on the
wire is the reverse of the order in which arguments are encoded. Integer
fields (`0x2d7870`/`0x2d7900` → `0x2d7f00`) use the usual `02 04 <be32>`.

Cross-check with the known-good `UtaModeSetReq` (`0x12F`): Windows calls
`UtaModeSetReq(1, ctx, callback)`. In reverse, the wire body is
`int(0) int(0x0f) int(1)`, which is byte-for-byte what xmm7360-pci sends.

So the radio-on bodies are:

```
UtaMsCpsSetStackModeConfiguration  0x020: 02 04 00000001  02 04 00000000
UtaMsCpsSetModeReq                 0x01F: 02 04 00000010  02 04 00000000  02 04 00000000
                                          02 04 00000001  02 04 00000000
```

(`0x10` is a free-choice callback transaction ID, which the modem echoes in
`UtaMsCpsSetModeRsp`.)

## Result on the test machine

Before: `COPS: 2`, `CEREG: 0,0`, `XCESQ: 0,99,99,255,255,255,255,255`.

After the two calls and `AT+COPS=0`:

```
+CEREG: 2,1,"…","…",7          registered, home, E-UTRAN
+XCESQ: 0,99,99,255,255,23,27,18
+COPS: 0,0,"lifecell",7
UtaMsNetAttachReq -> 0x0, +CGATT: 1
```

## SMS over RPC (for reference)

- **Incoming:** `UtaMsSmsIncomingIndCb` (`0x032`) fields, wire order: `B, L, S(SMSC+TPDU, 176), B tpdu_len, L, H, L, B tipd, L`. Ack with `UtaMsSmsIncomingSmsAck` (`0x036`), body `B(0) S(176 zero bytes) B(0) L(0) B(tipd) L(0)`. The modem returned 0 to this ack.
- **Outgoing:** `UtaMsSmsSendReq` (`0x031`) takes `(sim, struct*, ctx)`. Struct (0xC0 bytes): `u32 x=7 (+0), u8 len (+4), u8 pdu[0xB0] (+5, SMSC+TPDU), u32 msg_service=0 (+0xB8), u32 0 (+0xBC)`. Every layout derived from this (`B(0) L(0) L(0) S(pdu) B(len) L(x) L(sim)`) crashed the firmware ("ch[1]: confused phase 3", then "PORT open refused"). The exact wire bytes are still unknown. Emulating `RemUtaMsSmsSendReq` (Unicorn) would settle them.
- SMS don't need RPC at all once the protocol stack is on, because `AT+CPMS`/CNMI work then.
