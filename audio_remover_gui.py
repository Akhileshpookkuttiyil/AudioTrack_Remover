import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, MULTIPLE, ttk
import os
import shutil


def resolve_tool(tool_name):
    candidates = [
        shutil.which(tool_name),
        shutil.which(f"{tool_name}.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), tool_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{tool_name}.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg", "bin", f"{tool_name}.exe"),
    ]

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return None


def tools_ready():
    missing_tools = []
    if not FFPROBE_PATH:
        missing_tools.append("ffprobe")
    if not FFMPEG_PATH:
        missing_tools.append("ffmpeg")

    if missing_tools:
        status_var.set(f"Missing dependency: {', '.join(missing_tools)}")
        messagebox.showerror(
            "Missing FFmpeg Tools",
            "Required tool(s) not found: "
            f"{', '.join(missing_tools)}.\n\n"
            "Install FFmpeg and ensure both ffmpeg and ffprobe are available in PATH,\n"
            "or place ffmpeg.exe and ffprobe.exe in the same folder as this script."
        )
        return False

    return True


def get_audio_tracks(file_path):
    result = subprocess.run(
        [FFPROBE_PATH, '-v', 'error', '-select_streams', 'a',
         '-show_entries', 'stream=index:stream_tags=language,title',
         '-of', 'default=noprint_wrappers=1', file_path],
        capture_output=True, text=True
    )

    tracks = []
    index = None
    language = ""
    title = ""
    for line in result.stdout.splitlines():
        if line.startswith('index='):
            if index is not None:
                label = f"Track {index}: {language or 'unknown'} - {title or 'no title'}"
                tracks.append((index, label))
            index = int(line.split('=')[1])
            language = ""
            title = ""
        elif line.startswith('TAG:language='):
            language = line.split('=')[1]
        elif line.startswith('TAG:title='):
            title = line.split('=')[1]

    if index is not None:
        label = f"Track {index}: {language or 'unknown'} - {title or 'no title'}"
        tracks.append((index, label))

    return tracks


def select_files():
    if not tools_ready():
        return

    file_paths = filedialog.askopenfilenames(title="Select Video Files", filetypes=[("Video Files", "*.mkv *.mp4 *.mov *.avi")])
    if file_paths:
        audio_listbox.delete(0, tk.END)
        global selected_files
        selected_files = file_paths
        # Use first file for track selection
        tracks = get_audio_tracks(file_paths[0])
        global current_tracks
        current_tracks = tracks
        for _, label in tracks:
            audio_listbox.insert(tk.END, label)

        if len(file_paths) == 1:
            file_path_var.set(file_paths[0])
        else:
            file_path_var.set(f"{file_paths[0]} (+{len(file_paths) - 1} more)")

        status_var.set(f"Ready - {len(tracks)} audio track(s) loaded")
        messagebox.showinfo("Select Tracks", "Select the tracks you want to REMOVE from all selected files.")


def process_files():
    if not tools_ready():
        return

    selected = audio_listbox.curselection()
    if not selected_files or not selected:
        status_var.set("Error - select files and audio tracks")
        messagebox.showerror("Error", "Please select video files and audio tracks to remove.")
        return

    selected_labels = [audio_listbox.get(i) for i in selected]
    remove_indexes = [index for index, label in current_tracks if label in selected_labels]

    if len(current_tracks) == len(remove_indexes):
        status_var.set("Error - at least one track must remain")
        messagebox.showerror("Error", "You must keep at least one audio track.")
        return

    save_dir = filedialog.askdirectory(title="Select Output Folder")
    if not save_dir:
        status_var.set("Ready")
        return

    status_var.set("Processing files...")
    root.update_idletasks()

    for file_path in selected_files:
        base = os.path.basename(file_path)
        name, ext = os.path.splitext(base)
        output_file = os.path.join(save_dir, f"{name}_modified.mkv")

        tracks = get_audio_tracks(file_path)
        keep_tracks = [f"0:{index}" for index, label in tracks if index not in remove_indexes]

        if not keep_tracks:
            status_var.set(f"Skipped {base} - no tracks left to keep")
            messagebox.showwarning("Skipped", f"Skipped {base}: no tracks left to keep.")
            continue

        command = [FFMPEG_PATH, '-y', '-i', file_path, '-map', '0:v']
        for track in keep_tracks:
            command += ['-map', track]
        command += ['-c', 'copy', output_file]

        print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            status_var.set(f"Error processing {base}")
            messagebox.showerror("FFmpeg Error", f"Error processing {base}:\n\n{result.stderr}")
            return

    status_var.set("Done - files processed successfully")
    messagebox.showinfo("Success", f"All files processed successfully!\nSaved in:\n{save_dir}")


def center_window(window, width=760, height=520):
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


# GUI setup
FFPROBE_PATH = resolve_tool("ffprobe")
FFMPEG_PATH = resolve_tool("ffmpeg")

root = tk.Tk()
root.title("Audio Track Remover")
root.minsize(600, 400)
root.configure(bg="#f5f5f5")
center_window(root)

style = ttk.Style()
style.theme_use("clam")

