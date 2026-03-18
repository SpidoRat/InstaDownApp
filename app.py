"""
Instagram Image Downloader
--------------------------
A GUI-based tool to download image posts from public or followed Instagram profiles.
Uses instaloader for post fetching and tkinter for the user interface.

Dependencies:
    pip install instaloader
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import instaloader


# ─────────────────────────────────────────────
# Core Download Logic
# ─────────────────────────────────────────────

def download_posts(loader: instaloader.Instaloader, profile: instaloader.Profile, max_posts: int, progress_callback=None) -> int:
    """
    Downloads up to `max_posts` image-only posts from the given Instagram profile.

    Skips:
        - Videos (post.is_video)
        - Carousels/Sidecars (GraphSidecar) that may include videos

    Args:
        loader:            Authenticated (or anonymous) Instaloader instance.
        profile:           Target Instagram Profile object.
        max_posts:         Maximum number of image posts to download.
        progress_callback: Optional callable(current, total) to update UI progress.

    Returns:
        Number of posts actually downloaded.
    """
    os.makedirs(profile.username, exist_ok=True)
    downloaded_count = 0

    for post in profile.get_posts():
        if downloaded_count >= max_posts:
            break

        # Skip non-image content to stay image-only
        if post.is_video or post.typename == "GraphSidecar":
            continue

        loader.download_post(post, target=profile.username)
        downloaded_count += 1

        # Notify UI of progress if a callback is provided
        if progress_callback:
            progress_callback(downloaded_count, max_posts)

    return downloaded_count


def remove_unwanted_files(folder_path: str) -> None:
    """
    Cleans up metadata and archive files left by instaloader after downloading.

    Removes files with extensions: .txt, .zip, .json.xz

    Args:
        folder_path: Path to the profile's download folder.
    """
    unwanted_extensions = [".txt", ".zip", ".json.xz"]

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if not os.path.isfile(file_path):
            continue

        if any(filename.endswith(ext) for ext in unwanted_extensions):
            try:
                os.remove(file_path)
                print(f"[Cleanup] Removed: {file_path}")
            except OSError as e:
                # Log but don't abort — cleanup is non-critical
                print(f"[Cleanup] Could not remove {file_path}: {e}")


# ─────────────────────────────────────────────
# Login Helper
# ─────────────────────────────────────────────

def attempt_login(loader: instaloader.Instaloader, username: str, password: str) -> bool:
    """
    Attempts to log in to Instagram using the provided credentials.

    Args:
        loader:   Instaloader instance to authenticate.
        username: Instagram username.
        password: Instagram password.

    Returns:
        True if login succeeded, False otherwise (shows error dialog on failure).
    """
    if not username or not password:
        messagebox.showerror("Login Error", "Username and password cannot be empty.")
        return False

    try:
        loader.login(username, password)
        print(f"[Auth] Login successful for: {username}")
        return True

    except instaloader.exceptions.BadCredentialsException:
        messagebox.showerror("Login Error", "Incorrect Instagram username or password.")
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        messagebox.showerror("Login Error", "Two-factor authentication is enabled.\nPlease disable 2FA or use a session login.")
    except instaloader.exceptions.InvalidArgumentException:
        messagebox.showerror("Login Error", "Invalid argument provided during login.")
    except instaloader.exceptions.ConnectionException:
        messagebox.showerror("Network Error", "Could not connect to Instagram. Check your internet connection.")
    except Exception as e:
        messagebox.showerror("Unexpected Error", f"Login failed:\n{e}")

    return False


# ─────────────────────────────────────────────
# GUI Callbacks
# ─────────────────────────────────────────────

def run_download() -> None:
    """
    Entry point triggered by the Download button.

    Validates all input fields, optionally logs in, then spawns a background
    thread to perform the download — keeping the UI responsive throughout.
    """
    target_profile = profile_entry.get().strip()
    max_posts_str  = max_posts_entry.get().strip()
    login_choice   = login_var.get()

    # ── Input Validation ──────────────────────
    if not target_profile:
        messagebox.showwarning("Input Required", "Please enter an Instagram profile name.")
        return

    if not max_posts_str.isdigit() or int(max_posts_str) <= 0:
        messagebox.showwarning("Invalid Input", "Max posts must be a positive integer.")
        return

    max_posts = int(max_posts_str)

    # ── Setup Instaloader ─────────────────────
    loader = instaloader.Instaloader()

    if login_choice == "yes":
        username = username_entry.get().strip()
        password = password_entry.get().strip()
        if not attempt_login(loader, username, password):
            return  # Abort if login failed

    # ── Lock UI during download ───────────────
    set_ui_state(disabled=True)
    status_label.config(text="Starting download…")
    progress_bar["value"] = 0

    # ── Run download in background thread ─────
    thread = threading.Thread(
        target=_download_worker,
        args=(loader, target_profile, max_posts),
        daemon=True
    )
    thread.start()


def _download_worker(loader: instaloader.Instaloader, target_profile: str, max_posts: int) -> None:
    """
    Background worker that performs the actual download.
    Calls back to the main thread to update UI via `app.after()`.

    Args:
        loader:         Authenticated (or anonymous) Instaloader instance.
        target_profile: Username of the profile to download from.
        max_posts:      Maximum number of image posts to download.
    """
    def update_progress(current: int, total: int) -> None:
        """Thread-safe UI progress update."""
        percent = int((current / total) * 100)
        app.after(0, lambda: progress_bar.config(value=percent))
        app.after(0, lambda: status_label.config(text=f"Downloaded {current} / {total} posts…"))

    try:
        profile = instaloader.Profile.from_username(loader.context, target_profile)
        downloaded = download_posts(loader, profile, max_posts, progress_callback=update_progress)
        remove_unwanted_files(profile.username)

        # ── Success ───────────────────────────
        app.after(0, lambda: _on_download_complete(target_profile, downloaded))

    except instaloader.exceptions.ProfileNotExistsException:
        app.after(0, lambda: messagebox.showerror(
            "Profile Not Found", f"No Instagram profile found for '{target_profile}'."
        ))
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        app.after(0, lambda: messagebox.showerror(
            "Private Profile", f"'{target_profile}' is private. Log in and follow this account first."
        ))
    except instaloader.exceptions.LoginRequiredException:
        app.after(0, lambda: messagebox.showerror(
            "Login Required", "This profile requires you to be logged in to download posts."
        ))
    except instaloader.exceptions.ConnectionException:
        app.after(0, lambda: messagebox.showerror(
            "Network Error", "Lost connection to Instagram. Please check your internet and retry."
        ))
    except ValueError:
        app.after(0, lambda: messagebox.showerror(
            "Input Error", "Invalid value encountered. Please verify your inputs."
        ))
    except Exception as e:
        # Catch-all for unforeseen errors — surfaces the message without crashing
        app.after(0, lambda: messagebox.showerror("Unexpected Error", str(e)))

    finally:
        # Always re-enable UI and reset status, regardless of outcome
        app.after(0, lambda: set_ui_state(disabled=False))
        app.after(0, lambda: status_label.config(text="Ready"))


def _on_download_complete(profile_name: str, count: int) -> None:
    """
    Called on the main thread after a successful download.

    Args:
        profile_name: The downloaded profile's username.
        count:        Number of posts actually saved.
    """
    progress_bar["value"] = 100
    messagebox.showinfo(
        "Download Complete",
        f"Successfully downloaded {count} image post(s) from @{profile_name}.\n"
        f"Saved to folder: ./{profile_name}/"
    )


def clear_fields() -> None:
    """
    Resets all input fields and UI state back to defaults.
    Called by the Clear button.
    """
    profile_entry.delete(0, tk.END)
    max_posts_entry.delete(0, tk.END)
    username_entry.delete(0, tk.END)
    password_entry.delete(0, tk.END)
    login_var.set("no")
    progress_bar["value"] = 0
    status_label.config(text="Ready")
    toggle_credentials()  # Hide credential fields


def set_ui_state(disabled: bool) -> None:
    """
    Enables or disables interactive widgets during a download to prevent re-entry.

    Args:
        disabled: If True, disables all inputs and buttons; re-enables if False.
    """
    state = tk.DISABLED if disabled else tk.NORMAL
    for widget in [
        profile_entry, max_posts_entry,
        username_entry, password_entry,
        download_button, clear_button,
        login_yes_radio, login_no_radio,
    ]:
        widget.config(state=state)


def toggle_credentials(*_) -> None:
    """
    Shows or hides the username/password fields based on the login radio selection.
    Bound to changes on `login_var`.
    """
    if login_var.get() == "yes":
        credentials_frame.grid()
    else:
        credentials_frame.grid_remove()


# ─────────────────────────────────────────────
# GUI Layout
# ─────────────────────────────────────────────

app = tk.Tk()
app.title("Instagram Image Downloader")
app.resizable(False, False)
app.configure(padx=16, pady=16)

# ── Profile & Post Count ──────────────────────
tk.Label(app, text="Instagram Profile:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
profile_entry = tk.Entry(app, width=30)
profile_entry.grid(row=0, column=1, columnspan=2, sticky="w", pady=4)

tk.Label(app, text="Max Posts to Download:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
max_posts_entry = tk.Entry(app, width=10)
max_posts_entry.grid(row=1, column=1, sticky="w", pady=4)

# ── Login Radio Buttons ───────────────────────
tk.Label(app, text="Login Required?").grid(row=2, column=0, sticky="e", padx=6, pady=4)
login_var = tk.StringVar(value="no")
login_var.trace_add("write", toggle_credentials)  # Dynamically show/hide credentials

login_yes_radio = tk.Radiobutton(app, text="Yes", variable=login_var, value="yes")
login_yes_radio.grid(row=2, column=1, sticky="w")

login_no_radio = tk.Radiobutton(app, text="No", variable=login_var, value="no")
login_no_radio.grid(row=2, column=2, sticky="w")

# ── Credentials Frame (hidden by default) ─────
credentials_frame = tk.Frame(app)
credentials_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
credentials_frame.grid_remove()  # Hidden until "Yes" is selected

tk.Label(credentials_frame, text="Username:").grid(row=0, column=0, sticky="e", padx=6, pady=2)
username_entry = tk.Entry(credentials_frame, width=28)
username_entry.grid(row=0, column=1, sticky="w", pady=2)

tk.Label(credentials_frame, text="Password:").grid(row=1, column=0, sticky="e", padx=6, pady=2)
password_entry = tk.Entry(credentials_frame, width=28, show="*")
password_entry.grid(row=1, column=1, sticky="w", pady=2)

# ── Action Buttons ────────────────────────────
button_frame = tk.Frame(app)
button_frame.grid(row=4, column=0, columnspan=3, pady=10)

download_button = tk.Button(button_frame, text="⬇ Download", width=14, command=run_download)
download_button.pack(side=tk.LEFT, padx=6)

clear_button = tk.Button(button_frame, text="✕ Clear", width=10, command=clear_fields)
clear_button.pack(side=tk.LEFT, padx=6)

# ── Progress Bar & Status ─────────────────────
progress_bar = ttk.Progressbar(app, orient="horizontal", length=340, mode="determinate")
progress_bar.grid(row=5, column=0, columnspan=3, pady=(4, 2))

status_label = tk.Label(app, text="Ready", fg="gray", font=("TkDefaultFont", 9))
status_label.grid(row=6, column=0, columnspan=3)

# ─────────────────────────────────────────────
# Run Application
# ─────────────────────────────────────────────
app.mainloop()
