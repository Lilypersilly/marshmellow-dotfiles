#!/usr/bin/env bash
# Auto-mount all real data drives (> 3GB) and skip tiny EFI/recovery partitions
lsblk -b -Pnpo NAME,TYPE,FSTYPE,MOUNTPOINT,SIZE | while read -r line; do
    eval "$line"
    if [ -n "$FSTYPE" ] && [ "$FSTYPE" != "swap" ] && [ -z "$MOUNTPOINT" ] && [ "$SIZE" -gt 3000000000 ]; then
        udisksctl mount -b "$NAME" --no-user-interaction >/dev/null 2>&1
    fi
done
