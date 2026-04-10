import os
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import MULTIPLE, Listbox, filedialog, messagebox, ttk


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


def call_on_ui_thread(callback, *args, wait=False):
    if threading.current_thread() is threading.main_thread():
        return callback(*args)

    completed = threading.Event()

    def runner():
        try:
            callback(*args)
        finally:
            completed.set()

    root.after(0, runner)

    if wait:
        completed.wait()


def set_status(message):
    call_on_ui_thread(status_var.set, message)


def set_progress(current, total, message):
    def update_progress():
        progress_bar.configure(mode="determinate", maximum=max(total, 1))
        progress_bar["value"] = current
        progress_text_var.set(message)

    call_on_ui_thread(update_progress)


def reset_progress(message="No processing in progress"):
    set_progress(0, 1, message)


def show_message(kind, title, message, wait=False):
    callback = getattr(messagebox, kind)
    call_on_ui_thread(callback, title, message, wait=wait)


def update_process_button_state(event=None):
    tools_available = bool(FFPROBE_PATH and FFMPEG_PATH)
    has_files = bool(selected_files)
    has_audio_selection = bool(audio_listbox.curselection())
    process_state = "normal" if tools_available and has_files and has_audio_selection and not is_processing else "disabled"
    clear_state = "normal" if audio_listbox.size() > 0 and not is_processing else "disabled"

    process_button.configure(state=process_state)
    clear_button.configure(state=clear_state)


def set_processing_state(processing):
    global is_processing
    is_processing = processing

    widget_state = "disabled" if processing else "normal"
    listbox_state = tk.DISABLED if processing else tk.NORMAL

    browse_button.configure(state=widget_state)
    clear_button.configure(state=widget_state)
    audio_listbox.configure(state=listbox_state)
    update_process_button_state()


def clear_selection():
    audio_listbox.selection_clear(0, tk.END)
    reset_progress()
    set_status("Ready")
    update_process_button_state()


def tools_ready():
    missing_tools = []
    if not FFPROBE_PATH:
        missing_tools.append("ffprobe")
    if not FFMPEG_PATH:
        missing_tools.append("ffmpeg")

    if missing_tools:
        set_status(f"Missing dependency: {', '.join(missing_tools)}")
        show_message(
            "showerror",
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
    if not tools_ready() or is_processing:
        return

    file_paths = filedialog.askopenfilenames(title="Select Video Files", filetypes=[("Video Files", "*.mkv *.mp4 *.mov *.avi")])
    if file_paths:
        audio_listbox.delete(0, tk.END)
        audio_listbox.selection_clear(0, tk.END)
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

        set_status(f"Ready - {len(tracks)} audio track(s) loaded")
        reset_progress(f"{len(file_paths)} file(s) ready for processing")
        update_process_button_state()
        show_message("showinfo", "Select Tracks", "Select the tracks you want to REMOVE from all selected files.")


def process_files_worker(save_dir, remove_indexes, files_to_process):
    total_files = len(files_to_process)

    # Existing media-processing logic is preserved; it now runs in a worker thread.
    for position, file_path in enumerate(files_to_process, start=1):
        set_progress(position - 1, total_files, f"Processing file {position} of {total_files}")
        set_status("Processing video...")

        base = os.path.basename(file_path)
        name, ext = os.path.splitext(base)
        output_file = os.path.join(save_dir, f"{name}_modified.mkv")

        tracks = get_audio_tracks(file_path)
        keep_tracks = [f"0:{index}" for index, label in tracks if index not in remove_indexes]

        if not keep_tracks:
            set_status(f"Skipped {base} - no tracks left to keep")
            show_message("showwarning", "Skipped", f"Skipped {base}: no tracks left to keep.", wait=True)
            continue

        command = [FFMPEG_PATH, '-y', '-i', file_path, '-map', '0:v']
        for track in keep_tracks:
            command += ['-map', track]
        command += ['-map', '0:s?']

        command += ['-c', 'copy', output_file]

        print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            def finish_error():
                set_processing_state(False)
                set_status("Error occurred")
                progress_text_var.set(f"Processing stopped while working on {base}")
                messagebox.showerror("FFmpeg Error", f"Error processing {base}:\n\n{result.stderr}")

            call_on_ui_thread(finish_error)
            return

        set_progress(position, total_files, f"Processed {position} of {total_files}")

    def finish_success():
        set_processing_state(False)
        set_progress(total_files, total_files, f"Processed {total_files} of {total_files}")
        set_status("Completed successfully")
        messagebox.showinfo("Success", f"All files processed successfully!\nSaved in:\n{save_dir}")

    call_on_ui_thread(finish_success)


def process_files():
    if not tools_ready() or is_processing:
        return

    selected = audio_listbox.curselection()
    if not selected_files or not selected:
        set_status("Error occurred")
        show_message("showerror", "Error", "Please select video files and audio tracks to remove.")
        return

    selected_labels = [audio_listbox.get(i) for i in selected]
    remove_indexes = [index for index, label in current_tracks if label in selected_labels]

    if len(current_tracks) == len(remove_indexes):
        set_status("Error occurred")
        show_message("showerror", "Error", "You must keep at least one audio track.")
        return

    save_dir = filedialog.askdirectory(title="Select Output Folder")
    if not save_dir:
        set_status("Ready")
        return

    set_processing_state(True)
    set_status("Processing video...")
    set_progress(0, len(selected_files), f"Processing 0 of {len(selected_files)}")

    files_to_process = list(selected_files)
    worker = threading.Thread(
        target=process_files_worker,
        args=(save_dir, remove_indexes, files_to_process),
        daemon=True
    )
    worker.start()


def center_window(window, width=760, height=560):
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


def update_scroll_region(event=None):
    app_canvas.configure(scrollregion=app_canvas.bbox("all"))


def resize_scrollable_frame(event):
    app_canvas.itemconfigure(scroll_window, width=event.width)


def on_mousewheel(event):
    app_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# GUI setup
FFPROBE_PATH = resolve_tool("ffprobe")
FFMPEG_PATH = resolve_tool("ffmpeg")

root = tk.Tk()
root.title("Audio Track Remover")
root.minsize(650, 500)
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
    "TRadiobutton",
    background="#ffffff",
    foreground="#1f1f1f",
    font=("Segoe UI", 9)
)
style.map(
    "TRadiobutton",
    background=[("active", "#ffffff")]
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
    "Neutral.Horizontal.TProgressbar",
    troughcolor="#eef0f3",
    background="#c4cad3",
    bordercolor="#d1d5db",
    lightcolor="#c4cad3",
    darkcolor="#c4cad3"
)
style.configure(
    "Vertical.TScrollbar",
    background="#e5e7eb",
    troughcolor="#f3f4f6",
    bordercolor="#e5e7eb",
    arrowcolor="#6b7280"
)

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

