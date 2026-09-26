// MeshGate Studio — desktop shell. Starts the local Studio server (apps/studio/server.py, pure-stdlib Python) with a
// fresh session token, waits for its "MESHGATE_STUDIO <url>" line and shows that page in the window. All the work —
// AI command-line tools, Blender, validation — happens in the server, exactly as with `meshgate.py studio`.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{AppHandle, Manager, RunEvent, Url};

struct Server(Mutex<Option<Child>>);
/// Where the server listens and its token, for the shutdown call when the app quits.
struct Endpoint(Mutex<Option<(u16, String)>>);

/// Ask the server to cancel its jobs (and their Blender) and stop, then wait a moment for it to exit.
fn shutdown_server(port: u16, token: &str, child: &mut Child) {
    use std::io::{Read, Write};
    use std::net::{SocketAddr, TcpStream};
    use std::time::{Duration, Instant};
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    if let Ok(mut s) = TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        let _ = s.set_read_timeout(Some(Duration::from_secs(2)));
        let req = format!(
            "POST /api/shutdown HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-MeshGate-Token: {token}\r\n\
             Content-Type: application/json\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{{}}"
        );
        let _ = s.write_all(req.as_bytes());
        let mut buf = [0u8; 256];
        let _ = s.read(&mut buf);
    }
    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(20) {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

/// 128-bit session token from the OS-seeded hasher keys (no extra crates).
fn token() -> String {
    (0..2)
        .map(|i| {
            let mut h = RandomState::new().build_hasher();
            h.write_u64((std::process::id() as u64) ^ ((i as u64) << 32));
            format!("{:016x}", h.finish())
        })
        .collect()
}

/// The MeshGate files: MESHGATE_ROOT, the app bundle's resources, or the repository in a dev build.
fn meshgate_root(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(p) = std::env::var("MESHGATE_ROOT") {
        let p = PathBuf::from(p);
        if p.join("meshgate.py").exists() {
            return Some(p);
        }
    }
    if let Ok(res) = app.path().resource_dir() {
        let p = res.join("meshgate");
        if p.join("meshgate.py").exists() {
            return Some(p);
        }
    }
    let dev = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../..");
    if dev.join("meshgate.py").exists() {
        return dev.canonicalize().ok();
    }
    None
}

/// Apps started from Finder or the Start menu get a minimal PATH; AI CLIs usually live in the user's shell PATH
/// (Homebrew, ~/.local/bin, npm globals). Ask the login shell once and add the usual folders.
fn user_path() -> String {
    let mut parts: Vec<String> = Vec::new();
    #[cfg(not(windows))]
    {
        let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/zsh".into());
        if let Ok(out) = Command::new(&shell).args(["-ilc", "printf '%s' \"$PATH\""]).stdin(Stdio::null()).output() {
            let p = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !p.is_empty() {
                parts.push(p);
            }
        }
        if let Ok(home) = std::env::var("HOME") {
            for d in [".local/bin", ".npm-global/bin", ".bun/bin", ".cargo/bin"] {
                parts.push(format!("{home}/{d}"));
            }
        }
        parts.extend(["/opt/homebrew/bin", "/usr/local/bin"].iter().map(|s| s.to_string()));
    }
    if let Ok(p) = std::env::var("PATH") {
        parts.push(p);
    }
    parts.join(if cfg!(windows) { ";" } else { ":" })
}

/// A Python 3.9+ that can run the server: MESHGATE_PYTHON, then the usual names and locations.
fn find_python(path: &str) -> Option<Vec<String>> {
    let mut candidates: Vec<Vec<String>> = Vec::new();
    if let Ok(p) = std::env::var("MESHGATE_PYTHON") {
        candidates.push(vec![p]);
    }
    let names: &[&[&str]] = if cfg!(windows) {
        &[&["py", "-3"], &["python"], &["python3"]]
    } else {
        &[&["python3"], &["/opt/homebrew/bin/python3"], &["/usr/local/bin/python3"], &["/usr/bin/python3"], &["python"]]
    };
    candidates.extend(names.iter().map(|c| c.iter().map(|s| s.to_string()).collect()));
    for c in candidates {
        let mut cmd = Command::new(&c[0]);
        cmd.args(&c[1..]).args(["-c", "import sys; print(sys.version_info >= (3, 9))"]).env("PATH", path);
        hide_console(&mut cmd);
        if let Ok(out) = cmd.output() {
            if String::from_utf8_lossy(&out.stdout).trim() == "True" {
                return Some(c);
            }
        }
    }
    None
}

fn hide_console(_cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        _cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
}

fn show_error(app: &AppHandle, text: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let js = format!("window.showError({})", serde_json::to_string(text).unwrap_or_default());
        let _ = w.eval(&js);
    }
}

