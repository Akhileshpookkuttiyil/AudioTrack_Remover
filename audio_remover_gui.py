import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, MULTIPLE, ttk
import os

def get_audio_tracks(file_path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'a',
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
        messagebox.showinfo("Select Tracks", "Select the tracks you want to REMOVE from all selected files.")

def process_files():
    selected = audio_listbox.curselection()
    if not selected_files or not selected:
        messagebox.showerror("Error", "Please select video files and audio tracks to remove.")
        return

    selected_labels = [audio_listbox.get(i) for i in selected]
    remove_indexes = [index for index, label in current_tracks if label in selected_labels]

    if len(current_tracks) == len(remove_indexes):
        messagebox.showerror("Error", "You must keep at least one audio track.")
        return

    save_dir = filedialog.askdirectory(title="Select Output Folder")
    if not save_dir:
        return

    for file_path in selected_files:
        base = os.path.basename(file_path)
        name, ext = os.path.splitext(base)
        output_file = os.path.join(save_dir, f"{name}_modified.mkv")

        tracks = get_audio_tracks(file_path)
        keep_tracks = [f"0:{index}" for index, label in tracks if index not in remove_indexes]

        if not keep_tracks:
            messagebox.showwarning("Skipped", f"Skipped {base}: no tracks left to keep.")
            continue

        command = ['ffmpeg', '-y', '-i', file_path, '-map', '0:v']
        for track in keep_tracks:
            command += ['-map', track]
        command += ['-c', 'copy', output_file]

        print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            messagebox.showerror("FFmpeg Error", f"Error processing {base}:\n\n{result.stderr}")
            return

    messagebox.showinfo("Success", f"All files processed successfully!\nSaved in:\n{save_dir}")

# GUI setup
root = tk.Tk()
root.title("🎧 Audio Track Remover Tool")
root.geometry("550x470")  # Slightly taller to fit creator label
root.configure(bg="#1e1e1e")

style = ttk.Style()
style.theme_use("default")
style.configure("TButton", background="#007acc", foreground="white",
                font=("Segoe UI", 10, "bold"), padding=6)
style.configure("TLabel", background="#1e1e1e", foreground="white",
                font=("Segoe UI", 12))
style.configure("TListbox", background="#2d2d2d", foreground="white",
                font=("Segoe UI", 10))

# Title
title_label = ttk.Label(root, text="🎧 Batch Audio Track Remover", font=("Segoe UI", 16, "bold"))
title_label.pack(pady=(15, 0))

# Creator label
creator_label = ttk.Label(root, text="Created by Akhilesh", font=("Segoe UI", 10), foreground="#cccccc", background="#1e1e1e")
creator_label.pack(pady=(0, 15))

# File Selection Button
ttk.Button(root, text="Select Video Files", command=select_files).pack(pady=10)

# Listbox with Scrollbar
frame = tk.Frame(root, bg="#1e1e1e")
frame.pack(pady=5)
scrollbar = tk.Scrollbar(frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

audio_listbox = Listbox(frame, selectmode=MULTIPLE, width=60, height=12,
                        bg="#2d2d2d", fg="white", selectbackground="#444",
                        font=("Segoe UI", 10), yscrollcommand=scrollbar.set)
audio_listbox.pack(side=tk.LEFT)
scrollbar.config(command=audio_listbox.yview)

# Process Button
ttk.Button(root, text="Remove Selected Tracks from All Files", command=process_files).pack(pady=15)

# Globals
selected_files = []
current_tracks = []

root.mainloop()
