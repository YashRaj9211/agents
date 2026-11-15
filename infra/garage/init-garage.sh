#!/bin/sh
set -e

echo "Waiting for Garage daemon to become ready..."
until /garage -c /etc/garage.toml status > /dev/null 2>&1; do
  sleep 1
done

echo "Garage daemon is online. Querying Node ID..."
NODE_ID=$(/garage -c /etc/garage.toml status | awk '/^[0-9a-f]{16,64}/ {print $1}' | head -n 1)

if [ -n "$NODE_ID" ]; then
  echo "Assigning single-node layout for node $NODE_ID..."
  /garage -c /etc/garage.toml layout assign -z dc1 -c 10GB "$NODE_ID" || true
  /garage -c /etc/garage.toml layout apply --version 1 || true
fi

echo "Provisioning S3 bucket and credentials..."
/garage -c /etc/garage.toml bucket create agents-artifacts || true
/garage -c /etc/garage.toml key import --yes -n default-app-key GK0123456789abcdef01234567 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef || true
/garage -c /etc/garage.toml bucket allow agents-artifacts --read --write --owner --key default-app-key || true

echo "Garage S3 Object Storage successfully initialized!"
exit 0
