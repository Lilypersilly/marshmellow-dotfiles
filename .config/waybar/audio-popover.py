#!/usr/bin/env python3
import gi
import subprocess
import re
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

CSS = b"""
window {
    background-color: #fee4ff;
    border: none;
    border-radius: 0px;
    font-family: "Josefin Sans", "JetBrainsMono Nerd Font", sans-serif;
    color: #333933;
}
.header {
    font-size: 15px;
    font-weight: bold;
    color: #bf40a1;
    margin-top: 6px;
    margin-bottom: 4px;
}
scale trough {
    border: none;
    background-color: #322a32;
    border-radius: 8px;
    min-height: 10px;
}
scale highlight {
    border: none;
    background-color: #e975ca;
    border-radius: 8px;
}
scale slider {
    background-color: #ffc2ff;
    border: 2px solid #bf40a1;
    border-radius: 50%;
    min-width: 18px;
    min-height: 18px;
    margin: -5px;
}
button.device-btn {
    background-image: none;
    background-color: rgba(255, 194, 255, 0.45);
    color: #333933;
    border: 1px solid #f8d4ff;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 600;
}
button.device-btn:hover {
    background-color: #ef96d9;
    border-color: #e975ca;
}
button.device-active {
    background-image: none;
    background-color: #322a32;
    color: #fee4ff;
    border: 2px solid #e975ca;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: bold;
}
"""

def parse_wpctl():
    out = subprocess.check_output(["wpctl", "status"], text=True)
    sinks, sources = [], []
    mode = None
    for line in out.splitlines():
        if "Sinks:" in line:
            mode = "sinks"
            continue
        elif "Sources:" in line:
            mode = "sources"
            continue
        elif any(h in line for h in ["Sink endpoints:", "Source endpoints:", "Filters:", "Streams:", "Video"]):
            mode = None
            continue

        if mode in ("sinks", "sources"):
            active = "*" in line
            m = re.search(r'(\d+)\.\s+(.+?)(?:\s+\[vol:|$)', line)
            if m:
                dev_id, name = m.group(1), m.group(2).strip()
                item = (dev_id, name, active)
                if mode == "sinks":
                    sinks.append(item)
                else:
                    sources.append(item)
    return sinks, sources

def get_volume():
    out = subprocess.check_output(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], text=True)
    m = re.search(r'([0-9.]+)', out)
    vol = float(m.group(1)) * 100 if m else 50
    muted = "MUTED" in out
    return vol, muted

class AudioDropdown(Gtk.Window):
    def __init__(self):
        super().__init__(title="Audio Control")
        self.set_Name = "audio-dropdown"
        self.set_wmclass("audio-dropdown", "audio-dropdown")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_default_size(340, -1)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.connect("key-press-event", self.on_key)
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.vbox.set_margin_top(14)
        self.vbox.set_margin_bottom(14)
        self.vbox.set_margin_start(16)
        self.vbox.set_margin_end(16)
        self.add(self.vbox)
        self.build_ui()

    def build_ui(self):
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        vol, muted = get_volume()
        sinks, sources = parse_wpctl()

        # --- VOLUME SLIDER ---
        lbl_vol = Gtk.Label(label=f"   Output Volume ({int(vol)}%)" if not muted else "󰝟   Muted", xalign=0)
        lbl_vol.get_style_context().add_class("header")
        self.vbox.pack_start(lbl_vol, False, False, 0)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(False)
        scale.set_value(vol)
        scale.connect("value-changed", self.on_vol_change, lbl_vol)
        self.vbox.pack_start(scale, False, False, 4)

        # --- OUTPUT DEVICES ---
        lbl_out = Gtk.Label(label="󰋋   Output Device", xalign=0)
        lbl_out.get_style_context().add_class("header")
        self.vbox.pack_start(lbl_out, False, False, 0)

        for dev_id, name, active in sinks:
            btn = Gtk.Button(label=("●  " if active else "○  ") + name)
            btn.get_child().set_xalign(0)
            btn.get_style_context().add_class("device-active" if active else "device-btn")
            btn.connect("clicked", self.on_device_click, dev_id)
            self.vbox.pack_start(btn, False, False, 0)

        # --- INPUT DEVICES ---
        lbl_in = Gtk.Label(label="   Input Device (Mic)", xalign=0)
        lbl_in.get_style_context().add_class("header")
        self.vbox.pack_start(lbl_in, False, False, 0)

        for dev_id, name, active in sources:
            btn = Gtk.Button(label=("●  " if active else "○  ") + name)
            btn.get_child().set_xalign(0)
            btn.get_style_context().add_class("device-active" if active else "device-btn")
            btn.connect("clicked", self.on_device_click, dev_id)
            self.vbox.pack_start(btn, False, False, 0)

        self.show_all()

    def on_vol_change(self, scale, lbl):
        val = int(scale.get_value())
        subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{val}%"])
        lbl.set_text(f"   Output Volume ({val}%)")

    def on_device_click(self, btn, dev_id):
        subprocess.run(["wpctl", "set-default", dev_id])
        self.build_ui()

    def on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

if __name__ == "__main__":
    # Toggle behavior: if already running, close it
    res = subprocess.run(["pgrep", "-f", "audio-popover.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)

    win = AudioDropdown()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
