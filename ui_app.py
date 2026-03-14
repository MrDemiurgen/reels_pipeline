import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import build_reels as br


APP_BG = "#d9d6d1"


class CollapsibleSection(ttk.Frame):
    def __init__(self, parent, title: str, expanded: bool = False):
        super().__init__(parent)

        self.title = title
        self.expanded = tk.BooleanVar(value=expanded)

        self.header = ttk.Frame(self)
        self.header.pack(fill="x")

        self.toggle_button = ttk.Button(
            self.header,
            text=self._get_button_text(),
            command=self.toggle,
            width=28,
        )
        self.toggle_button.pack(fill="x", anchor="w")

        self.body = ttk.Frame(self)
        if expanded:
            self.body.pack(fill="x", pady=(6, 0))

    def _get_button_text(self) -> str:
        arrow = "▼" if self.expanded.get() else "▶"
        return f"{arrow} {self.title}"

    def toggle(self):
        if self.expanded.get():
            self.body.pack_forget()
            self.expanded.set(False)
        else:
            self.body.pack(fill="x", pady=(6, 0))
            self.expanded.set(True)

        self.toggle_button.config(text=self._get_button_text())


class ReelsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Reels Pipeline")
        self.root.minsize(520, 520)
        self.root.resizable(True, True)

        self.set_window_geometry(760, 520)

        self.input_dir_var = tk.StringVar(value=os.path.join("input", "reels_001"))
        self.background_var = tk.StringVar(value=os.path.join("assets", "background.png"))
        self.music_var = tk.StringVar(value=os.path.join("assets", "music.mp3"))
        self.output_var = tk.StringVar(value=os.path.join("output", "reels_001.mp4"))

        self.video_w_var = tk.StringVar(value=str(br.VIDEO_W))
        self.video_h_var = tk.StringVar(value=str(br.VIDEO_H))
        self.fps_var = tk.StringVar(value=str(br.FPS))

        self.total_duration_var = tk.StringVar(value=str(br.TOTAL_DURATION))
        self.reveal_duration_var = tk.StringVar(value=str(br.REVEAL_DURATION))

        self.card_scale_var = tk.StringVar(value=str(br.CARD_SCALE))
        self.card_radius_var = tk.StringVar(value=str(br.CARD_RADIUS))
        self.card_gap_var = tk.StringVar(value=str(br.CARD_GAP))

        self.video_codec_var = tk.StringVar(value=str(br.VIDEO_CODEC))
        self.audio_codec_var = tk.StringVar(value=str(br.AUDIO_CODEC))
        self.bitrate_var = tk.StringVar(value=str(br.BITRATE))
        self.threads_var = tk.StringVar(value=str(br.THREADS))
        self.preset_var = tk.StringVar(value=str(br.PRESET))

        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.IntVar(value=0)

        self.build_ui()

    def set_window_geometry(self, width: int, height: int):
        self.root.update_idletasks()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        taskbar_safe_margin = 80

        x = max((screen_w - width) // 2, 20)
        y = max((screen_h - height - taskbar_safe_margin) // 2, 20)

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def build_ui(self):
        self.configure_styles()

        container = ttk.Frame(self.root, style="App.TFrame")
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, highlightthickness=0, bg=APP_BG)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = ttk.Frame(self.canvas, style="App.TFrame")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        main = ttk.Frame(self.scrollable_frame, padding=14, style="App.TFrame")
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Reels Pipeline", font=("Segoe UI", 16, "bold"), style="App.TLabel").pack(anchor="w", pady=(0, 10))

        self.create_path_section(main)
        self.create_collapsible_sections(main)
        self.create_actions_section(main)

    def configure_styles(self):
        style = ttk.Style(self.root)

        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.root.configure(bg=APP_BG)

        style.configure("App.TFrame", background=APP_BG)
        style.configure("App.TLabel", background=APP_BG)
        style.configure("TLabelframe", background=APP_BG)
        style.configure("TLabelframe.Label", background=APP_BG)

        style.configure(
            "Green.Horizontal.TProgressbar",
            troughcolor="#cfcac4",
            background="#36b24a",
            lightcolor="#36b24a",
            darkcolor="#36b24a",
            bordercolor="#bdb7b0",
        )

        style.configure(
            "TCombobox",
            fieldbackground="white",
            background="white",
            foreground="black",
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "white")],
            background=[("readonly", "white")],
            foreground=[("readonly", "black")],
        )

    def on_mousewheel(self, event):
        first, last = self.canvas.yview()
        delta = int(-1 * (event.delta / 120))

        if delta < 0 and first <= 0.0:
            return

        if delta > 0 and last >= 1.0:
            return

        self.canvas.yview_scroll(delta, "units")

    def create_path_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Paths", padding=10)
        frame.pack(fill="x", pady=6)

        self.add_path_row(frame, "Input folder", self.input_dir_var, self.browse_input_folder)
        self.add_path_row(frame, "Background", self.background_var, self.browse_background_file)
        self.add_path_row(frame, "Music", self.music_var, self.browse_music_file)
        self.add_path_row(frame, "Output file", self.output_var, self.browse_output_file)

    def create_collapsible_sections(self, parent):
        self.video_section = CollapsibleSection(parent, "Video settings", expanded=False)
        self.video_section.pack(fill="x", pady=4)
        self.fill_video_section(self.video_section.body)

        self.animation_section = CollapsibleSection(parent, "Animation settings", expanded=False)
        self.animation_section.pack(fill="x", pady=4)
        self.fill_animation_section(self.animation_section.body)

        self.cards_section = CollapsibleSection(parent, "Card visual settings", expanded=False)
        self.cards_section.pack(fill="x", pady=4)
        self.fill_cards_section(self.cards_section.body)

        self.render_section = CollapsibleSection(parent, "Render settings", expanded=False)
        self.render_section.pack(fill="x", pady=4)
        self.fill_render_section(self.render_section.body)

    def fill_video_section(self, parent):
        frame = ttk.Frame(parent, padding=10, style="App.TFrame")
        frame.pack(fill="x")

        ttk.Label(frame, text="Width", style="App.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.video_w_var, width=14).grid(row=0, column=1, sticky="w", padx=(0, 16), pady=4)

        ttk.Label(frame, text="Height", style="App.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.video_h_var, width=14).grid(row=0, column=3, sticky="w", padx=(0, 16), pady=4)

        ttk.Label(frame, text="FPS", style="App.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=4)
        fps_box = ttk.Combobox(
            frame,
            textvariable=self.fps_var,
            state="readonly",
            values=["24", "25", "30", "50", "60"],
            width=12,
        )
        fps_box.grid(row=0, column=5, sticky="w", pady=4)

    def fill_animation_section(self, parent):
        frame = ttk.Frame(parent, padding=10, style="App.TFrame")
        frame.pack(fill="x")

        self.add_labeled_entry(frame, "Total duration", self.total_duration_var, 0, 0)
        self.add_labeled_entry(frame, "Reveal duration", self.reveal_duration_var, 0, 2)

    def fill_cards_section(self, parent):
        frame = ttk.Frame(parent, padding=10, style="App.TFrame")
        frame.pack(fill="x")

        self.add_labeled_entry(frame, "Card scale", self.card_scale_var, 0, 0)
        self.add_labeled_entry(frame, "Card radius", self.card_radius_var, 0, 2)
        self.add_labeled_entry(frame, "Card gap", self.card_gap_var, 0, 4)

    def fill_render_section(self, parent):
        frame = ttk.Frame(parent, padding=10, style="App.TFrame")
        frame.pack(fill="x")

        ttk.Label(frame, text="Video codec", style="App.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        codec_box = ttk.Combobox(
            frame,
            textvariable=self.video_codec_var,
            state="readonly",
            values=["libx264", "libx265"],
            width=14,
        )
        codec_box.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=4)

        ttk.Label(frame, text="Audio codec", style="App.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=4)
        audio_box = ttk.Combobox(
            frame,
            textvariable=self.audio_codec_var,
            state="readonly",
            values=["aac", "mp3"],
            width=14,
        )
        audio_box.grid(row=0, column=3, sticky="w", padx=(0, 16), pady=4)

        ttk.Label(frame, text="Bitrate", style="App.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        bitrate_box = ttk.Combobox(
            frame,
            textvariable=self.bitrate_var,
            state="readonly",
            values=["6000k", "8000k", "9000k", "12000k", "16000k"],
            width=14,
        )
        bitrate_box.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=4)

        ttk.Label(frame, text="Threads", style="App.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=4)
        threads_box = ttk.Combobox(
            frame,
            textvariable=self.threads_var,
            state="readonly",
            values=["2", "4", "6", "8"],
            width=14,
        )
        threads_box.grid(row=1, column=3, sticky="w", padx=(0, 16), pady=4)

        ttk.Label(frame, text="Preset", style="App.TLabel").grid(row=1, column=4, sticky="w", padx=(0, 8), pady=4)
        preset_box = ttk.Combobox(
            frame,
            textvariable=self.preset_var,
            state="readonly",
            values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower"],
            width=14,
        )
        preset_box.grid(row=1, column=5, sticky="w", pady=4)

    def create_actions_section(self, parent):
        frame = ttk.Frame(parent, padding=(0, 12, 0, 0), style="App.TFrame")
        frame.pack(fill="x")

        ttk.Button(frame, text="Render video", command=self.start_render).pack(side="left")
        ttk.Label(frame, textvariable=self.status_var, style="App.TLabel").pack(side="left", padx=12)

        progress_frame = ttk.Frame(parent, style="App.TFrame")
        progress_frame.pack(fill="x", pady=(10, 0))

        self.progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.progress_var,
            style="Green.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x")

    def add_path_row(self, parent, label, variable, button_command):
        row = ttk.Frame(parent, style="App.TFrame")
        row.pack(fill="x", pady=4)

        ttk.Label(row, text=label, width=12, style="App.TLabel").pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="Browse", command=button_command).pack(side="left")

    def add_labeled_entry(self, parent, label, variable, row, col):
        ttk.Label(parent, text=label, style="App.TLabel").grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable, width=14).grid(row=row, column=col + 1, sticky="w", padx=(0, 16), pady=4)

    def browse_input_folder(self):
        path = filedialog.askdirectory(title="Select input folder")
        if path:
            self.input_dir_var.set(path)
            folder_name = os.path.basename(path.rstrip("\\/"))
            self.output_var.set(os.path.join("output", f"{folder_name}.mp4"))

    def browse_background_file(self):
        path = filedialog.askopenfilename(
            title="Select background image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg"), ("All files", "*.*")],
        )
        if path:
            self.background_var.set(path)

    def browse_music_file(self):
        path = filedialog.askopenfilename(
            title="Select music file",
            filetypes=[("Audio files", "*.mp3;*.wav;*.m4a"), ("All files", "*.*")],
        )
        if path:
            self.music_var.set(path)

    def browse_output_file(self):
        path = filedialog.asksaveasfilename(
            title="Save output video as",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4")],
        )
        if path:
            self.output_var.set(path)

    def apply_settings_to_renderer(self):
        br.VIDEO_W = int(self.video_w_var.get())
        br.VIDEO_H = int(self.video_h_var.get())
        br.FPS = int(self.fps_var.get())

        br.TOTAL_DURATION = float(self.total_duration_var.get())
        br.REVEAL_DURATION = float(self.reveal_duration_var.get())

        br.CARD_SCALE = float(self.card_scale_var.get())
        br.CARD_RADIUS = int(self.card_radius_var.get())
        br.CARD_GAP = int(self.card_gap_var.get())

        br.VIDEO_CODEC = self.video_codec_var.get().strip()
        br.AUDIO_CODEC = self.audio_codec_var.get().strip()
        br.BITRATE = self.bitrate_var.get().strip()
        br.THREADS = int(self.threads_var.get())
        br.PRESET = self.preset_var.get().strip()

        br.recalculate_layout()

    def validate_inputs(self):
        if not os.path.isdir(self.input_dir_var.get()):
            raise ValueError("Input folder not found.")

        if not os.path.isfile(self.background_var.get()):
            raise ValueError("Background file not found.")

        music_path = self.music_var.get().strip()
        if music_path and not os.path.isfile(music_path):
            raise ValueError("Music file not found.")

        output_dir = os.path.dirname(self.output_var.get())
        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

    def render_progress_callback(self, percent: int):
        self.root.after(0, lambda: self.update_progress(percent))

    def update_progress(self, percent: int):
        self.progress_var.set(percent)
        self.status_var.set(f"Rendering... {percent}%")

    def start_render(self):
        try:
            self.validate_inputs()
            self.apply_settings_to_renderer()
        except Exception as e:
            messagebox.showerror("Validation error", str(e))
            return

        self.progress_var.set(0)
        self.status_var.set("Rendering... 0%")

        thread = threading.Thread(target=self.render_video, daemon=True)
        thread.start()

    def render_video(self):
        try:
            br.build_video(
                input_dir=self.input_dir_var.get(),
                background_path=self.background_var.get(),
                music_path=self.music_var.get(),
                output_path=self.output_var.get(),
                logger=None,
                progress_callback=self.render_progress_callback,
            )
            self.root.after(0, self.on_render_success)
        except Exception as e:
            self.root.after(0, lambda: self.on_render_error(e))

    def on_render_success(self):
        self.progress_var.set(100)
        self.status_var.set("Done")
        messagebox.showinfo("Success", f"Video rendered successfully.\n\nSaved to:\n{self.output_var.get()}")

    def on_render_error(self, error):
        self.status_var.set("Error")
        messagebox.showerror("Render error", str(error))


def main():
    root = tk.Tk()
    ReelsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()