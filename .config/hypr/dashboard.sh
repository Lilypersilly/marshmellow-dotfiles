#!/usr/bin/env bash

# 1. Wait a couple seconds for monitors to fully wake up
sleep 2

VERT_MON=$(hyprctl monitors -j | python3 -c "import sys, json; mons=json.load(sys.stdin); print(next((m['name'] for m in mons if m.get('transform',0) in (1,2,3) or m['height']>m['width']), ''))")
MAIN_MON=$(hyprctl monitors -j | python3 -c "import sys, json; mons=json.load(sys.stdin); print(next((m['name'] for m in mons if not (m.get('transform',0) in (1,2,3) or m['height']>m['width'])), ''))")

# 2. Pin Workspace 2 to Vertical Monitor
if [ -n "$VERT_MON" ]; then
    hyprctl keyword workspace "2, monitor:$VERT_MON, default:true" >/dev/null
fi

# Clean up old dashboard windows
pkill -f "kitty --class dash-" 2>/dev/null
sleep 0.5

# 3. Force focus to Workspace 2 before spawning
hyprctl dispatch workspace 2 >/dev/null
sleep 0.5

# 4. Launch TOP (btop) forced to workspace 2
hyprctl dispatch exec "[workspace 2] kitty --class dash-btop --title dash-btop -e btop" >/dev/null
sleep 0.6

# 5. Launch BOTTOM-LEFT (lava)
hyprctl dispatch focuswindow "class:^dash-btop$" >/dev/null
hyprctl dispatch layoutmsg "preselect d" >/dev/null
hyprctl dispatch exec "[workspace 2] kitty --class dash-lava --title dash-lava -e lavat -c magenta -k cyan -R 2" >/dev/null
sleep 0.6

# 6. Launch BOTTOM-RIGHT (cava)
hyprctl dispatch focuswindow "class:^dash-lava$" >/dev/null
hyprctl dispatch layoutmsg "preselect r" >/dev/null
hyprctl dispatch exec "[workspace 2] kitty --class dash-cava --title dash-cava -e cava" >/dev/null
sleep 0.6

# 7. Return focus to Main Monitor (Workspace 1)
if [ -n "$MAIN_MON" ]; then
    hyprctl dispatch focusmonitor "$MAIN_MON" >/dev/null
    hyprctl dispatch workspace 1 >/dev/null
fi
