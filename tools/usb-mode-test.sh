#!/usr/bin/env bash
# Run as root. Non-persistent test: disable the modem's PCIe link and reset it via ACPI
# so it falls back to USB (method from xmm7360/xmm7360_usb xmm2usb). A full power-off
# restores normal PCIe mode.
set -uo pipefail
MODEM=0000:02:00.0
BRIDGE=0000:00:1c.0
ACPI_PATH=$(cat /sys/bus/pci/devices/$MODEM/firmware_node/path)

systemctl stop ModemManager.service
echo "$MODEM" > /sys/bus/pci/drivers/iosm/unbind 2>/dev/null && echo "iosm unbound"
modprobe acpi_call || { echo "acpi_call module missing"; exit 1; }
echo "Disabling PCIe link on $BRIDGE..."
setpci -s "$BRIDGE" CAP_EXP+10.w=0052
echo "Resetting modem via ${ACPI_PATH}._RST..."
printf "%s" "${ACPI_PATH}._RST" > /proc/acpi/call
echo "ACPI result: $(tr -d '\0' < /proc/acpi/call)"
for i in $(seq 1 20); do
  lsusb | grep -iE "2cb7|8087:0911|fibocom|xmm|L850" && break
  sleep 1
done
echo "== lsusb:"; lsusb
echo "== kernel:"; journalctl -k --since "-1min" --no-pager | grep -iE "usb|cdc|mbim|acm|ncm" | tail -15
systemctl start ModemManager.service
