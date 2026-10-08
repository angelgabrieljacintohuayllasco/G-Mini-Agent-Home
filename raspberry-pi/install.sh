#!/usr/bin/env bash
# Instala el cliente de G-Mini Home en Raspberry Pi OS (Bookworm) o Debian/Ubuntu.
#
#   sudo ./install.sh                                   # instala y arranca el servicio
#   sudo ./install.sh --url http://192.168.1.50:8765 --pair 482913
#   sudo ./install.sh --no-service                      # solo instala (para probar a mano)
#   sudo ./install.sh --desktop                         # la Pi arranca con escritorio (X11/Wayland)
#
# Archivos: /opt/gmini-home (codigo y venv), /etc/gmini-home/config.toml,
#           /var/lib/gmini-home (token), /etc/systemd/system/gmini-pi.service
set -euo pipefail

PREFIX=/opt/gmini-home
CONF_DIR=/etc/gmini-home
STATE_DIR=/var/lib/gmini-home
UNIT=/etc/systemd/system/gmini-pi.service
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL=""
PAIR=""
WITH_SERVICE=1
SDL_DRIVER="kmsdrm"
RUN_USER="${SUDO_USER:-}"

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) URL="$2"; shift 2 ;;
    --pair) PAIR="$2"; shift 2 ;;
    --user) RUN_USER="$2"; shift 2 ;;
    --no-service) WITH_SERVICE=0; shift ;;
    --desktop) SDL_DRIVER="x11"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opcion desconocida: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo $0 $*" >&2
  exit 1
fi
if [[ -z "$RUN_USER" || "$RUN_USER" == "root" ]]; then
  echo "Indica el usuario que usara la pantalla y el audio: sudo ./install.sh --user pi" >&2
  exit 1
fi
id "$RUN_USER" >/dev/null 2>&1 || { echo "No existe el usuario $RUN_USER" >&2; exit 1; }

# El codigo puede venir del repositorio (raspberry-pi/ y common/) o del zip de la release.
if [[ -d "$HERE/../common/gmini_link" ]]; then
  LINK_SRC="$HERE/../common/gmini_link"
  KIOSK_SRC="$HERE/../kiosk"
else
  LINK_SRC="$HERE/gmini_link"
  KIOSK_SRC="$HERE/kiosk"
fi
[[ -d "$LINK_SRC" && -d "$HERE/gmini_pi" ]] || { echo "No encuentro gmini_pi/ o gmini_link/" >&2; exit 1; }

echo "==> Paquetes del sistema"
apt-get update -qq
apt-get install -y --no-install-recommends python3 python3-venv python3-pip libportaudio2 \
  libsdl2-2.0-0 libsdl2-ttf-2.0-0 fonts-dejavu-core >/dev/null

PYV=$(python3 -c 'import sys; print("%d%02d" % sys.version_info[:2])')
if (( PYV < 311 )); then
  echo "Se necesita Python 3.11 o mas nuevo (Raspberry Pi OS Bookworm lo trae)." >&2
  exit 1
fi

echo "==> Codigo en $PREFIX"
install -d -m 755 "$PREFIX"
rm -rf "$PREFIX/gmini_pi" "$PREFIX/gmini_link" "$PREFIX/kiosk"
cp -r "$HERE/gmini_pi" "$PREFIX/gmini_pi"
cp -r "$LINK_SRC" "$PREFIX/gmini_link"
[[ -d "$KIOSK_SRC" ]] && cp -r "$KIOSK_SRC" "$PREFIX/kiosk"
cp "$HERE/requirements.txt" "$PREFIX/requirements.txt"
find "$PREFIX" -name '__pycache__' -prune -exec rm -rf {} +

echo "==> Entorno virtual de Python"
if [[ ! -x "$PREFIX/venv/bin/python" ]]; then
  python3 -m venv "$PREFIX/venv"
fi
"$PREFIX/venv/bin/pip" install --quiet --upgrade pip
"$PREFIX/venv/bin/pip" install --quiet -r "$PREFIX/requirements.txt"

echo "==> Configuracion"
install -d -m 755 "$CONF_DIR"
if [[ ! -f "$CONF_DIR/config.toml" ]]; then
  install -m 644 "$HERE/config.example.toml" "$CONF_DIR/config.toml"
  echo "    Creado $CONF_DIR/config.toml (revisa server.url)"
fi
if [[ -n "$URL" ]]; then
  sed -i "s|^url = .*|url = \"$URL\"|" "$CONF_DIR/config.toml"
fi
install -d -m 700 -o "$RUN_USER" -g "$RUN_USER" "$STATE_DIR"
for group in audio video input gpio render; do
  getent group "$group" >/dev/null && usermod -aG "$group" "$RUN_USER"
done

if [[ -n "$PAIR" ]]; then
  echo "==> Emparejando con G-Mini"
  sudo -u "$RUN_USER" env PYTHONPATH="$PREFIX" GMINI_HOME_CONFIG="$STATE_DIR" \
    GMINI_PI_CONFIG="$CONF_DIR/config.toml" "$PREFIX/venv/bin/python" -m gmini_pi --pair "$PAIR" --pair-only
fi

if (( WITH_SERVICE )); then
  echo "==> Servicio systemd"
  sed -e "s|@USER@|$RUN_USER|g" -e "s|@SDL_DRIVER@|$SDL_DRIVER|g" "$HERE/gmini-pi.service" > "$UNIT"
  chmod 644 "$UNIT"
  systemctl daemon-reload
  systemctl enable --now gmini-pi.service
  echo "    Estado: systemctl status gmini-pi    Registro: journalctl -u gmini-pi -f"
fi

echo
echo "Listo. Para emparejar mas tarde:"
echo "  sudo -u $RUN_USER env PYTHONPATH=$PREFIX GMINI_HOME_CONFIG=$STATE_DIR $PREFIX/venv/bin/python -m gmini_pi --pair CODIGO"
echo "  sudo systemctl restart gmini-pi"
