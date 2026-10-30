#!/bin/sh
# Adapt rollback.json from your BEFORE snapshot. Never place this script in auto-start.
set -u
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
BASE=/opt/etc/home-xray
[ "${1:-}" != --if-unconfirmed ] || [ ! -e "$BASE/confirmed" ] || exit 0
CONF="$BASE/rollback.json"
[ -f "$CONF" ] || { echo 'Missing reviewed rollback.json'; exit 1; }
IFACE=$(jq -er .old_interface "$CONF") || exit 1
PROFILE=$(jq -er .dns_profile "$CONF") || exit 1
echo "$IFACE" | grep -Eq '^OpenVPN[0-9]+$' || exit 1
echo "$PROFILE" | grep -Eq '^[A-Za-z0-9_-]+$' || exit 1
for key in old_dns new_dns; do
    jq -e ".$key | type == \"array\" and length > 0" "$CONF" >/dev/null || exit 1
    jq -er ".$key | arrays | .[]" "$CONF" | while IFS= read -r ip; do
        echo "$ip" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || exit 1
    done || exit 1
done
rm -f "$BASE/confirmed"
sed -i 's/^start_auto=.*/start_auto="off"/' /opt/etc/init.d/S05xkeen
/opt/etc/init.d/S05xkeen stop
# Official stop may skip cleanup if the core has already crashed.
for table in nat mangle filter; do
    iptables-save -t "$table" | awk -v t="$table" '/^-A/ && /xkeen_rule/ {sub(/^-A/,"iptables -t " t " -D");print}' | sh
    for chain in $(iptables-save -t "$table" | sed -n 's/^:\(xkeen[^ ]*\).*/\1/p'); do iptables -t "$table" -F "$chain"; done
    for chain in $(iptables-save -t "$table" | sed -n 's/^:\(xkeen[^ ]*\).*/\1/p'); do iptables -t "$table" -X "$chain"; done
done
rm -f /opt/etc/ndm/netfilter.d/proxy.sh /opt/etc/ndm/schedule.d/00-xkeen-hotspot-sync.sh
ip rule del fwmark 0x111 lookup 111 2>/dev/null
ip route flush table 111 2>/dev/null
jq -r '.new_dns[]' "$CONF" | while IFS= read -r ip; do /bin/ndmc -c "dns-proxy filter profile $PROFILE dns53 no upstream $ip"; done
jq -r '.old_dns[]' "$CONF" | while IFS= read -r ip; do /bin/ndmc -c "dns-proxy filter profile $PROFILE dns53 upstream $ip"; done
/bin/ndmc -c "interface $IFACE up"
/bin/ndmc -c 'system configuration save'
if [ -f /opt/var/spool/cron/crontabs/root ]; then
    sed -i '\|/opt/etc/home-xray/update-geodata.sh|d' /opt/var/spool/cron/crontabs/root
fi
logger -t home-xray 'XKeen stopped; previous OpenVPN and DNS requested. Verify connectivity.'
