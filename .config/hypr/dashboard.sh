#!/usr/bin/env bash

# Wait a moment on boot for monitors & Waybar to settle
sleep 1

# 1. Automatically find your Vertical Monitor & Main Horizontal Monitor
VERT_MON=$(hyprctl monitors -j | python3 -c "import sys, json; mons=json.load(sys.stdin); print(next((m['name'] for m in mons if m.get('transform',0) in (1,3) or m['height']>m['width']), ''))")
MAIN_MON=$(hyprctl monitors -j | python3 -c "import sys, json; mons=json.load(sys.stdin); print(next((m['name'] for m in mons if not (m.get('transform',0) in (1,3) or m['height']>m['width'])), ''))")

# Close any old dashboard windows if re-running
pkill -f "kitty --class dash-" 2>/dev/null
sleep 0.2

# 2. Pin Workspace 2 to the Vertical Monitor and focus it
if [ -n "$VERT_MON" ]; then
    hyprctl keyword workspace "2, monitor:$VERT_MON, default:true" >/dev/null
    hyprctl dispatch focusmonitor "$VERT_MON" >/dev/null
fi
hyprctl dispatch workspace 2 >/dev/null

# 3. Launch TOP window: btop
kitty --class dash-btop --title dash-btop -e btop &
for _ in {1..40}; do
    hyprctl clients | grep -q "class: dash-btop" && break
    sleep 0.05
done
sleep 0.1

# 4. Preselect DOWN and launch BOTTOM-LEFT window: lava
hyprctl dispatch focuswindow "class:^dash-btop$" >/dev/null
hyprctl dispatch layoutmsg "preselect d" >/dev/null
kitty --class dash-lava --title dash-lava -e lavat -c magenta -k cyan -R 2 &
for _ in {1..40}; do
    hyprctl clients | grep -q "class: dash-lava" && break
    sleep 0.05
done
sleep 0.1

# 5. Preselect RIGHT and launch BOTTOM-RIGHT window: cava
hyprctl dispatch focuswindow "class:^dash-lava$" >/dev/null
hyprctl dispatch layoutmsg "preselect r" >/dev/null
kitty --class dash-cava --title dash-cava -e cava &
for _ in {1..40}; do
    hyprctl clients | grep -q "class: dash-cava" && break
    sleep 0.05
done

# 6. Return focus to your Main Horizontal Monitor (Workspace 1)
if [ -n "$MAIN_MON" ]; then
    hyprctl dispatch focusmonitor "$MAIN_MON" >/dev/null
fi
