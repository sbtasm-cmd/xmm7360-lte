#!/usr/bin/env bash
# Run as root. Installs the built ModemManager package and XMM7360 system config.
set -euo pipefail
cd "$(dirname "$0")"

pkg=$(ls -t ../packaging/arch/modemmanager-xmm7360-git-[0-9]*.pkg.tar.zst | head -1)
# --ask 4 auto-accepts replacing the conflicting libmm-glib package.
pacman -U --noconfirm --ask 4 "$pkg"

# FCC unlock before ModemManager opens the RPC port (avoids MM issue 1028).
install -Dm755 /dev/stdin /usr/local/bin/wwan-fcc-unlock <<'S'
#!/usr/bin/env bash
for _ in {1..30}; do [[ -c /dev/wwan0xmmrpc0 ]] && break; sleep 1; done
[[ -c /dev/wwan0xmmrpc0 ]] || exit 0   # no modem present
exec timeout 30 bash /usr/share/ModemManager/fcc-unlock.available.d/8086:7360 dummy wwan0xmmrpc0
S
install -Dm644 /dev/stdin /etc/systemd/system/ModemManager.service.d/fcc-unlock.conf <<'S'
[Service]
ExecStartPre=-/usr/local/bin/wwan-fcc-unlock
S

# PCI runtime PM crashes the modem firmware (MM issue 992).
install -Dm644 /dev/stdin /etc/udev/rules.d/99-wwan-nopm.rules <<'S'
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x8086", ATTR{device}=="0x7360", ATTR{power/control}="on"
S

# The modem loses power in S3 sleep; revive it via ACPI _RST after resume.
install -Dm755 /dev/stdin /usr/local/bin/wwan-resume-reset <<'S'
#!/usr/bin/env bash
SLOT="$(lspci -Dn -d 8086:7360)"
SLOT="${SLOT%% *}"
D=/sys/bus/pci/devices/$SLOT
if [[ -z "$SLOT" || ! -e "$D/reset_method" ]]; then exit 0; fi
echo "$SLOT" > /sys/bus/pci/drivers/iosm/unbind
sleep 1
echo acpi > "$D/reset_method"
echo 1 > "$D/reset"
sleep 5
echo "$SLOT" > /sys/bus/pci/drivers/iosm/bind
systemctl restart ModemManager.service
S
install -Dm644 /dev/stdin /etc/systemd/system/wwan-resume-reset.service <<'S'
[Unit]
Description=Reset the WWAN modem after resume
After=suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/wwan-resume-reset
TimeoutStartSec=120

[Install]
WantedBy=suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
S

udevadm control --reload
systemctl daemon-reload
systemctl enable wwan-resume-reset.service
systemctl enable --now ModemManager.service
echo "Done. ModemManager status:"
systemctl --no-pager --lines=0 status ModemManager.service || true
