#!/bin/bash
if pgrep -f "divergence-popup" > /dev/null; then
    pkill -f "divergence-popup"
else
    ~/.local/bin/divergence-popup &
fi
