#!/bin/bash
# =============================================================
# ebs_provision.sh — Provision AWS EBS gp3 volumes for Cassandra
# Project: Distributed DB Performance Tuning
# Usage: bash aws/ebs_provision.sh
# Prerequisites: AWS CLI configured with appropriate IAM role
# =============================================================

set -euo pipefail

# ── CONFIG ────────────────────────────────────────────────────
REGION="us-east-1"
ZONE="${REGION}a"
VOLUME_SIZE_GB=500
VOLUME_TYPE="gp3"
IOPS=6000           # gp3: 3000-16000 (baseline 3000 free)
THROUGHPUT_MBPS=250 # gp3: 125-1000 MB/s (baseline 125 free)
NODES=3

# Replace with your actual EC2 instance IDs after launch
INSTANCE_IDS=(
  "i-XXXXXXXXXXXXXXXXX"   # node1
  "i-XXXXXXXXXXXXXXXXY"   # node2
  "i-XXXXXXXXXXXXXXXXX"   # node3

)

DEVICES=("/dev/xvdf" "/dev/xvdg" "/dev/xvdh")

echo "=================================================="
echo " Provisioning ${NODES} EBS gp3 volumes"
echo " Size: ${VOLUME_SIZE_GB}GB | IOPS: ${IOPS} | Throughput: ${THROUGHPUT_MBPS}MB/s"
echo "=================================================="

VOLUME_IDS=()

for i in $(seq 1 $NODES); do
  NODE_NAME="cassandra-node${i}"
  echo ""
  echo "▶  Creating volume for ${NODE_NAME}..."

  VOLUME_ID=$(aws ec2 create-volume \
    --region "$REGION" \
    --availability-zone "$ZONE" \
    --volume-type "$VOLUME_TYPE" \
    --size "$VOLUME_SIZE_GB" \
    --iops "$IOPS" \
    --throughput "$THROUGHPUT_MBPS" \
    --encrypted \
    --tag-specifications "ResourceType=volume,Tags=[{Key=Name,Value=${NODE_NAME}},{Key=Project,Value=cassandra-perf}]" \
    --query 'VolumeId' \
    --output text)

  echo "  ✓ Created: ${VOLUME_ID}"
  VOLUME_IDS+=("$VOLUME_ID")

  # Wait for volume to become available
  echo "  ⏳ Waiting for volume to be available..."
  aws ec2 wait volume-available --region "$REGION" --volume-ids "$VOLUME_ID"
  echo "  ✓ Volume available."

  # Attach to EC2 instance
  IDX=$((i-1))
  INSTANCE_ID="${INSTANCE_IDS[$IDX]}"
  DEVICE="${DEVICES[$IDX]}"

  if [[ "$INSTANCE_ID" != "i-XXX"* ]]; then
    echo "  📎 Attaching ${VOLUME_ID} → ${INSTANCE_ID} as ${DEVICE}..."
    aws ec2 attach-volume \
      --region "$REGION" \
      --volume-id "$VOLUME_ID" \
      --instance-id "$INSTANCE_ID" \
      --device "$DEVICE"
    echo "  ✓ Attached."
  else
    echo "  ⚠  Skipping attach (no real instance ID set for node${i})"
  fi
done

echo ""
echo "=================================================="
echo " Volume IDs created:"
for vid in "${VOLUME_IDS[@]}"; do echo "  - $vid"; done
echo ""
echo " NEXT STEPS — run on each EC2 instance:"
echo ""
echo "  # Format the volume (EXT4, no discard for Cassandra)"
echo "  sudo mkfs.ext4 -E nodiscard /dev/xvdf"
echo ""
echo "  # Create mount point and mount with performance flags"
echo "  sudo mkdir -p /var/lib/cassandra"
echo "  sudo mount -o noatime,nodiscard /dev/xvdf /var/lib/cassandra"
echo ""
echo "  # Persist across reboots"
echo "  echo '/dev/xvdf /var/lib/cassandra ext4 noatime,nodiscard 0 2' | sudo tee -a /etc/fstab"
echo ""
echo "  # Set ownership for Cassandra process"
echo "  sudo chown -R cassandra:cassandra /var/lib/cassandra"
echo "=================================================="
