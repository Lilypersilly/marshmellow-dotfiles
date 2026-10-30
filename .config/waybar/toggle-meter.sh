#!/bin/bash
if pgrep -f "divergence-meter" > /dev/null; then
    pkill -f "divergence-meter"
else
    hyprctl dispatch exec "$HOME/.local/bin/divergence-meter"
fi
