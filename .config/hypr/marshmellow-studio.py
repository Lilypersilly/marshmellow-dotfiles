#!/usr/bin/env python3
import gi
import os
import re
import shutil
import subprocess
import sys

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib

HYPR_CONF = os.path.expanduser("~/.config/hypr/hyprland.lua")
HYPR_BAK  = os.path.expanduser("~/.config/hypr/hyprland.lua.bak")
WAYBAR_CSS = os.path.expanduser("~/.config/waybar/style.css")

CSS = """
window, window.background {
    background-color: rgba(254, 228, 255, 0.96);
    border: none;
    border-radius: 0px;
    font-family: "Josefin Sans", "JetBrainsMono Nerd Font", sans-serif;
    color: #333933;
}
.main-box { padding: 24px 30px; }
.title-lbl { font-size: 22px; font-weight: bold; color: #bf40a1; }
.sub-lbl { font-size: 13px; font-weight: bold; color: #856d8a; margin-bottom: 10px; }
.card {
    background-color: rgba(255, 194, 255, 0.50);
    border: 1.5px solid #e975ca;
    border-radius: 14px;
    padding: 14px 18px;
}
.row-lbl { font-size: 14px; font-weight: bold; color: #333933; min-width: 170px; }
.val-badge {
    background-color: #322a32;
    color: #fee4ff;
    border-radius: 999px;
    padding: 5px 10px 1px 10px;
    font-size: 12px;
    font-weight: bold;
    min-width: 48px;
}
scale trough {
    background-color: #322a32;
    border-radius: 999px;
    min-height: 8px;
    min-width: 200px;
}
scale highlight {
    background-color: #e975ca;
    border-radius: 999px;
}
scale slider {
    background-color: #ffc2ff;
    border: 2px solid #bf40a1;
    border-radius: 999px;
    min-width: 18px;
    min-height: 18px;
    margin: -5px;
}
button.action-pill {
    background-image: none;
    background-color: #322a32;
    color: #fee4ff;
    border: 2px solid #e975ca;
    border-radius: 999px;
    padding: 8px 16px 4px 16px;
    font-size: 13px;
    font-weight: bold;
    transition: all 150ms ease;
}
button.action-pill:hover {
    background-color: #e975ca;
    color: #322a32;
}
"""

def read_val(filepath, pattern, default):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            m = re.search(pattern, f.read())
            if m:
                return float(m.group(1))
    return default

def atomic_write(filepath, text):
    # Safety check: never write an empty or suspiciously tiny file
    if len(text.strip()) < 100:
        return False
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, filepath)
    return True

class StudioApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.marshmellow.studio")
        self.pending_ipc = {}
        self.ipc_timer = None

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        win = Gtk.ApplicationWindow(application=self, title="Marshmellow Studio")
        win.set_decorated(False)
        win.set_resizable(False)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", lambda c, k, kc, s: self.quit() if k == Gdk.KEY_Escape else False)
        win.add_controller(key_ctrl)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.add_css_class("main-box")
        win.set_child(outer)

        hdr = Gtk.Label(label="Marshmellow Studio")
        hdr.add_css_class("title-lbl")
        outer.append(hdr)

        sub = Gtk.Label(label="Drag sliders for live preview  •  Esc to close")
        sub.add_css_class("sub-lbl")
        outer.append(sub)

        gaps_in = read_val(HYPR_CONF, r'\bgaps_in\s*=\s*([0-9.]+)', 5)
        gaps_out = read_val(HYPR_CONF, r'\bgaps_out\s*=\s*([0-9.]+)', 20)
        rounding = read_val(HYPR_CONF, r'\brounding\s*=\s*([0-9.]+)', 10)
        act_op = read_val(HYPR_CONF, r'\bactive_opacity\s*=\s*([0-9.]+)', 0.8) * 100
        inact_op = read_val(HYPR_CONF, r'\binactive_opacity\s*=\s*([0-9.]+)', 0.6) * 100
        wb_op = read_val(WAYBAR_CSS, r'@define-color\s+bg_main\s+rgba\(254,\s*228,\s*255,\s*([0-9.]+)\)', 0.72) * 100

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        outer.append(card)

        self.sliders = {}
        rows = [
            ("gaps_in",  "Window Gaps (Inner)",   0, 30, 1, gaps_in,  "px", "int",   "general:gaps_in"),
            ("gaps_out", "Screen Gaps (Outer)",   0, 50, 1, gaps_out, "px", "int",   "general:gaps_out"),
            ("rounding", "Corner Rounding",       0, 30, 1, rounding, "px", "int",   "decoration:rounding"),
            ("act_op",   "Focused Opacity",      30, 100, 1, act_op,   "%",  "float", "decoration:active_opacity"),
            ("inact_op", "Unfocused Opacity",    20, 100, 1, inact_op, "%",  "float", "decoration:inactive_opacity"),
            ("wb_op",    "Waybar Pill Opacity",  20, 100, 1, wb_op,    "%",  None,    None),
        ]

        for key, label, mn, mx, step, val, unit, mode, hypr_key in rows:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            lbl = Gtk.Label(label=label, xalign=0)
            lbl.add_css_class("row-lbl")

            badge = Gtk.Label(label=f"{int(val)}{unit}")
            badge.add_css_class("val-badge")

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, mn, mx, step)
            scale.set_draw_value(False)
            scale.set_value(val)
            scale.connect("value-changed", self.on_slider, badge, unit, mode, hypr_key)

            self.sliders[key] = scale
            row.append(lbl)
            row.append(scale)
            row.append(badge)
            card.append(row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.set_halign(Gtk.Align.CENTER)
        outer.append(btn_row)

        btn_save = Gtk.Button(label="Save to Configs")
        btn_save.add_css_class("action-pill")
        btn_save.connect("clicked", self.save_all)
        btn_row.append(btn_save)

        btn_wp = Gtk.Button(label="Wallpapers")
        btn_wp.add_css_class("action-pill")
        btn_wp.connect("clicked", lambda b: subprocess.Popen(["/home/lilypersilly/.config/hypr/wallpaper-carousel.py"]))
        btn_row.append(btn_wp)

        btn_git = Gtk.Button(label="Backup to GitHub")
        btn_git.add_css_class("action-pill")
        btn_git.connect("clicked", self.backup_github)
        btn_row.append(btn_git)

        win.present()

    def on_slider(self, scale, badge, unit, mode, hypr_key):
        val = int(scale.get_value())
        badge.set_label(f"{val}{unit}")
        if hypr_key:
            formatted = str(val) if mode == "int" else f"{val / 100.0:.2f}"
            self.pending_ipc[hypr_key] = formatted
            if self.ipc_timer is None:
                self.ipc_timer = GLib.timeout_add(40, self.flush_ipc)

    def flush_ipc(self):
        for k, v in list(self.pending_ipc.items()):
            subprocess.Popen(["hyprctl", "keyword", k, v], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pending_ipc.clear()
        self.ipc_timer = None
        return False

    def save_all(self, btn):
        gi = int(self.sliders["gaps_in"].get_value())
        go = int(self.sliders["gaps_out"].get_value())
        rd = int(self.sliders["rounding"].get_value())
        ao = self.sliders["act_op"].get_value() / 100.0
        io = self.sliders["inact_op"].get_value() / 100.0
        wo = self.sliders["wb_op"].get_value() / 100.0

        if os.path.exists(HYPR_CONF):
            shutil.copy2(HYPR_CONF, HYPR_BAK)
            with open(HYPR_CONF, "r") as f:
                text = f.read()
            text = re.sub(r'(\bgaps_in\s*=\s*)[0-9.]+', f'\\g<1>{gi}', text, count=1)
            text = re.sub(r'(\bgaps_out\s*=\s*)[0-9.]+', f'\\g<1>{go}', text, count=1)
            text = re.sub(r'(\brounding\s*=\s*)[0-9.]+', f'\\g<1>{rd}', text, count=1)
            text = re.sub(r'(\bactive_opacity\s*=\s*)[0-9.]+', f'\\g<1>{ao:.2f}', text, count=1)
            text = re.sub(r'(\binactive_opacity\s*=\s*)[0-9.]+', f'\\g<1>{io:.2f}', text, count=1)
            atomic_write(HYPR_CONF, text)

        if os.path.exists(WAYBAR_CSS):
            with open(WAYBAR_CSS, "r") as f:
                wb_text = f.read()
            wb_text = re.sub(
                r'(@define-color\s+bg_main\s+rgba\(254,\s*228,\s*255,\s*)[0-9.]+(\))',
                f'\\g<1>{wo:.2f}\\g<2>',
                wb_text,
                count=1
            )
            atomic_write(WAYBAR_CSS, wb_text)

        subprocess.Popen("pkill waybar; waybar >/dev/null 2>&1 &", shell=True)
        subprocess.Popen(["notify-send", "🌸 Marshmellow Studio", "Saved atomically (backup in hyprland.lua.bak)!"])

    def backup_github(self, btn):
        cmd = "~/marshmellow-dotfiles/sync.sh && cd ~/marshmellow-dotfiles && git add . && git commit -m 'Marshmellow Studio sync 🌸' && git push && notify-send '☁️ GitHub Backup' 'All dotfiles pushed to GitHub!'"
        subprocess.Popen(cmd, shell=True)

if __name__ == "__main__":
    res = subprocess.run(["pgrep", "-f", "marshmellow-studio.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)
    app = StudioApp()
    app.run(None)
