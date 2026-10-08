#!/usr/bin/env bash
# Desinstala el cliente de G-Mini Home.
#
#   sudo ./uninstall.sh            # quita el servicio y el codigo; conserva config y token
#   sudo ./uninstall.sh --purge    # ademas borra /etc/gmini-home y /var/lib/gmini-home
#
# Despues revoca el dispositivo en G-Mini (Ajustes > Dispositivos) si no lo vas a usar mas.
set -euo pipefail

PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1
if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo $0 $*" >&2
  exit 1
fi

if systemctl list-unit-files gmini-pi.service >/dev/null 2>&1; then
  systemctl disable --now gmini-pi.service 2>/dev/null || true
fi
rm -f /etc/systemd/system/gmini-pi.service
systemctl daemon-reload
rm -rf /opt/gmini-home
echo "Servicio y codigo eliminados."

if (( PURGE )); then
  rm -rf /etc/gmini-home /var/lib/gmini-home
  echo "Configuracion y token eliminados."
else
  echo "Se conservan /etc/gmini-home (configuracion) y /var/lib/gmini-home (token)."
fi
echo "Recuerda revocar el dispositivo en G-Mini: Ajustes > Dispositivos."