fn start_server(app: AppHandle) {
    let Some(root) = meshgate_root(&app) else {
        return show_error(&app, "The MeshGate files were not found next to the app (set MESHGATE_ROOT).");
    };
    let path = user_path();
    let Some(python) = find_python(&path) else {
        return show_error(&app, "Python 3.9 or newer was not found.");
    };
    let library = app
        .path()
        .document_dir()
        .map(|d| d.join("MeshGate Assets")) // not "MeshGate": case-insensitive disks would hit a clone named meshgate
        .unwrap_or_else(|_| root.join("out").join("gen"));
    let tok = token();
    let mut cmd = Command::new(&python[0]);
    cmd.args(&python[1..])
        .arg(root.join("meshgate.py"))
        .args(["studio", "--port", "0", "--no-browser", "--library"])
        .arg(&library)
        .current_dir(&root)
        .env("PATH", &path)
        .env("MESHGATE_STUDIO_TOKEN", &tok) // not in argv: other processes can read command lines
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1") // never write .pyc into the (signed) app bundle
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    hide_console(&mut cmd);
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => return show_error(&app, &format!("Could not start {}: {e}", python.join(" "))),
    };
    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    *app.state::<Server>().0.lock().unwrap() = Some(child);

    // Everything the server prints also goes to the app log (macOS ~/Library/Logs/dev.meshgate.studio/studio.log,
    // Windows %LOCALAPPDATA%\dev.meshgate.studio\logs\studio.log) — the first place to look when something fails.
    let log = app.path().app_log_dir().ok().and_then(|dir| {
        std::fs::create_dir_all(&dir).ok()?;
        std::fs::File::create(dir.join("studio.log")).ok()
    });
    let log = std::sync::Arc::new(Mutex::new(log));
    let write_log = {
        let log = log.clone();
        move |line: &str| {
            if let Some(f) = log.lock().unwrap().as_mut() {
                use std::io::Write;
                let _ = writeln!(f, "{line}");
            }
        }
    };
    let errors = std::sync::Arc::new(Mutex::new(String::new()));
    if let Some(err) = stderr {
        let errors = errors.clone();
        let write_log = write_log.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(err).lines().map_while(Result::ok) {
                write_log(&line);
                let mut e = errors.lock().unwrap();
                e.push_str(&line);
                e.push('\n');
                if e.len() > 8000 {
                    let cut = e.len() - 8000;
                    e.drain(..cut);
                }
            }
        });
    }
    let Some(out) = stdout else { return };
    let mut opened = false;
    for line in BufReader::new(out).lines().map_while(Result::ok) {
        write_log(&line.replace(&tok, "<token>"));
        if let Some(url) = line.strip_prefix("MESHGATE_STUDIO ") {
            if let (Ok(url), Some(w)) = (Url::parse(url.trim()), app.get_webview_window("main")) {
                if let Some(port) = url.port() {
                    *app.state::<Endpoint>().0.lock().unwrap() = Some((port, tok.clone()));
                }
                let _ = w.navigate(url);
                opened = true;
            }
        }
    }
    if !opened {
        std::thread::sleep(std::time::Duration::from_millis(200));
        let e = errors.lock().unwrap().clone();
        show_error(&app, &format!("The Studio server stopped before it was ready.\n\n{}", e.trim()));
    }
}

fn main() {
    let app = tauri::Builder::default()
        .manage(Server(Mutex::new(None)))
        .manage(Endpoint(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            std::thread::spawn(move || start_server(handle));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("MeshGate Studio: could not build the window");
    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(mut child) = handle.state::<Server>().0.lock().unwrap().take() {
                if let Some((port, token)) = handle.state::<Endpoint>().0.lock().unwrap().clone() {
                    shutdown_server(port, &token, &mut child); // cancels running jobs, so no Blender is left behind
                }
                let _ = child.kill();
            }
        }
    });
}
