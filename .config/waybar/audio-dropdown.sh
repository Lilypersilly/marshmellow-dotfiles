#!/usr/bin/env bash

# If dropdown is already open, close it
if pgrep -x "wofi" > /dev/null; then
    pkill -x wofi
    exit 0
fi

WOFI_CMD="wofi --dmenu --location=top_right --xoffset=-15 --yoffset=46 --width=360 --height=260 --hide-scroll --insensitive"

# Build the main dropdown menu
VOL=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{printf "%d%%", $2*100}')
CHOICE=$(printf "🎧  Switch Output (Speakers / Headphones)\n🎙️  Switch Input (Microphone)\n🔊  Volume Up (+10%%)\n🔉  Volume Down (-10%%)\n🔇  Toggle Mute (Current: %s)" "$VOL" | $WOFI_CMD --prompt "Audio Control")

case "$CHOICE" in
    *"Switch Output"*)
        # Parse Sinks from wpctl status
        SINK=$(wpctl status | awk '/Sinks:/,/Sources:/' | grep -E '[0-9]+\.' | sed 's/│//g; s/\*/✓/g; s/^[ \t]*//' | $WOFI_CMD --prompt "Select Output")
        ID=$(echo "$SINK" | grep -oE '[0-9]+' | head -n1)
        [ -n "$ID" ] && wpctl set-default "$ID"
        ;;
    *"Switch Input"*)
        # Parse Sources from wpctl status
        SRC=$(wpctl status | awk '/Sources:/,/Filters:/' | grep -E '[0-9]+\.' | sed 's/│//g; s/\*/✓/g; s/^[ \t]*//' | $WOFI_CMD --prompt "Select Microphone")
        ID=$(echo "$SRC" | grep -oE '[0-9]+' | head -n1)
        [ -n "$ID" ] && wpctl set-default "$ID"
        ;;
    *"Volume Up"*)
        wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 10%+
        ;;
    *"Volume Down"*)
        wpctl set-volume @DEFAULT_AUDIO_SINK@ 10%-
        ;;
    *"Toggle Mute"*)
        wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
        ;;
esac
