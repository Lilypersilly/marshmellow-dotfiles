use gdk::prelude::*;
use gdk_pixbuf::prelude::*;
use gtk::prelude::*;
use percent_encoding::percent_decode_str;
use std::cell::{Cell, RefCell};
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::rc::Rc;
use std::time::Duration;

const CSS: &[u8] = br#"
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
"#;

struct ClipItem {
    full_line: String,
    preview: String,
}

fn get_history(limit: usize) -> Vec<ClipItem> {
    let output = Command::new("cliphist")
        .arg("list")
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
        .unwrap_or_default();

    let mut items = Vec::new();
    for line in output.lines().take(limit) {
        let parts: Vec<&str> = line.splitn(2, '\t').collect();
        if parts.len() == 2 {
            items.push(ClipItem {
                full_line: line.to_string(),
                preview: parts[1].to_string(),
            });
        }
    }
    items
}

fn decode_raw(full_line: &str) -> Vec<u8> {
    let mut child = match Command::new("cliphist")
        .arg("decode")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    if let Some(mut stdin) = child.stdin.take() {
        let _ = stdin.write_all(full_line.as_bytes());
    }

    child
        .wait_with_output()
        .map(|o| o.stdout)
        .unwrap_or_default()
}

fn copy_to_clipboard(data: &[u8], is_uri: bool) {
    let mut cmd = Command::new("wl-copy");
    if is_uri {
        cmd.args(["--type", "text/uri-list"]);
    }
    cmd.stdin(Stdio::piped());

    if let Ok(mut child) = cmd.spawn() {
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(data);
        }
        let _ = child.wait();
    }
}

fn populate(list_box: &gtk::Box) {
    for child in list_box.children() {
        list_box.remove(&child);
    }

    let items = get_history(12);
    if items.is_empty() {
        let empty = gtk::Label::new(Some("Clipboard is empty"));
        empty.set_margin_top(40);
        list_box.pack_start(&empty, false, false, 0);
        list_box.show_all();
        return;
    }

    for item in items {
        let btn = gtk::Button::new();
        btn.style_context().add_class("clip-item");

        let full_line = item.full_line;
        let preview = item.preview;

        if preview.contains("[[ binary data") {
            let raw = decode_raw(&full_line);

            // Attempt to load as pixbuf
            let pixbuf_res = (|| -> Result<gdk_pixbuf::Pixbuf, glib::Error> {
                let loader = gdk_pixbuf::PixbufLoader::new();
                loader.write(&raw)?;
                loader.close()?;
                loader
                    .pixbuf()
                    .ok_or_else(|| glib::Error::new(glib::FileError::Failed, "No pixbuf"))
            })();

            if let Ok(pix) = pixbuf_res {
                let w = pix.width();
                let h = pix.height();
                let new_w = 260;
                let new_h = if w > 0 {
                    (h as f64 * (new_w as f64 / w as f64)) as i32
                } else {
                    40
                }
                .clamp(40, 140);

                let scaled = pix.scale_simple(new_w, new_h, gdk_pixbuf::InterpType::Bilinear);
                let img = match scaled {
                    Some(s) => gtk::Image::from_pixbuf(Some(&s)),
                    None => gtk::Image::from_pixbuf(Some(&pix)),
                };

                let box_inner = gtk::Box::new(gtk::Orientation::Vertical, 4);
                let lbl = gtk::Label::new(Some(&format!("󰋩   Image ({w}x{h})")));
                lbl.set_xalign(0.0);
                box_inner.pack_start(&lbl, false, false, 0);
                box_inner.pack_start(&img, false, false, 0);
                btn.add(&box_inner);

                let raw_clone = raw.clone();
                btn.connect_clicked(move |_| {
                    copy_to_clipboard(&raw_clone, false);
                    gtk::main_quit();
                });
            } else {
                let lbl = gtk::Label::new(Some(&format!("󰏗   {preview}")));
                lbl.set_xalign(0.0);
                btn.add(&lbl);

                let raw_clone = raw.clone();
                btn.connect_clicked(move |_| {
                    copy_to_clipboard(&raw_clone, false);
                    gtk::main_quit();
                });
            }
        } else if preview.contains("file://") {
            let clean = percent_decode_str(&preview)
                .decode_utf8_lossy()
                .replace("copy", "")
                .replace("file://", "")
                .trim()
                .to_string();

            let lbl = gtk::Label::new(Some(&format!("󰉋   File: {clean}")));
            lbl.set_xalign(0.0);
            lbl.set_ellipsize(pango::EllipsizeMode::Middle);
            lbl.set_max_width_chars(38);
            btn.add(&lbl);

            let fl = full_line.clone();
            btn.connect_clicked(move |_| {
                let raw = decode_raw(&fl);
                let text = String::from_utf8_lossy(&raw);
                let mut uris = String::new();
                for token in text.split_whitespace() {
                    if token.starts_with("file://") {
                        uris.push_str(token);
                        uris.push('\n');
                    }
                }
                copy_to_clipboard(uris.as_bytes(), true);
                gtk::main_quit();
            });
        } else {
            let lbl = gtk::Label::new(Some(&format!("󰈙   {}", preview.trim())));
            lbl.set_xalign(0.0);
            lbl.set_ellipsize(pango::EllipsizeMode::End);
            lbl.set_max_width_chars(38);
            btn.add(&lbl);

            let fl = full_line.clone();
            btn.connect_clicked(move |_| {
                let raw = decode_raw(&fl);
                copy_to_clipboard(&raw, false);
                gtk::main_quit();
            });
        }

        list_box.pack_start(&btn, false, false, 0);
    }

    list_box.show_all();
}

fn get_pid_file() -> PathBuf {
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(runtime_dir).join("clipboard-popover.pid")
}

