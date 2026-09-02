#!/bin/bash
# Boot the Linux release on a distribution other than the one that built it.
#
# Run inside a bare container of the distribution under test, with the
# repository (or just `dist/`) mounted at /work:
#
#     docker run --rm -v "$PWD:/work" fedora:latest bash /work/tools/linux_smoke.sh
#
# Both downloads are booted exactly as a player would: the tarball unpacked
# and its executable run, the AppImage run in place (extracted first,
# because a container has no FUSE). Each boots for five frames with SDL's
# dummy video and audio drivers, and the session log then has to say that
# BASS and Prism loaded from beside the executable -- speech is NOT
# disabled here, so libprism.so and its bundled glib are really opened,
# which is where a distribution's loader would object if it were going to.
#
# On Fedora the tarball is booted a second time under Xvfb with SDL's real
# X11 driver, to prove the statically linked SDL2 finds the system's X
# libraries at run time. The other distributions run the dummy driver only;
# that is the loader and glibc check, which is what differs between them.
#
# What each container is given is what every desktop install already has:
# libdbus-1 (the executable links it for the Secret Service keyring) and
# libstdc++ (Prism). Nothing else is installed -- a distribution that needs
# more is a finding, not something to paper over here.
set -euo pipefail

. /etc/os-release
echo "== $PRETTY_NAME"
case "${ID:-}" in
  ubuntu|debian)
    apt-get update -qq >/dev/null
    apt-get install -y -qq --no-install-recommends libdbus-1-3 libstdc++6 >/dev/null
    ;;
  fedora)
    dnf install -y -q dbus-libs libstdc++ xorg-x11-server-Xvfb \
      libX11 libXext libXrandr libXcursor libXi libXfixes libXScrnSaver libxkbcommon \
      mesa-libGL mesa-libEGL >/dev/null
    ;;
  arch)
    pacman -Sy --noconfirm --quiet dbus gcc-libs >/dev/null
    ;;
  opensuse-tumbleweed|opensuse-leap)
    zypper --quiet --non-interactive install libdbus-1-3 libstdc++6 >/dev/null
    ;;
  *)
    echo "No package step for ${ID:-unknown}; booting with what the image has."
    ;;
esac
echo "glibc: $(ldd --version | head -1)"

export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export FREIGHT_FATE_DATA_DIR=/tmp/ff-data

check_log() {
  # $1: what booted, $2: its log.
  if [ ! -s "$2" ]; then
    echo "$1: the game wrote no session log." >&2
    exit 1
  fi
  for line in "bass: loaded from" "prism: loaded from" "Audio backend: bass"; do
    if ! grep -q "$line" "$2"; then
      echo "$1: the session log never says '$line':" >&2
      cat "$2" >&2
      exit 1
    fi
  done
  echo "$1: booted; BASS and Prism loaded from beside the executable."
}

# Shell globs, not find: a bare openSUSE image has no findutils.
tarballs=(/work/dist/FreightFate-*-linux-x64.tar.gz)
tarball="${tarballs[0]}"
if [ ! -f "$tarball" ]; then
  echo "No Linux tarball under /work/dist." >&2
  exit 1
fi
rm -rf /tmp/ff-tarball && mkdir -p /tmp/ff-tarball
tar -xzf "$tarball" -C /tmp/ff-tarball
FREIGHT_FATE_LOG_FILE=/tmp/ff-tarball.log timeout 120 /tmp/ff-tarball/FreightFate/FreightFate --smoke
check_log "tarball" /tmp/ff-tarball.log

appimages=(/work/dist/FreightFate-*-linux-x86_64.AppImage)
appimage="${appimages[0]}"
if [ ! -f "$appimage" ]; then
  echo "No Linux AppImage under /work/dist." >&2
  exit 1
fi
cp "$appimage" /tmp/FreightFate.AppImage
chmod +x /tmp/FreightFate.AppImage
FREIGHT_FATE_LOG_FILE=/tmp/ff-appimage.log timeout 120 /tmp/FreightFate.AppImage --appimage-extract-and-run --smoke
check_log "AppImage" /tmp/ff-appimage.log

if [ "${ID:-}" = "fedora" ]; then
  unset SDL_VIDEODRIVER
  FREIGHT_FATE_LOG_FILE=/tmp/ff-x11.log timeout 120 xvfb-run -a /tmp/ff-tarball/FreightFate/FreightFate --smoke
  check_log "tarball under Xvfb (X11 driver)" /tmp/ff-x11.log
fi
echo "Linux smoke passed on $PRETTY_NAME."
