#!/bin/sh
# Run on the router after XKeen and the three referenced geodata files exist.
set -u
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
D=/opt/etc/xray/dat
LOCK=/opt/var/run/home-xray-geodata.lock
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK"' EXIT
BACKUP=$(mktemp -d /opt/tmp/home-xray-geodata.XXXXXX) || exit 1
chmod 700 "$BACKUP"
for f in geosite_refilter.dat geosite_zkeen.dat geoip_zkeenip.dat; do
    cp -p "$D/$f" "$BACKUP/$f" || exit 1
done
# Official XKeen validates asset size and release SHA-256, then restarts the core.
/opt/sbin/xkeen -ug
sleep 8
if ! pidof xray >/dev/null; then
    for f in geosite_refilter.dat geosite_zkeen.dat geoip_zkeenip.dat; do
        cp -p "$BACKUP/$f" "$D/$f"
    done
    /opt/etc/init.d/S05xkeen start on
    logger -t home-xray 'Geodata update failed; previous files restored'
    exit 1
fi
# Keep the last checked files on USB for operator rollback.
for f in geosite_refilter.dat geosite_zkeen.dat geoip_zkeenip.dat; do
    mv "$BACKUP/$f" "$D/$f.previous"
done
rmdir "$BACKUP"
logger -t home-xray 'Geodata check completed; custom configuration unchanged'
