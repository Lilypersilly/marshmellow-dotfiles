use gdk::prelude::*;
use gtk::prelude::*;
use percent_encoding::percent_decode_str;
use std::cell::{Cell, RefCell};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::rc::Rc;
use std::thread;
use std::time::Duration;

const CSS: &[u8] = br#"
window, window:backdrop, window.background {
    background-color: rgba(254, 228, 255, 0.35);
    background-image: none;
    border: none;
    border-radius: 0;
    font-family: "Josefin Sans", "JetBrainsMono Nerd Font", sans-serif;
}
.header { font-size: 15px; font-weight: bold; color: #bf40a1; }
.title { font-size: 16px; font-weight: bold; color: #322a32; }
.artist { font-size: 13px; color: #856d8a; font-weight: bold; }
.time-lbl { font-size: 11px; color: #504250; font-weight: bold; }
progressbar trough {
    min-height: 6px;
    border-radius: 999px;
    background-color: rgba(50, 42, 50, 0.35);
    border: none;
}
progressbar progress {
    min-height: 6px;
    border-radius: 999px;
    background-color: #e975ca;
    border: none;
}
button.ctrl-btn {
    background-image: none;
    background-color: rgba(255, 194, 255, 0.8);
    color: #322a32;
    border: 2px solid #e975ca;
    border-radius: 999px;
    min-width: 46px;
    min-height: 46px;
    font-size: 20px;
    margin: 4px;
}
button.ctrl-btn:hover {
    background-color: #ef96d9;
    border-color: #bf40a1;
}
"#;

struct MediaState {
    current_title: String,
    current_artist: String,
    current_art_url: String,
    current_status: String,
}

fn fmt_time(microseconds: f64) -> String {
    let secs = (microseconds / 1_000_000.0) as u64;
    format!("{:02}:{:02}", secs / 60, secs % 60)
}

fn fetch_art_in_background(art_url: String, sender: glib::Sender<(String, Option<String>)>) {
    thread::spawn(move || {
        let mut art_path: Option<String> = None;

        if art_url.starts_with("file://") {
            let path_part = &art_url["file://".len()..];
            let decoded = percent_decode_str(path_part).decode_utf8_lossy();
            art_path = Some(decoded.to_string());
        } else if art_url.starts_with("http://") || art_url.starts_with("https://") {
            let res = ureq::get(&art_url)
                .set("User-Agent", "Mozilla/5.0")
                .timeout(Duration::from_secs(2))
                .call();

            if let Ok(response) = res {
                let cache_path = "/tmp/waybar_art.jpg";
                let mut reader = response.into_reader();
                if let Ok(mut out_file) = fs::File::create(cache_path) {
                    if std::io::copy(&mut reader, &mut out_file).is_ok() {
                        art_path = Some(cache_path.to_string());
                    }
                }
            }
        }

        let _ = sender.send((art_url, art_path));
    });
}

fn refresh_metadata(
    state: &Rc<RefCell<MediaState>>,
    lbl_title: &gtk::Label,
    lbl_artist: &gtk::Label,
    btn_play: &gtk::Button,
    prog_bar: &gtk::ProgressBar,
    lbl_pos: &gtk::Label,
    lbl_len: &gtk::Label,
    art_sender: &glib::Sender<(String, Option<String>)>,
) {
    let output = Command::new("playerctl")
        .args([
            "metadata",
            "--format",
            "{{title}}|||{{artist}}|||{{mpris:artUrl}}|||{{status}}|||{{position}}|||{{mpris:length}}",
        ])
        .output();

    let (title, artist, art_url, status, pos, length) = match output {
        Ok(out) if out.status.success() => {
            let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
            let parts: Vec<&str> = text.split("|||").collect();
            if parts.len() == 6 {
                (
                    parts[0].to_string(),
                    parts[1].to_string(),
                    parts[2].to_string(),
                    parts[3].to_string(),
                    parts[4].to_string(),
                    parts[5].to_string(),
                )
            } else {
                default_media_info()
            }
        }
        _ => default_media_info(),
    };

    let mut st = state.borrow_mut();

    if title != st.current_title || artist != st.current_artist {
        st.current_title = title.clone();
        st.current_artist = artist.clone();
        lbl_title.set_text(&title);
        lbl_artist.set_text(&artist);
    }

    if status != st.current_status {
        st.current_status = status.clone();
        btn_play.set_label(if status == "Playing" { "󰏤" } else { "󰐊" });
    }

    let p_val = pos.parse::<f64>().unwrap_or(0.0);
    let l_val = length.parse::<f64>().unwrap_or(0.0);

    if l_val > 0.0 {
        prog_bar.set_fraction((p_val / l_val).clamp(0.0, 1.0));
        lbl_pos.set_text(&fmt_time(p_val));
        lbl_len.set_text(&fmt_time(l_val));
    } else {
        prog_bar.set_fraction(0.0);
        lbl_pos.set_text("00:00");
        lbl_len.set_text("00:00");
    }

    if art_url != st.current_art_url {
        st.current_art_url = art_url.clone();
        fetch_art_in_background(art_url, art_sender.clone());
    }
}

fn default_media_info() -> (String, String, String, String, String, String) {
    (
        "No Media Playing".into(),
        "Play something first!".into(),
        "".into(),
        "Stopped".into(),
        "0".into(),
        "0".into(),
    )
}

fn get_pid_file() -> PathBuf {
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(runtime_dir).join("media-popover.pid")
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
    window.set_title("Media Control");
    window.set_decorated(false);
    window.set_keep_above(true);
    window.set_default_size(320, -1);

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
    main_box.set_margin_top(16);
    main_box.set_margin_bottom(16);
    main_box.set_margin_start(16);
    main_box.set_margin_end(16);
    window.add(&main_box);

    let hdr_lbl = gtk::Label::new(Some("   Now Playing"));
    hdr_lbl.set_xalign(0.0);
    hdr_lbl.style_context().add_class("header");
    main_box.pack_start(&hdr_lbl, false, false, 0);

    let info_box = gtk::Box::new(gtk::Orientation::Horizontal, 12);
    main_box.pack_start(&info_box, false, false, 4);

    let art_holder = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    art_holder.set_size_request(80, 80);
    let placeholder = gtk::Label::new(Some(""));
    placeholder.set_size_request(80, 80);
    art_holder.pack_start(&placeholder, true, true, 0);
    info_box.pack_start(&art_holder, false, false, 0);

    let text_box = gtk::Box::new(gtk::Orientation::Vertical, 4);
    text_box.set_valign(gtk::Align::Center);
    info_box.pack_start(&text_box, true, true, 0);

    let lbl_title = gtk::Label::new(Some("Loading..."));
    lbl_title.set_xalign(0.0);
    lbl_title.style_context().add_class("title");
    lbl_title.set_ellipsize(pango::EllipsizeMode::End);
    lbl_title.set_max_width_chars(20);
    text_box.pack_start(&lbl_title, false, false, 0);

    let lbl_artist = gtk::Label::new(Some(""));
    lbl_artist.set_xalign(0.0);
    lbl_artist.style_context().add_class("artist");
    lbl_artist.set_ellipsize(pango::EllipsizeMode::End);
    lbl_artist.set_max_width_chars(20);
    text_box.pack_start(&lbl_artist, false, false, 0);

    let prog_bar = gtk::ProgressBar::new();
    main_box.pack_start(&prog_bar, false, false, 2);

    let time_box = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    let lbl_pos = gtk::Label::new(Some("00:00"));
    lbl_pos.set_xalign(0.0);
    lbl_pos.style_context().add_class("time-lbl");

    let lbl_len = gtk::Label::new(Some("00:00"));
    lbl_len.set_xalign(1.0);
    lbl_len.style_context().add_class("time-lbl");

    time_box.pack_start(&lbl_pos, true, true, 0);
    time_box.pack_end(&lbl_len, true, true, 0);
    main_box.pack_start(&time_box, false, false, 0);

    let ctrl_box = gtk::Box::new(gtk::Orientation::Horizontal, 0);
    ctrl_box.set_halign(gtk::Align::Center);
    main_box.pack_start(&ctrl_box, false, false, 2);

    let btn_prev = gtk::Button::with_label("󰒮");
    btn_prev.style_context().add_class("ctrl-btn");
    btn_prev.connect_clicked(|_| {
        let _ = Command::new("playerctl").arg("previous").spawn();
    });
    ctrl_box.pack_start(&btn_prev, false, false, 0);

    let btn_play = gtk::Button::with_label("󰐊");
    btn_play.style_context().add_class("ctrl-btn");
    {
        let btn_play_clone = btn_play.clone();
        btn_play.connect_clicked(move |_| {
            let _ = Command::new("playerctl").arg("play-pause").spawn();
            let cur = btn_play_clone.label().unwrap_or_default();
            btn_play_clone.set_label(if cur == "󰏤" { "󰐊" } else { "󰏤" });
        });
    }
    ctrl_box.pack_start(&btn_play, false, false, 0);

    let btn_next = gtk::Button::with_label("󰒭");
    btn_next.style_context().add_class("ctrl-btn");
    btn_next.connect_clicked(|_| {
        let _ = Command::new("playerctl").arg("next").spawn();
    });
    ctrl_box.pack_start(&btn_next, false, false, 0);

    // Auto-close handling
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

    {
        let has_entered = has_entered.clone();
        glib::timeout_add_local(Duration::from_millis(2500), move || {
            has_entered.set(true);
            glib::ControlFlow::Break
        });
    }

    {
        let has_entered = has_entered.clone();
        let cancel_close_timer = cancel_close_timer.clone();
        window.connect_enter_notify_event(move |_, _| {
            has_entered.set(true);
            cancel_close_timer();
            glib::Propagation::Proceed
        });
    }

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

    // Metadata refresh state
    let state = Rc::new(RefCell::new(MediaState {
        current_title: String::new(),
        current_artist: String::new(),
        current_art_url: String::new(),
        current_status: String::new(),
    }));

    // GLib MainContext channel for thread-safe art updates
    let (art_sender, art_receiver) = glib::MainContext::channel::<(String, Option<String>)>(glib::Priority::default());
    {
        let art_holder = art_holder.clone();
        let state = state.clone();

        art_receiver.attach(None, move |(requested_url, art_path)| {
            if state.borrow().current_art_url != requested_url {
                return glib::ControlFlow::Continue;
            }

            for child in art_holder.children() {
                art_holder.remove(&child);
            }

            let mut pixbuf_img: Option<gtk::Image> = None;
            if let Some(path) = art_path {
                if Path::new(&path).exists() {
                    if let Ok(pix) = gdk_pixbuf::Pixbuf::from_file_at_scale(&path, 80, 80, true) {
                        pixbuf_img = Some(gtk::Image::from_pixbuf(Some(&pix)));
                    }
                }
            }

            let widget: gtk::Widget = match pixbuf_img {
                Some(img) => img.upcast(),
                None => {
                    let lbl = gtk::Label::new(Some(""));
                    lbl.set_size_request(80, 80);
                    lbl.upcast()
                }
            };

            art_holder.pack_start(&widget, true, true, 0);
            art_holder.show_all();

            glib::ControlFlow::Continue
        });
    }

    // Initial load
    refresh_metadata(
        &state,
        &lbl_title,
        &lbl_artist,
        &btn_play,
        &prog_bar,
        &lbl_pos,
        &lbl_len,
        &art_sender,
    );

    window.show_all();

    // 400ms periodic update loop
    {
        let state = state.clone();
        let lbl_title = lbl_title.clone();
        let lbl_artist = lbl_artist.clone();
        let btn_play = btn_play.clone();
        let prog_bar = prog_bar.clone();
        let lbl_pos = lbl_pos.clone();
        let lbl_len = lbl_len.clone();
        let art_sender = art_sender.clone();

        glib::timeout_add_local(Duration::from_millis(400), move || {
            refresh_metadata(
                &state,
                &lbl_title,
                &lbl_artist,
                &btn_play,
                &prog_bar,
                &lbl_pos,
                &lbl_len,
                &art_sender,
            );
            glib::ControlFlow::Continue
        });
    }

    gtk::main();
    cleanup_pid_file();
}