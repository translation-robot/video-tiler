import yt_dlp
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font
import webbrowser
from screeninfo import get_monitors
from prettytable import PrettyTable
import os
import shutil
import sys
import traceback
import psutil  # For process handling
import time
import appdirs

# Left to do:
# Add a loop check box
# Load and save number of divisions on startup and playing video
# Check layout + menu size is too small
# Auto play on start

# Constants for program version and author
APP_NAME = 'videotiler'
PROGRAM_VERSION = "1.0"
PROGRAM_AUTHOR = "Bluesun"
AUTHOR_EMAIL = "smtv.bot@gmail.com"
AUTHOR_WEBSITE = "https://github.com/translation-robot"

# URL for "Why Tiling" page
WHY_TILING_URL = "https://suprememastertv.com/en1/v/245875177398.html"
SUPPORTED_WEB_SITES = "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"

# File to store the number of divisions
DIVISIONS_FILE_NAME = 'divisions.txt'

DEFAULT_URL = "https://www.youtube.com/watch?v=ZzWBpGwKoaI"


def add_to_path():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    # Add the script directory to PATH
    if script_dir not in os.environ['PATH']:
        os.environ['PATH'] = script_dir + os.pathsep + os.environ['PATH']
    
    # Check if the 'bin' subdirectory exists
    bin_dir = os.path.join(script_dir, 'bin')
    if os.path.isdir(bin_dir):
        # Add the 'bin' subdirectory to PATH
        if bin_dir not in os.environ['PATH']:
            os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']
            
            