style.configure("App.TFrame", background="#f5f5f5")
style.configure(
    "Card.TFrame",
    background="#ffffff",
    relief="solid",
    borderwidth=1
)
style.configure(
    "Title.TLabel",
    background="#f5f5f5",
    foreground="#1f1f1f",
    font=("Segoe UI", 16, "bold")
)
style.configure(
    "Subtitle.TLabel",
    background="#f5f5f5",
    foreground="#6b7280",
    font=("Segoe UI", 9)
)
style.configure(
    "Section.TLabel",
    background="#ffffff",
    foreground="#1f1f1f",
    font=("Segoe UI", 10, "bold")
)
style.configure(
    "Body.TLabel",
    background="#ffffff",
    foreground="#4b5563",
    font=("Segoe UI", 9)
)
style.configure(
    "Status.TLabel",
    background="#ffffff",
    foreground="#4b5563",
    font=("Segoe UI", 9),
    padding=(10, 8)
)
style.configure(
    "TEntry",
    fieldbackground="#ffffff",
    foreground="#1f1f1f",
    bordercolor="#d1d5db",
    lightcolor="#d1d5db",
    darkcolor="#d1d5db",
    padding=8
)
style.configure(
    "TButton",
    font=("Segoe UI", 10),
    padding=(14, 8),
    background="#ffffff",
    foreground="#1f1f1f",
    bordercolor="#d1d5db",
    lightcolor="#d1d5db",
    darkcolor="#d1d5db"
)
style.map(
    "TButton",
    background=[("active", "#f0f0f0"), ("pressed", "#e5e7eb")]
)
style.configure(
    "Primary.TButton",
    font=("Segoe UI", 10, "bold"),
    background="#e5e7eb",
    foreground="#111827",
    bordercolor="#c7ccd4",
    lightcolor="#c7ccd4",
    darkcolor="#c7ccd4"
)
style.map(
    "Primary.TButton",
    background=[("active", "#d9dde3"), ("pressed", "#cfd4db")]
)
style.configure(
    "Vertical.TScrollbar",
    background="#e5e7eb",
    troughcolor="#f3f4f6",
    bordercolor="#e5e7eb",
    arrowcolor="#6b7280"
)

main_frame = ttk.Frame(root, style="App.TFrame", padding=16)
main_frame.grid(row=0, column=0, sticky="nsew")
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

main_frame.grid_rowconfigure(2, weight=1)
main_frame.grid_columnconfigure(0, weight=1)

header_frame = ttk.Frame(main_frame, style="App.TFrame")
header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
header_frame.grid_columnconfigure(0, weight=1)

title_label = ttk.Label(header_frame, text="Audio Track Remover", style="Title.TLabel")
title_label.grid(row=0, column=0, sticky="w")

creator_label = ttk.Label(header_frame, text="Created by Akhilesh", style="Subtitle.TLabel")
creator_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

file_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=14)
file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
file_frame.grid_columnconfigure(0, weight=1)

ttk.Label(file_frame, text="Select Video File", style="Section.TLabel").grid(
    row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
)

file_path_var = tk.StringVar(value="No files selected")
file_entry = ttk.Entry(file_frame, textvariable=file_path_var, state="readonly")
file_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))

browse_button = ttk.Button(file_frame, text="Browse", command=select_files)
browse_button.grid(row=1, column=1, sticky="e")

tracks_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=14)
tracks_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
tracks_frame.grid_rowconfigure(2, weight=1)
tracks_frame.grid_columnconfigure(0, weight=1)

ttk.Label(tracks_frame, text="Available Audio Tracks", style="Section.TLabel").grid(
    row=0, column=0, sticky="w"
)

ttk.Label(
    tracks_frame,
    text="Select one or more tracks to remove from every chosen video.",
    style="Body.TLabel"
).grid(row=1, column=0, sticky="w", pady=(4, 10))

listbox_container = tk.Frame(tracks_frame, bg="#d1d5db", bd=0, highlightthickness=0)
listbox_container.grid(row=2, column=0, sticky="nsew")
listbox_container.grid_rowconfigure(0, weight=1)
listbox_container.grid_columnconfigure(0, weight=1)

audio_listbox = Listbox(
    listbox_container,
    selectmode=MULTIPLE,
    width=60,
    height=12,
    bg="#ffffff",
    fg="#1f1f1f",
    selectbackground="#dbe4f0",
    selectforeground="#111827",
    highlightthickness=0,
    relief="flat",
    bd=0,
    font=("Segoe UI", 10)
)
audio_listbox.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)

scrollbar = ttk.Scrollbar(listbox_container, orient="vertical", command=audio_listbox.yview)
scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
audio_listbox.config(yscrollcommand=scrollbar.set)

action_frame = ttk.Frame(main_frame, style="App.TFrame")
action_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
action_frame.grid_columnconfigure(0, weight=1)

process_button = ttk.Button(
    action_frame,
    text="Process Video",
    command=process_files,
    style="Primary.TButton"
)
process_button.grid(row=0, column=1, sticky="e")

initial_status = "Ready" if FFPROBE_PATH and FFMPEG_PATH else "Missing dependency: ffmpeg / ffprobe"
status_var = tk.StringVar(value=initial_status)
status_frame = ttk.Frame(main_frame, style="Card.TFrame")
status_frame.grid(row=4, column=0, sticky="ew")
status_frame.grid_columnconfigure(0, weight=1)

status_label = ttk.Label(status_frame, textvariable=status_var, style="Status.TLabel", anchor="w")
status_label.grid(row=0, column=0, sticky="ew")

# Globals
selected_files = []
current_tracks = []

root.mainloop()