scroll_host = ttk.Frame(root, style="App.TFrame")
scroll_host.grid(row=0, column=0, sticky="nsew")
scroll_host.grid_rowconfigure(0, weight=1)
scroll_host.grid_columnconfigure(0, weight=1)

app_canvas = tk.Canvas(scroll_host, bg="#f5f5f5", highlightthickness=0, bd=0)
app_canvas.grid(row=0, column=0, sticky="nsew")

app_scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=app_canvas.yview)
app_scrollbar.grid(row=0, column=1, sticky="ns")
app_canvas.configure(yscrollcommand=app_scrollbar.set)

# Scrollable layout implementation: the full app content lives inside this frame on a canvas.
main_frame = ttk.Frame(app_canvas, style="App.TFrame", padding=16)
scroll_window = app_canvas.create_window((0, 0), window=main_frame, anchor="nw")
main_frame.bind("<Configure>", update_scroll_region)
app_canvas.bind("<Configure>", resize_scrollable_frame)
root.bind_all("<MouseWheel>", on_mousewheel)

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

browse_button = ttk.Button(file_frame, text="Browse", command=select_files, width=12)
browse_button.grid(row=1, column=1, sticky="e")

tracks_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=14)
tracks_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
tracks_frame.grid_columnconfigure(0, weight=1)

ttk.Label(tracks_frame, text="Available Audio Tracks", style="Section.TLabel").grid(
    row=0, column=0, sticky="w"
)

ttk.Label(
    tracks_frame,
    text="Select one or more tracks to remove from every chosen video.",
    style="Body.TLabel"
).grid(row=1, column=0, sticky="w", pady=(4, 10))

audio_listbox_container = tk.Frame(tracks_frame, bg="#d1d5db", bd=0, highlightthickness=0)
audio_listbox_container.grid(row=2, column=0, sticky="ew")
audio_listbox_container.grid_rowconfigure(0, weight=1)
audio_listbox_container.grid_columnconfigure(0, weight=1)

audio_listbox = Listbox(
    audio_listbox_container,
    selectmode=MULTIPLE,
    width=60,
    height=7,
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

audio_scrollbar = ttk.Scrollbar(audio_listbox_container, orient="vertical", command=audio_listbox.yview)
audio_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 1), pady=1)
audio_listbox.config(yscrollcommand=audio_scrollbar.set)
audio_listbox.bind("<<ListboxSelect>>", update_process_button_state)

action_frame = ttk.Frame(main_frame, style="App.TFrame")
action_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
action_frame.grid_columnconfigure(0, weight=1)

clear_button = ttk.Button(action_frame, text="Clear Selection", command=clear_selection, width=16)
clear_button.grid(row=0, column=0, sticky="w")

process_button = ttk.Button(
    action_frame,
    text="Process Video",
    command=process_files,
    style="Primary.TButton",
    width=16
)
process_button.grid(row=0, column=1, sticky="e")

feedback_frame = ttk.Frame(main_frame, style="Card.TFrame", padding=14)
feedback_frame.grid(row=4, column=0, sticky="ew")
feedback_frame.grid_columnconfigure(0, weight=1)

ttk.Label(feedback_frame, text="Progress", style="Section.TLabel").grid(
    row=0, column=0, sticky="w"
)

progress_bar = ttk.Progressbar(
    feedback_frame,
    orient="horizontal",
    mode="determinate",
    style="Neutral.Horizontal.TProgressbar"
)
progress_bar.grid(row=1, column=0, sticky="ew", pady=(10, 6))

progress_text_var = tk.StringVar(value="No processing in progress")
progress_label = ttk.Label(feedback_frame, textvariable=progress_text_var, style="Body.TLabel")
progress_label.grid(row=2, column=0, sticky="w")

initial_status = "Ready" if FFPROBE_PATH and FFMPEG_PATH else "Missing dependency: ffmpeg / ffprobe"
status_var = tk.StringVar(value=initial_status)
status_label = ttk.Label(feedback_frame, textvariable=status_var, style="Status.TLabel", anchor="w")
status_label.grid(row=3, column=0, sticky="ew", pady=(10, 0))

# Globals
selected_files = []
current_tracks = []
is_processing = False

reset_progress()
update_process_button_state()

root.mainloop()
