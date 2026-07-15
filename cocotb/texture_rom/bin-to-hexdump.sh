#!/usr/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 {inputfile.bin}"
    exit 1
fi

hexdump -v -e '16/1 "%02X " "\n"' "$1"

