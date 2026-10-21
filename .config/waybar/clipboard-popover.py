#!/usr/bin/env python3
import gi
import subprocess
import sys
import urllib.parse

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

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
}
button.clear-btn {
    background-image: none;
    background-color: #322a32;
    color: #fee4ff;
    border: 1px solid #e975ca;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: bold;
}
button.clear-btn:hover {
    background-color: #da4453;
    border-color: #da4453;
}
button.clip-item {
    background-image: none;
    background-color: rgba(255, 194, 255, 0.45);
    color: #333933;
    border: 1px solid #f8d4ff;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 600;
}
button.clip-item:hover {
    background-color: #ef96d9;
    border-color: #e975ca;
}
"""

def get_history(limit=25):
    try:
        out = subprocess.check_output(["cliphist", "list"], text=True)
    except Exception:
        return []
    items = []
    for line in out.splitlines()[:limit]:
        parts = line.split("\t", 1)
        if len(parts) == 2:
            items.append((line, parts[0], parts[1]))
    return items

def decode_raw(full_line):
    p = subprocess.Popen(["cliphist", "decode"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = p.communicate(input=full_line.encode())
    return out

class ClipboardDropdown(Gtk.Window):
    def __init__(self):
        super().__init__(title="Clipboard History")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_default_size(360, 420)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.connect("key-press-event", self.on_key)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(14)
        main_box.set_margin_bottom(14)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        self.add(main_box)

        # Header Row
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label(label="󰅌   Clipboard History", xalign=0)
        lbl.get_style_context().add_class("header")
        hdr_box.pack_start(lbl, True, True, 0)

        clear_btn = Gtk.Button(label="󰆴 Clear")
        clear_btn.get_style_context().add_class("clear-btn")
        clear_btn.connect("clicked", self.on_clear)
        hdr_box.pack_end(clear_btn, False, False, 0)
        main_box.pack_start(hdr_box, False, False, 2)

        # Scrollable List
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(340)
        main_box.pack_start(scroll, True, True, 0)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroll.add(self.list_box)

        self.populate()

    def populate(self):
        for child in self.list_box.get_children():
            self.list_box.remove(child)

        items = get_history()
        if not items:
            empty = Gtk.Label(label="Clipboard is empty ")
            empty.set_margin_top(40)
            self.list_box.pack_start(empty, False, False, 0)
            return

        for full_line, item_id, preview in items:
            btn = Gtk.Button()
            btn.get_style_context().add_class("clip-item")

            # 1. Image item
            if "[[ binary data" in preview:
                raw = decode_raw(full_line)
                try:
                    loader = GdkPixbuf.PixbufLoader()
                    loader.write(raw)
                    loader.close()
                    pix = loader.get_pixbuf()
                    w, h = pix.get_width(), pix.get_height()
                    new_w = 260
                    new_h = max(40, min(140, int(h * (new_w / w))))
                    scaled = pix.scale_simple(new_w, new_h, GdkPixbuf.InterpType.BILINEAR)
                    img = Gtk.Image.new_from_pixbuf(scaled)
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                    lbl = Gtk.Label(label=f"󰋩   Image ({w}x{h})", xalign=0)
                    box.pack_start(lbl, False, False, 0)
                    box.pack_start(img, False, False, 0)
                    btn.add(box)
                    btn.connect("clicked", self.on_select, full_line, "image")
                except Exception:
                    lbl = Gtk.Label(label=f"󰏗   {preview}", xalign=0)
                    btn.add(lbl)
                    btn.connect("clicked", self.on_select, full_line, "raw")

            # 2. Copied File(s) from Dolphin
            elif "file://" in preview:
                clean = urllib.parse.unquote(preview).replace("copy", "").replace("file://", "").strip()
                lbl = Gtk.Label(label=f"󰉋   File: {clean}", xalign=0)
                lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                lbl.set_max_width_chars(38)
                btn.add(lbl)
                btn.connect("clicked", self.on_select, full_line, "file")

            # 3. Normal Text
            else:
                lbl = Gtk.Label(label=f"󰈙   {preview.strip()}", xalign=0)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                lbl.set_max_width_chars(38)
                btn.add(lbl)
                btn.connect("clicked", self.on_select, full_line, "text")

            self.list_box.pack_start(btn, False, False, 0)

        self.show_all()

    def on_select(self, btn, full_line, mode):
        raw = decode_raw(full_line)
        if mode == "file":
            # Restore as URI list so Dolphin can Ctrl+V paste the file
            uris = "\n".join([s for s in raw.decode(errors="ignore").split() if s.startswith("file://")]) + "\n"
            p = subprocess.Popen(["wl-copy", "--type", "text/uri-list"], stdin=subprocess.PIPE)
            p.communicate(input=uris.encode())
        else:
            p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
            p.communicate(input=raw)
        Gtk.main_quit()

    def on_clear(self, btn):
        subprocess.run(["cliphist", "wipe"])
        self.populate()

    def on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

if __name__ == "__main__":
    res = subprocess.run(["pgrep", "-f", "clipboard-popover.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)

    win = ClipboardDropdown()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
