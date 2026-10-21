#!/usr/bin/env python3
import json, subprocess, time

def hypr_json(cmd):
    return json.loads(subprocess.check_output(["hyprctl", cmd, "-j"], text=True))

def dispatch(*args):
    subprocess.run(["hyprctl", "dispatch", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 1. Close any previous dashboard windows
subprocess.run(["pkill", "-f", "kitty --class marshmellow-(btop|lava|cava)"], stderr=subprocess.DEVNULL)
time.sleep(0.3)

vert_mon = "DP-3"
main_mon = "DVI-D-1"

# 2. Force Workspace 2 onto DP-3 (vertical monitor) and display it there
dispatch("moveworkspacetomonitor", "2", vert_mon)
dispatch("focusmonitor", vert_mon)
dispatch("workspace", "2")
time.sleep(0.2)

def spawn_on_dp3_ws2(cmd_list):
    before = {c["address"] for c in hypr_json("clients")}
    dispatch("focusmonitor", vert_mon)
    subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    new_addr = None
    for _ in range(50):
        time.sleep(0.1)
        for c in hypr_json("clients"):
            if c["address"] not in before:
                new_addr = c["address"]
                break
        if new_addr:
            break

    if not new_addr:
        return None

    # Move the window to Workspace 2 (which is locked to DP-3) and focus it
    dispatch("movetoworkspace", f"2,address:{new_addr}")
    time.sleep(0.15)
    dispatch("focuswindow", f"address:{new_addr}")
    time.sleep(0.15)
    return new_addr

# Step 1: Spawn btop on Workspace 2 (DP-3)
btop_addr = spawn_on_dp3_ws2(["kitty", "--class", "marshmellow-btop", "--title", "btop", "-e", "btop"])

# Step 2: Spawn lavat on Workspace 2 (DP-3)
lava_addr = spawn_on_dp3_ws2(["kitty", "--class", "marshmellow-lava", "--title", "lavat", "-e", "lavat", "-c", "magenta", "-k", "cyan"])

# Ensure btop is on TOP and lavat is on BOTTOM
clients = {c["address"]: c for c in hypr_json("clients")}
if btop_addr in clients and lava_addr in clients:
    b, l = clients[btop_addr], clients[lava_addr]
    if abs(b["at"][1] - l["at"][1]) < 50:
        dispatch("focuswindow", f"address:{lava_addr}")
        dispatch("togglesplit")
        time.sleep(0.15)
    clients = {c["address"]: c for c in hypr_json("clients")}
    b, l = clients[btop_addr], clients[lava_addr]
    if b["at"][1] > l["at"][1]:
        dispatch("focuswindow", f"address:{btop_addr}")
        dispatch("swapwindow", "u")
        time.sleep(0.15)

# Step 3: Focus lavat (bottom half) and spawn cava next to it on Workspace 2 (DP-3)
dispatch("focuswindow", f"address:{lava_addr}")
time.sleep(0.1)
cava_addr = spawn_on_dp3_ws2(["kitty", "--class", "marshmellow-cava", "--title", "cava", "-e", "cava"])

# Ensure lavat and cava are side-by-side on the bottom half
clients = {c["address"]: c for c in hypr_json("clients")}
if lava_addr in clients and cava_addr in clients:
    l, c = clients[lava_addr], clients[cava_addr]
    if abs(l["at"][0] - c["at"][0]) < 50:
        dispatch("focuswindow", f"address:{cava_addr}")
        dispatch("togglesplit")
        time.sleep(0.1)

# Return focus back to your main horizontal monitor (DVI-D-1)
dispatch("focusmonitor", main_mon)
print("✅ Opened btop, lavat, and cava on Workspace 2 (DP-3)!")
