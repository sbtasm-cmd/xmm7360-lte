# xmm7360-lte

LTE on Linux for the Intel XMM7360 (Fibocom L850-GL) modem on laptops where it
registers fine under Windows but never finds a network under Linux.

Tested on a ThinkPad X1 Yoga Gen 5 (20UB), Arch Linux (Omarchy), kernel 7.2,
`iosm` driver, ModemManager git `338ecc06`, with lifecell (UA) on LTE. Works
from a cold boot (full power-off) and after suspend (S3; it reconnects about a
minute after wake-up) with no manual steps.

## Symptom

With the mainline `iosm` driver and ModemManager ≥ 1.25.95, everything looks
healthy except the radio:

- FCC unlock succeeds and the SIM is `READY`.
- `AT+CFUN?` reports `1` and `UtaModeSet(1)` is acknowledged.
- `AT+COPS?` stays at `2`, `AT+CEREG?` at `0`/`2,0`, `AT+CSQ` at `99,99`, and `AT+XCESQ?` at `99/255`.
- `AT+COPS=0` fails with `+CME ERROR: 30` (No network service).
- No `UtaMsNetIsAttachAllowedIndCb` arrives, and `UtaMsNetAttachReq` returns `0xffffffff`.

The same happens with the `xmm7360-pci` Python bring-up, so it isn't a
ModemManager-only bug. See also
[ModemManager#997](https://gitlab.freedesktop.org/mobile-broadband/ModemManager/-/issues/997).

## Root cause

The modem's cellular protocol stack is left in an internal airplane mode.
After the UTA mode is set, the Windows driver (Lenovo/Intel `WinIhvRil.dll`,
`FUN_MODE_STACK_ON`) sends two more RPCs that no Linux stack sent:

| RPC | ID | Body (after the header) |
|---|---|---|
| `UtaMsCpsSetStackModeConfiguration` | `0x20` | `int(1) int(sim=0)` |
| `UtaMsCpsSetModeReq` | `0x1F` | `int(tid) int(0) int(0) int(mode=1) int(sim=0)` |

After them, the modem sends `UtaMsCpsSetModeRsp` and `UtaMsCpsSetModeIndCb`,
starts reporting band, cell and signal information, accepts `AT+COPS=0`,
registers on LTE, and attaches. Details are in
[docs/reverse-engineering.md](docs/reverse-engineering.md).

## Contents

| Path | What |
|---|---|
| `patches/0001-intel-xmm7360-power-on-the-protocol-stack.patch` | ModemManager patch: sends both RPCs in the init sequence and after power-up |
| `packaging/arch/PKGBUILD` | Arch package `modemmanager-xmm7360-git` (ModemManager git + patch) |
| `system/install-system.sh` | Installs the package plus the FCC-unlock drop-in, the runtime-PM udev rule, and the resume reset service |
| `tools/` | Diagnostic scripts (raw RPC and AT); run `tools/fetch-xmm7360-rpc.sh` first |

## Install (Arch)

```sh
cd packaging/arch
makepkg -s                       # builds modemmanager-xmm7360-git
cd ../..
sudo bash system/install-system.sh
```

Then create a connection (replace the APN):

```sh
sudo nmcli connection add type gsm ifname '*' con-name lte gsm.apn internet \
     connection.autoconnect yes connection.metered yes \
     ipv4.route-metric 1000 ipv6.route-metric 1000
```

`install-system.sh` also sets up:

- **FCC unlock:** `ExecStartPre` runs `fcc-unlock.available.d/8086:7360` before ModemManager opens the RPC port.
- **Runtime power management:** turned off for the modem, because it crashes the firmware.
- **`wwan-resume-reset.service`:** resets the modem through ACPI `_RST` after resume, because the modem loses power in S3.

## Omarchy bar widget

The [Omarchy](https://omarchy.org/) bar widget for LTE status and a mobile data
switch now lives in its own repository:
[omarchy-lte](https://github.com/sbtasm-cmd/omarchy-lte).

```sh
omarchy plugin add https://github.com/sbtasm-cmd/omarchy-lte.git --enable
```

## SMS

SMS work with stock ModemManager once patch 0001 is applied. Without it the SIM
isn't fully initialized (the protocol stack is off), `AT+CPMS` fails, and
ModemManager disables messaging. With the stack on, ModemManager uses SIM
storage (`sm`) over AT, reads stored messages, assembles multipart SMS, and
receives new ones.

`patches/withdrawn/0002-…` was an RPC-based receive path
(`UtaMsSmsIncomingIndCb` + `UtaMsSmsIncomingSmsAck`). It is withdrawn: it isn't
needed, and keeping the RPC port open for indications broke data connections
(bearer RPC commands timed out). It stays in the repo as protocol
documentation. Sending SMS over RPC (`UtaMsSmsSendReq`) crashed the firmware in
every attempted layout and isn't implemented; see the notes in
docs/reverse-engineering.md.

## Notes

- ModemManager reports 0% signal on LTE because it reads `AT+CSQ`, which this modem answers with `99`. The real values are in `AT+XCESQ?`.
- The tools stop ModemManager while they run and restart it afterwards. Run them as root.

## Credits

- [xmm7360-pci](https://github.com/xmm7360/xmm7360-pci) for the RPC protocol work and the Python helpers.
- ModemManager's XMM7360 RPC plugin and the ArchWiki *Intel XMM 7360* page.

## License

GPL-2.0-or-later (see `LICENSE`), the same license as ModemManager.