fn toggle_single_instance() {
    let pid_file = get_pid_file();

    if pid_file.exists() {
        if let Ok(content) = fs::read_to_string(&pid_file) {
            if let Ok(old_pid) = content.trim().parse::<i32>() {
                let is_running = Command::new("kill")
                    .args(["-0", &old_pid.to_string()])
                    .status()
                    .map(|s| s.success())
                    .unwrap_or(false);

                if is_running {
                    let _ = Command::new("kill").arg(old_pid.to_string()).status();
                    let _ = fs::remove_file(&pid_file);
                    std::process::exit(0);
                }
            }
        }
        let _ = fs::remove_file(&pid_file);
    }

    let my_pid = std::process::id();
    let _ = fs::write(&pid_file, my_pid.to_string());
}

fn cleanup_pid_file() {
    let pid_file = get_pid_file();
    let _ = fs::remove_file(pid_file);
}

fn main() {
    toggle_single_instance();

    if gtk::init().is_err() {
        eprintln!("Failed to initialize GTK.");
        cleanup_pid_file();
        std::process::exit(1);
    }

    let window = gtk::Window::new(gtk::WindowType::Toplevel);
    window.set_title("Clipboard History");
    window.set_decorated(false);
    window.set_keep_above(true);
    window.set_default_size(360, 420);

    // Alpha channel / transparent visual support
    if let Some(screen) = gtk::prelude::GtkWindowExt::screen(&window) {
        if screen.is_composited() {
            if let Some(visual) = screen.rgba_visual() {
                window.set_visual(Some(&visual));
            }
        }

        let provider = gtk::CssProvider::new();
        let _ = provider.load_from_data(CSS);
        gtk::StyleContext::add_provider_for_screen(
            &screen,
            &provider,
            gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
        );
    }

    let main_box = gtk::Box::new(gtk::Orientation::Vertical, 8);
    main_box.set_margin_top(14);
    main_box.set_margin_bottom(14);
    main_box.set_margin_start(16);
    main_box.set_margin_end(16);
    window.add(&main_box);

    let hdr_box = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    let lbl = gtk::Label::new(Some("󰅌   Clipboard History"));
    lbl.set_xalign(0.0);
    lbl.style_context().add_class("header");
    hdr_box.pack_start(&lbl, true, true, 0);

    let list_box = gtk::Box::new(gtk::Orientation::Vertical, 6);

    let clear_btn = gtk::Button::with_label("󰆴 Clear");
    clear_btn.style_context().add_class("clear-btn");
    {
        let list_box_clone = list_box.clone();
        clear_btn.connect_clicked(move |_| {
            let _ = Command::new("cliphist").arg("wipe").status();
            populate(&list_box_clone);
        });
    }
    hdr_box.pack_end(&clear_btn, false, false, 0);
    main_box.pack_start(&hdr_box, false, false, 2);

    let scroll = gtk::ScrolledWindow::new(
        gtk::Adjustment::NONE,
        gtk::Adjustment::NONE,
    );
    scroll.set_policy(gtk::PolicyType::Never, gtk::PolicyType::Automatic);
    scroll.set_min_content_height(340);
    scroll.add(&list_box);
    main_box.pack_start(&scroll, true, true, 0);

    // Auto-close logic
    let close_timer: Rc<RefCell<Option<glib::SourceId>>> = Rc::new(RefCell::new(None));
    let has_entered = Rc::new(Cell::new(false));

    window.add_events(gdk::EventMask::ENTER_NOTIFY_MASK | gdk::EventMask::LEAVE_NOTIFY_MASK);

    let start_close_timer = {
        let close_timer = close_timer.clone();
        move || {
            let mut timer = close_timer.borrow_mut();
            if timer.is_none() {
                *timer = Some(glib::timeout_add_local(Duration::from_millis(500), || {
                    cleanup_pid_file();
                    gtk::main_quit();
                    glib::ControlFlow::Break
                }));
            }
        }
    };

    let cancel_close_timer = {
        let close_timer = close_timer.clone();
        move || {
            let mut timer = close_timer.borrow_mut();
            if let Some(source_id) = timer.take() {
                source_id.remove();
            }
        }
    };

    // Arm auto-close after 2.5 seconds
    {
        let has_entered = has_entered.clone();
        glib::timeout_add_local(Duration::from_millis(2500), move || {
            has_entered.set(true);
            glib::ControlFlow::Break
        });
    }

    // Pointer Enter
    {
        let has_entered = has_entered.clone();
        let cancel_close_timer = cancel_close_timer.clone();
        window.connect_enter_notify_event(move |_, _| {
            has_entered.set(true);
            cancel_close_timer();
            glib::Propagation::Proceed
        });
    }

    // Pointer Leave
    {
        let has_entered = has_entered.clone();
        let start_close_timer = start_close_timer.clone();
        window.connect_leave_notify_event(move |_, event| {
            if event.detail() == gdk::NotifyType::Inferior {
                return glib::Propagation::Proceed;
            }
            if has_entered.get() {
                start_close_timer();
            }
            glib::Propagation::Proceed
        });
    }

    // Focus Out
    {
        let has_entered = has_entered.clone();
        let start_close_timer = start_close_timer.clone();
        window.connect_focus_out_event(move |_, _| {
            if has_entered.get() {
                start_close_timer();
            }
            glib::Propagation::Proceed
        });
    }

    // Escape Key
    window.connect_key_press_event(|_, event| {
        if event.keyval() == gdk::keys::constants::Escape {
            cleanup_pid_file();
            gtk::main_quit();
        }
        glib::Propagation::Proceed
    });

    window.connect_destroy(|_| {
        cleanup_pid_file();
        gtk::main_quit();
    });

    populate(&list_box);
    window.show_all();

    gtk::main();
    cleanup_pid_file();
}