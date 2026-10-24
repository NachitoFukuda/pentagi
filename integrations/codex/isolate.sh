#!/bin/sh
# Runs INSIDE the dedicated PentAGI VM; never run against a shared Docker host.
set -eu
# Non-root PentAGI may contact only VM loopback (database and CLI SSH tunnel).
sudo iptables -N PENTAGI_EGRESS 2>/dev/null || true
sudo iptables -F PENTAGI_EGRESS
sudo iptables -A PENTAGI_EGRESS -d 127.0.0.0/8 -j ACCEPT
sudo iptables -A PENTAGI_EGRESS -j REJECT
sudo iptables -C OUTPUT -m owner --uid-owner 10001 -j PENTAGI_EGRESS 2>/dev/null || sudo iptables -I OUTPUT 1 -m owner --uid-owner 10001 -j PENTAGI_EGRESS
# Workers have neither Internet routing nor access to services on the VM host.
sudo iptables -C INPUT -i br-pentagiwork -j REJECT 2>/dev/null || sudo iptables -I INPUT 1 -i br-pentagiwork -j REJECT
