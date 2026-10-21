#!/usr/bin/env python3
import gi
import subprocess
import re
import sys

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

CSS = b"""
window, window:backdrop, window.background {
    background-color: rgba(254, 228, 255, 0.35);
    background-image: none;
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
    background-color: #322a32;
    border: none;
    border-radius: 8px;
    min-height: 10px;
}
scale highlight {
    background-color: #e975ca;
    border: none;
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
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_default_size(340, -1)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.connect("key-press-event", self.on_key)
        self.setup_auto_close()

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.vbox.set_margin_top(14)
        self.vbox.set_margin_bottom(14)
        self.vbox.set_margin_start(16)
        self.vbox.set_margin_end(16)
        self.add(self.vbox)
        self.show_all()
        GLib.idle_add(self.build_ui)

    def build_ui(self):
        for child in self.vbox.get_children():
            self.vbox.remove(child)

        vol, muted = get_volume()
        sinks, sources = parse_wpctl()

        lbl_vol = Gtk.Label(label=f"   Output Volume ({int(vol)}%)" if not muted else "󰝟   Muted", xalign=0)
        lbl_vol.get_style_context().add_class("header")
        self.vbox.pack_start(lbl_vol, False, False, 0)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(False)
        scale.set_value(vol)
        scale.connect("value-changed", self.on_vol_change, lbl_vol)
        self.vbox.pack_start(scale, False, False, 4)

        lbl_out = Gtk.Label(label="󰋋   Output Device", xalign=0)
        lbl_out.get_style_context().add_class("header")
        self.vbox.pack_start(lbl_out, False, False, 0)

        for dev_id, name, active in sinks:
            btn = Gtk.Button(label=("●  " if active else "○  ") + name)
            btn.get_child().set_xalign(0)
            btn.get_style_context().add_class("device-active" if active else "device-btn")
            btn.connect("clicked", self.on_device_click, dev_id)
            self.vbox.pack_start(btn, False, False, 0)

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

    def setup_auto_close(self):
        self._close_timer = None
        self._has_entered = False
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("focus-out-event", self._on_focus_out)
        # If user never moves mouse into the popup within 2.5s, allow close
        GLib.timeout_add(2500, self._arm_close)

    def _arm_close(self):
        self._has_entered = True
        return False

    def _start_close_timer(self):
        if self._close_timer is None:
            self._close_timer = GLib.timeout_add(500, Gtk.main_quit)

    def _cancel_close_timer(self):
        if self._close_timer is not None:
            GLib.source_remove(self._close_timer)
            self._close_timer = None

    def _on_enter(self, widget, event):
        self._has_entered = True
        self._cancel_close_timer()
        return False

    def _on_leave(self, widget, event):
        # Ignore when mouse moves onto a button/slider inside the popup itself
        if event.detail == Gdk.NotifyType.INFERIOR:
            return False
        if self._has_entered:
            self._start_close_timer()
        return False

    def _on_focus_out(self, *args):
        if self._has_entered:
            self._start_close_timer()
        return False

    def on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

if __name__ == "__main__":
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