def find_executable(executable_name):
    """Find the executable in PATH, script directory, or bin directory."""
    def is_executable(path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    # Check PATH
    path = shutil.which(executable_name)
    if path and is_executable(path):
        return path

    # Check the directory of the script or executable
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    exe_path = os.path.join(base_dir, executable_name)
    if is_executable(exe_path):
        return exe_path

    # Check in a 'bin' directory
    bin_dir = os.path.join(base_dir, 'bin', executable_name)
    if is_executable(bin_dir):
        return bin_dir

    return None

# Get the application directory
app_data_dir = appdirs.user_data_dir(APP_NAME)
DIVISIONS_FILE = os.path.join(app_data_dir, DIVISIONS_FILE_NAME)

# Ensure the application directory exists
os.makedirs(app_data_dir, exist_ok=True)

def read_divisions():
    """Read the number of divisions from a file."""
    if os.path.exists(DIVISIONS_FILE):
        with open(DIVISIONS_FILE, 'r') as file:
            content = file.read().strip()
            if content.isdigit():
                return int(content)
    return 3  # Default number of divisions if the file does not exist or is invalid

def write_divisions(divisions):
    """Write the number of divisions to a file."""
    with open(DIVISIONS_FILE, 'w') as file:
        file.write(str(divisions))

class YouTubeVideo:
    def __init__(self, url, divisions=None, verbose=True):
        self.url = url
        try:
            if divisions is None:
                self.divisions = read_divisions()
            else:
                self.divisions = divisions
        except:
            self.divisions = 3
            write_divisions(self.divisions)
        
        self.verbose = verbose
        self.format = None
        self.title = ""
        self.process = None
        self.process_pid = None
        self.yt_dlp_path = find_executable('yt-dlp')
        self.ffmpeg_path = find_executable('ffmpeg')
        self.ffplay_path = find_executable('ffplay')
        self.play_flag = None

        if not self.yt_dlp_path or not self.ffmpeg_path or not self.ffplay_path:
            raise FileNotFoundError("One or more required executables (yt-dlp, ffmpeg, ffplay) not found.")

        self._get_video_info()
        self._get_screen_resolution()
        #self._choose_format()

    def _get_video_info(self):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(self.url, download=False)
            self.title = result.get('title', 'Unknown Title')

    def _get_screen_resolution(self):
        monitor = get_monitors()[0]
        self.screen_width = monitor.width
        self.screen_height = monitor.height
        
    def _choose_format(self):
        self.format = None
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(self.url, download=False)
            formats = result.get('formats', [])

            # Filter out vp09 codecs
            video_audio_formats = [
                f for f in formats 
                if 'vcodec' in f and 'acodec' in f 
                and not f.get('vcodec', '').startswith('vp09')  # Exclude vp09 codecs
                and f.get('vcodec') != 'none' 
                and f.get('acodec') != 'none'
            ]
            video_formats = [
                f for f in formats 
                if f.get('vcodec') and not f['vcodec'].startswith('vp09')  # Exclude vp09 codecs
                and f.get('acodec') == 'none'
                and f.get('vcodec') is not None
            ]
            audio_formats = [
                f for f in formats 
                if 'acodec' in f and not f.get('vcodec', '').startswith('vp09')  # Exclude vp09 codecs
                and f.get('vcodec') == 'none'
            ]

            # Sort formats
            video_audio_formats.sort(key=lambda x: (x.get('height', 0), x.get('width', 0)))
            video_formats.sort(key=lambda x: (x.get('height', 0), x.get('width', 0)))
            audio_formats.sort(key=lambda x: x.get('abr') or 0)

            # Prepare pretty table
            if self.verbose:
                table = PrettyTable()
                table.field_names = ["Format ID", "Resolution", "Type", "VCodec", "ACodec", "Bitrate (kbps)"]

                for f in video_audio_formats:
                    table.add_row([
                        f['format_id'],
                        f.get('resolution', 'Unknown'),
                        "Video+Audio",
                        f.get('vcodec', 'Unknown'),
                        f.get('acodec', 'Unknown'),
                        f.get('abr', 'N/A') if 'abr' in f else 'N/A'
                    ])
                
                for f in video_formats:
                    table.add_row([
                        f['format_id'],
                        f.get('resolution', 'Unknown'),
                        "Video",
                        f.get('vcodec', 'Unknown'),
                        'N/A',
                        'N/A'
                    ])
                
                for f in audio_formats:
                    table.add_row([
                        f['format_id'],
                        "Audio only",
                        "Audio",
                        'N/A',
                        f.get('acodec', 'Unknown'),
                        f.get('abr', 'N/A') if 'abr' in f else 'N/A'
                    ])
                
                print(table)

            tile_width = self.screen_width / self.divisions
            tile_height = self.screen_height / self.divisions

            selected_format = None

            # Step 1: Prefer a format that has both video and audio
            for f in video_audio_formats:
                if f.get('width', 0) >= tile_width and f.get('height', 0) >= tile_height:
                    selected_format = f
                    break

            # Step 2: If no suitable video+audio format, combine separate video and audio formats
            if not selected_format:
                selected_video_format = None
                selected_audio_format = None

                for f in video_formats:
                    if f.get('width', 0) >= tile_width and f.get('height', 0) >= tile_height:
                        selected_video_format = f
                        break

                if selected_video_format is None and video_formats:
                    selected_video_format = video_formats[-1]

                if audio_formats:
                    selected_audio_format = audio_formats[-1]  # Choosing the highest bitrate available

                if selected_video_format and selected_audio_format:
                    selected_format = {
                        'format_id': f"{selected_video_format['format_id']}+{selected_audio_format['format_id']}",
                        'resolution': f"{selected_video_format.get('width', 'Unknown')}x{selected_video_format.get('height', 'Unknown')}",
                    }

            if selected_format:
                self.format = selected_format['format_id']
                if self.verbose:
                    print(f"Screen resolution: {self.screen_width}x{self.screen_height}")
                    print(f"Tile resolution: {tile_width}x{tile_height}")
                    print(f"Selected format ID: {self.format} - {selected_format['resolution']}")
            else:
                print("No suitable format found.")



    def play_video(self):
        print("play_video")
        self.play_flag = True
        #if not self.format:
        #    print("No suitable format found.")
        #    return
        self._choose_format()
        
        try:
            write_divisions(self.divisions)
        except:
            pass

        useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"

        # yt-dlp command
        if self.format is not None:
            #print("Using default format")
            yt_dlp_command = [
                self.yt_dlp_path, self.url, '--user-agent', useragent, '-4', '-f', self.format, '-o', '-',
                '--quiet', '--no-warnings'
            ]
        else:
            #self.format
            #print(f"Using format {self.format}") '--user-agent', useragent, 
            yt_dlp_command = [
                self.yt_dlp_path, self.url, '-4', '-f', 'bestvideo+bestaudio/best', '-o', '-',
                '--quiet', '--no-warnings'
            ]
        
        # ffplay command
        ffplay_command = [
            self.ffplay_path, '-', '-vf',
            f'scale=w=iw*{self.divisions}/{self.divisions}:h=ih*{self.divisions}/{self.divisions},'
            f'fps=source_fps*{self.divisions}*{self.divisions},tile={self.divisions}x{self.divisions}',
            '-autoexit', '-loglevel', 'error', '-hide_banner', '-fs'
        ]

        while self.play_flag:  # Check play flag to 
            if self.process:
                self.process.terminate()
                self.process.wait()
                print("Previous yt-dlp process terminated.")
                
            # Use subprocess.PIPE to handle the pipe
            print(yt_dlp_command)
            print(ffplay_command)
            self.process = subprocess.Popen(
                yt_dlp_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            ffplay_process = subprocess.Popen(
                ffplay_command, stdin=self.process.stdout, stderr=subprocess.PIPE
            )
            
            self.process_pid = ffplay_process.pid
            print(f"yt-dlp process PID: {self.process_pid}")

            # Monitor yt-dlp process
            while self.play_flag:  # Continue to monitor if play flag is set
                try:
                    # Check if yt-dlp process is still running
                    if self.process.poll() is not None:  # Check if process is terminated
                        print("yt-dlp process terminated. Restarting...")
                        break
                    
                    # Check if ffplay process is still running
                    current_process = psutil.Process()
                    ffplay_alive = False
                    for child in current_process.children(recursive=True):
                        if child.name() == 'ffplay' or child.name() == 'ffplay.exe':
                            ffplay_alive = True
                    
                    # If ffplay is not running but yt-dlp is, restart yt-dlp and ffplay
                    if not ffplay_alive:
                        print("ffplay process terminated. Restarting yt-dlp and ffplay...")
                        #self.stop_video()  # Ensure old processes are terminated
                        break
    
                    if self.process.poll() is not None:  # Check if process is terminated
                        print("yt-dlp process terminated. Restarting...")
                        self.play_video
                        break
                except:
                    var = traceback.format_exc()
                    print(var)
                    print("Sleep 1")
                time.sleep(1)  # Check every second

    def stop_video(self):
        if self.process_pid:
            print("Stopping video")
            try:
                # Use psutil to handle process tree
                process = psutil.Process(self.process_pid)
                for proc in process.children(recursive=True):
                    print(f"Terminating child process ID: {proc.pid}")
                    try:
                        proc.kill()
                    except psutil.NoSuchProcess:
                        print(f"Child process ID {proc.pid} does not exist anymore.")
                print(f"Terminating process ID: {self.process_pid}")
                process.kill()
                process.wait(timeout=5)
                print(f"Process ID {self.process_pid} terminated gracefully.")
            except psutil.NoSuchProcess:
                print(f"Process ID {self.process_pid} already terminated.")
            except subprocess.TimeoutExpired:
                print(f"Process ID {self.process_pid} did not terminate in time. Forcefully Terminating.")
                process.kill()
                print(f"Killed process ID: {self.process_pid}")
            finally:
                # Clean up
                self.process = None
                self.process_pid = None
        else:
            #print("No video instance to stop.")
            pass
        self.play_flag = False  # Stop the play flag

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Tiler")
        #self.geometry("600x300")  # Set window size to 600x300
        
        # Set the app icon
        try:
            bin_path = os.path.dirname(os.path.abspath(__file__))
            self.icon_path = os.path.join(bin_path, 'img', 'app.ico')
            self.iconbitmap(self.icon_path)
        except Exception as e:
            print(f"Failed to set app icon: {e}")
        
        self.yt_video = None
        self.video_thread = None
        self.play_flag = False  # Flag to track play state
        
        self.create_menu()
        self.create_widgets()
        self.load_saved_divisions()
        
        # Initialize with default video
        self.initialize_default_video()

    def initialize_default_video(self):
        if not self.yt_video:
            self.url_entry.insert(0, DEFAULT_URL)
            self.after(1, self.update_video_title)
            #self.play_video()  # Automatically start playing the default video

    def create_widgets(self):
        # Video title label
        self.video_title_label = tk.Label(self, text="Video Title", font=("Helvetica", 12))
        self.video_title_label.grid(row=1, column=1, columnspan=4, padx=10, pady=10, sticky='w')

        # URL Entry
        self.url_label = tk.Label(self, text="Video URL:", font=("Helvetica", 12))
        self.url_label.grid(row=2, column=1, padx=10, pady=10, sticky='w')

        self.url_entry = tk.Entry(self, width=50)
        self.url_entry.grid(row=2, column=2, columnspan=3, padx=10, pady=10, sticky='w')

        # Spinbox for divisions
        self.divisions_label = tk.Label(self, text="Grid divisions:", font=("Helvetica", 12))
        self.divisions_label.grid(row=3, column=1, padx=10, pady=10, sticky='w')

        self.divisions_spinbox = tk.Spinbox(self, from_=1, to=50, increment=1, width=5)
        self.divisions_spinbox.grid(row=3, column=2, padx=10, pady=10, sticky='w')

        # Buttons
        self.stop_button = tk.Button(self, text="■", command=self.stop_video, width=5, height=2, bg='blue', fg='white')
        self.stop_button.grid(row=3, column=3, padx=10, pady=10)

        self.play_button = tk.Button(self, text="▶", command=self.play_video, width=5, height=2, bg='blue', fg='white')
        self.play_button.grid(row=3, column=4, padx=10, pady=10)

        # Status bar
        self.status_bar = tk.Label(self, text="Status: Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=4, column=1, columnspan=5, padx=10, pady=10, sticky='ew')

        # Bind URL entry change to update video title
        self.url_entry.bind("<FocusOut>", self.update_video_title)

        # Configure grid resizing
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_columnconfigure(4, weight=1)

        
    def create_menu(self):
        menubar = tk.Menu(self)
        about_menu = tk.Menu(menubar, tearoff=0)
        about_menu.add_command(label="Supported video sites", command=self.open_supported_video_site_list)
        about_menu.add_command(label="Why Tiling", command=self.open_why_tiling)
        about_menu.add_command(label="Help", command=self.show_help)
        menubar.add_cascade(label="About", menu=about_menu)
        self.config(menu=menubar)

    def show_help(self):
        help_text = f"Program Version: {PROGRAM_VERSION}\nEmail: {AUTHOR_EMAIL}\nWebsite: {AUTHOR_WEBSITE}"
        messagebox.showinfo("Help", help_text)

    def open_why_tiling(self):
        webbrowser.open(WHY_TILING_URL)
        
    def open_supported_video_site_list(self):
        webbrowser.open(SUPPORTED_WEB_SITES)


    def update_video_title(self, event=None):
        url = self.url_entry.get()
        if url != (self.yt_video.url if self.yt_video else ""):
            if self.yt_video:
                self.stop_video()  # Stop any currently playing video
            self.yt_video = YouTubeVideo(url, int(self.divisions_spinbox.get()))
            self.after(100, self._update_title_label)

    def _update_title_label(self):
        if self.yt_video:
            self.video_title_label.config(text=f"{self.yt_video.title}")

    def play_video(self):
        self.stop_video()  # Stop any currently playing video
        
        # Start video playback in a separate thread
        url = self.url_entry.get()
        divisions = int(self.divisions_spinbox.get())
        self.yt_video = YouTubeVideo(url, divisions)
        
        # Show temporary starting message
        try:
            self.update_status(f"Starting video player '{self.yt_video.title}'", color='blue')
            self._update_title_label()
        except:
            self.update_status(f"Ready")
            
        self.play_flag = True  # Set play flag
        self.video_thread = threading.Thread(target=self.yt_video.play_video)
        self.video_thread.start()

        # Update status after 17 seconds
        self.after(17000, lambda: self.update_status(f"Playing video '{self.yt_video.title}'"))
        self._update_title_label()

    def stop_video(self):
        if self.yt_video:
            self.yt_video.stop_video()
            self.update_status("Ready")
            self.play_flag = False  # Unset play flag
        else:
            print("No video instance to stop.")

    def update_status(self, message, color='black'):
        self.status_bar.config(text=f"Status: {message}", fg=color)

    def load_saved_divisions(self):
        try:
            with open(DIVISIONS_FILE, "r") as file:
                saved_divisions = int(file.read().strip())
                if 1 <= saved_divisions <= 50:
                    self.divisions_spinbox.delete(0, tk.END)
                    self.divisions_spinbox.insert(0, saved_divisions)
                else:
                    self.divisions_spinbox.delete(0, tk.END)
                    self.divisions_spinbox.insert(0, 3)
        except FileNotFoundError:
            self.divisions_spinbox.delete(0, tk.END)
            self.divisions_spinbox.insert(0, 3)

    def on_closing(self):
        self.stop_video()  # Ensure the video is stopped before closing
        self.destroy()

if __name__ == "__main__":
    add_to_path()
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
