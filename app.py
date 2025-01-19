import instaloader
import getpass
import os
import tkinter as tk
from tkinter import messagebox

def get_credentials():
    """
    Retrieves the user's Instagram login credentials from the input fields.
    """
    username = username_entry.get().strip()
    password = password_entry.get().strip()
    return username, password

def download_posts(loader, profile, max_posts):
    """
    Downloads a specified number of image posts from the given Instagram profile.
    """
    os.makedirs(profile.username, exist_ok=True)
    
    downloaded_count = 0
    
    for post in profile.get_posts():
        if downloaded_count >= max_posts:
            break
        if post.is_video or post.typename == 'GraphSidecar':
            continue  # Skip videos and reels
        
        loader.download_post(post, target=profile.username)
        downloaded_count += 1

def remove_unwanted_files(folder_path):
    """
    Removes unwanted files from the specified folder.
    """
    unwanted_extensions = ['.txt', '.zip', '.json.xz']

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path) and any(filename.endswith(ext) for ext in unwanted_extensions):
            try:
                os.remove(file_path)
                print(f"Removed: {file_path}")
            except Exception as e:
                print(f"Error removing {file_path}: {e}")

def run_download():
    """
    Executes the download process based on user input.
    """
    loader = instaloader.Instaloader()
    target_profile = profile_entry.get().strip()
    max_posts = int(max_posts_entry.get().strip())

    login_choice = login_var.get()
    if login_choice == 'yes':
        username, password = get_credentials()
        try:
            loader.login(username, password)
            print("Login successful!")
        except instaloader.exceptions.BadCredentialsException:
            messagebox.showerror("Error", "Invalid Instagram username or password.")
            return
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            messagebox.showerror("Error", "Two-factor authentication is required.")
            return
        except instaloader.exceptions.InvalidArgumentException:
            messagebox.showerror("Error", "Invalid argument provided.")
            return

    try:
        profile = instaloader.Profile.from_username(loader.context, target_profile)
        download_posts(loader, profile, max_posts)
        remove_unwanted_files(profile.username)
        messagebox.showinfo("Success", f"Downloaded {max_posts} image posts from {target_profile}.")
    except instaloader.exceptions.ProfileNotExistsException:
        messagebox.showerror("Error", f"The profile '{target_profile}' does not exist.")
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        messagebox.showerror("Error", f"The profile '{target_profile}' is private and requires following.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def clear_fields():
    """
    Clears the input fields for reuse.
    """
    profile_entry.delete(0, tk.END)
    max_posts_entry.delete(0, tk.END)
    username_entry.delete(0, tk.END)
    password_entry.delete(0, tk.END)
    login_var.set('no')

# Create the main application window
app = tk.Tk()
app.title("Instagram Image Downloader")

# Create and place the input fields and labels
tk.Label(app, text="Instagram Profile:").grid(row=0, column=0)
profile_entry = tk.Entry(app)
profile_entry.grid(row=0, column=1)

tk.Label(app, text="Max Posts to Download:").grid(row=1, column=0)
max_posts_entry = tk.Entry(app)
max_posts_entry.grid(row=1, column=1)

tk.Label(app, text="Login Required? (yes/no):").grid(row=2, column=0)
login_var = tk.StringVar(value='no')
tk.Radiobutton(app, text='Yes', variable=login_var, value='yes').grid(row=2, column=1)
tk.Radiobutton(app, text='No', variable=login_var, value='no').grid(row=2, column=2)

tk.Label(app, text="Username:").grid(row=3, column=0)
username_entry = tk.Entry(app)
username_entry.grid(row=3, column=1)

tk.Label(app, text="Password:").grid(row=4, column=0)
password_entry = tk.Entry(app, show='*')
password_entry.grid(row=4, column=1)

# Create and place the buttons
download_button = tk.Button(app, text=" Download", command=run_download)
download_button.grid(row=5, column=0, columnspan=2)

clear_button = tk.Button(app, text="Clear", command=clear_fields)
clear_button.grid(row=5, column=2)

# Run the application
app.mainloop()