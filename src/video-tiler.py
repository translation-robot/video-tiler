import yt_dlp
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
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
import pygetwindow as gw
import win32process


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
AUTHOR_WEBSITE = "https://github.com/translation-robot/video-tiler"

# URL for "Why Tiling" page
WHY_TILING_URL = "https://suprememastertv.com/en1/v/245875177398.html"
SUPPORTED_WEB_SITES = "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"
SOURCE_CODE_GITHUB = "https://github.com/translation-robot/video-tiler"

json_configuration_url='https://raw.githubusercontent.com/translation-robot/video-tiler/main/src/configuration/configuration.json'

# File to store the number of divisions
DIVISIONS_FILE_NAME = 'divisions.txt'

DEFAULT_URL = "https://www.youtube.com/watch?v=ZzWBpGwKoaI"

DefaultJsonConfiguration = """{
    "streaming_url_array": ["https://www.youtube.com/watch?v=ZzWBpGwKoaI", "https://x.com/i/broadcasts/1gqGvNDqqZgGB"],
    "streaming_url_user_added_array": []
}"""

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

class TimerWindow:
    def __init__(self, parent, title, question, duration):
        self.parent = tk.Toplevel(parent)  # Create a separate window
        self.parent.title(title)  # Set the window title dynamically
        self.duration = duration
        self.remaining = duration
        
        self.question_var = tk.StringVar(value=question)
        self.do_not_ask_var = tk.BooleanVar(value=False)  # Checkbox state
        self.result = None  # Store the result of OK/Cancel
        self.expired = False  # Track if the timer expired

        # Create UI elements
        self.label = tk.Label(self.parent, textvariable=self.question_var)
        self.label.pack(pady=20)

        self.timer_label = tk.Label(self.parent, text=f"Time remaining: {self.remaining} seconds")
        self.timer_label.pack(pady=10)

        #self.checkbox = tk.Checkbutton(self.parent, text="Do not ask again", variable=self.do_not_ask_var)
        #self.checkbox.pack(pady=10)

        #self.ok_button = tk.Button(self.parent, text="OK", command=self.ok)
        #self.ok_button.pack(side=tk.LEFT, padx=20)

        self.cancel_button = tk.Button(self.parent, text="Cancel", command=self.cancel)
        self.cancel_button.pack(side=tk.RIGHT, padx=20)

        self.update_timer()
        
    def update_timer(self):
        if self.remaining > 0:
            self.remaining -= 1
            self.timer_label.config(text=f"Time remaining: {self.remaining} seconds")
            self.parent.after(1000, self.update_timer)  # Call this function again after 1 second
        else:
            self.expired = True  # Mark as expired
            self.cancel()  # Automatically call cancel when time is up

    def ok(self):
        self.result = True  # OK was pressed
        self.parent.destroy()

    def cancel(self):
        self.result = False  # Cancel was pressed
        self.parent.destroy()
        
        
class YouTubeVideo:
    def __init__(self, parent, url, divisions=None, verbose=True):
        self.parent = parent  # Store reference to the Tkinter parent (App instance)
        self.url = url
        self.timer_window = None
        self.ytdlp_process = None
        self.ytdlp_process = None
        self.ytdlp_is_valid = False
        
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

        try:
            self._get_video_info()
            self._get_screen_resolution()
            self.ytdlp_is_valid = True
        except Exception as e:
            # Handle errors here (e.g., invalid URL, video not available)
            print(f"Error creating YouTube video: {e}")
            return
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
            #print(formats)
            #input("Formats listed (all)")

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
                if f.get('vcodec') == 'none'
                #    and 'acodec' in f  # Exclude vp09 codecs
            ]
            
            #print("Audio codecs")
            #print(audio_formats)
            #input("Formats audio (all)")

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
            if not selected_format or selected_format is None:
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

    def check_timer_result(self, timer_window):
        self.parent.wait_window(timer_window.parent)  # Wait for the TimerWindow to close

        if timer_window.expired:
            print("The timer expired before user response.")
        elif timer_window.result:  # If OK was pressed
            print("User chose to restart the video.")
        else:
            print("User chose to cancel.")
            self.parent.update_status("Ready")
            
    def _is_ffmpeg_descendant_with_window(self, timeout=30):
        current_pid = psutil.Process().pid
        start_time = time.time()

        def has_window(pid):
            for window in gw.getAllWindows():
                if window._hWnd:  # Ensure the window handle is valid
                    _, window_pid = win32process.GetWindowThreadProcessId(window._hWnd)
                    if window_pid == pid:
                        return True
            return False

        while (time.time() - start_time) < timeout:
            # Get the current process
            current_process = psutil.Process(current_pid)

            # Check for yt-dlp child processes
            yt_dlp_exists = any(child.name() == 'yt-dlp.exe' for child in current_process.children(recursive=True))

            if not yt_dlp_exists:
                print("no yt-dlp process exists")
                return False  # Return False immediately if no yt-dlp child process exists

            # Iterate over the children of the current process to check for ffplay
            for child in current_process.children(recursive=True):
                try:
                    # Check for yt-dlp child processes
                    ffplay_exists = any(child.name() == 'ffplay.exe' for child in current_process.children(recursive=True))

                    if not ffplay_exists:
                        print("no yt-dlp process exists")
                        return False  # Return False immediately if no yt-dlp child process exists
                        
                    # Check if the child process is ffplay
                    if child.name() == 'ffplay.exe':
                        if has_window(child.pid):  # Use child.pid to check for the window
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            time.sleep(1)  # Check every second

        return False



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


        while self.play_flag:  # Check play flag to 
            self.url = self.parent.url_entry.get()
            self.divisions = int(self.parent.divisions_spinbox.get())
            write_divisions(self.divisions)
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

        
        
        
            if self.ytdlp_process:
                self.ytdlp_process.terminate()
                self.ytdlp_process.wait()
                exit_code = self.ytdlp_process.returncode
                print(f"yt-dlp process exited with exit code {exit_code}")
                print("Previous yt-dlp process terminated.")
                
            # Use subprocess.PIPE to handle the pipe
            print(yt_dlp_command)
            print(ffplay_command)
            self.ytdlp_process = subprocess.Popen(
                yt_dlp_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            
            self.ffplay_process = subprocess.Popen(
                ffplay_command, stdin=self.ytdlp_process.stdout, stderr=subprocess.PIPE
            )
            
            self.process_pid = self.ffplay_process.pid
            print(f"yt-dlp process PID: {self.process_pid}")

            # Monitor yt-dlp process
            ffplay_alive = False
            while self.play_flag:  # Continue to monitor if play flag is set
                try:
                    print("Loop 1")
                    if self._is_ffmpeg_descendant_with_window():
                        if ffplay_alive == False:
                            print("ffmpeg window is running.")
                        ffplay_alive = True
                    else:
                        if ffplay_alive == True:
                            print("No descendant ffmpeg process with a window found.")
                        ffplay_alive = False
                        self.parent.play_button.config(state=tk.NORMAL)
                        
                    
                    # If ffplay is not running but yt-dlp is, restart yt-dlp and ffplay
                    if not ffplay_alive:
                        #self.timer_window = TimerWindow(self, self.parent, title="Action Required", question="Video was stopped, do you want to restart it?", duration=10)
                        if self.parent.auto_restart_video.get() == True:
                            if self.play_flag == True:
                                print("Starting OK/Cancell window")
                                self.timer_window = TimerWindow(parent=self.parent, title="Action Required", question="Video was stopped and will be restarted automatically.", duration=10)
                            else:
                                return
                        else:
                            self.parent.update_status(f"Ready")
                            return
                        
                        #self.parent.root.wait_window(timer_window.parent)
                        self.parent.wait_window(self.timer_window.parent)
                        if self.timer_window.expired:
                            print("The timer expired before user response.")
                            self.timer_window.result = True
                        # Access the result and the checkbox value after the window has been closed
                        if self.timer_window.result:  # If OK was pressed
                            print("User chose to restart the video.")
                        else:
                            print("User chose to cancel or timer expired.")
                            self.parent.update_status(f"Ready")
                                        
                            self.ytdlp_process.wait()
                            exit_code = self.ytdlp_process.returncode
                            print(f"yt-dlp process exited with exit code {exit_code}")
                            print("Previous yt-dlp process terminated.")
                            return

                        # Check if "Do not ask again" was selected
                        if self.timer_window.do_not_ask_var:
                            print("User checked 'Do not ask again'.")
                        else:
                            print("User did not check 'Do not ask again'.")
                            
                        
                        print("ffplay process terminated. Restarting yt-dlp and ffplay...")
                        #self.stop_video()  # Ensure old processes are terminated
                        break
    
                    if self.ytdlp_process.poll() is not None:  # Check if process is terminated
                        #self.timer_window = TimerWindow(self, self.parent, title="Action Required", question="Video was stopped, do you want to restart it?", duration=10)
                        #self.timer_window = TimerWindow(parent=self.parent, title="Action Required", question="Video was stopped, do you want to restart it?", duration=10)
                        print("yt-dlp process terminated. Restarting...")
                        
                        exit_code = self.ytdlp_process.returncode
                        print(f"yt-dlp process exited with exit code {exit_code}")
                        print("Previous yt-dlp process terminated.")
                        self.play_video
                        break
                except:
                    var = traceback.format_exc()
                    print(var)
                    print("Sleep 1")
                time.sleep(1)  # Check every second
        self.parent.play_button.config(state=tk.NORMAL)

    def stop_video(self):
        self.play_flag = False
        if self.timer_window is not None:
            self.timer_window.parent.destroy()
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
        self.is_ffmpeg_visible = False
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

        array_url = ["https://www.youtube.com/watch?v=ZzWBpGwKoaI", "https://x.com/i/broadcasts/1LyxBgjebwOKN"]

        #self.url_entry = tk.Entry(self, width=50)
        
        self.url_entry = ttk.Combobox(self, values=array_url, width=50)
        self.url_entry.set('')  # Optional: Set default text
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

        # Checkbox
        self.auto_restart_video = tk.BooleanVar(value=True)  # Checkbox state
        self.auto_restart_checkbutton = tk.Checkbutton(self, text="Auto Restart Video", variable=self.auto_restart_video)
        self.auto_restart_checkbutton.grid(row=4, column=1, padx=10, pady=10, sticky='w')  # Use Checkbutton and grid it

        
        # Status bar
        self.status_bar = tk.Label(self, text="Status: Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.grid(row=5, column=1, columnspan=5, padx=10, pady=10, sticky='ew')

        # Bind URL entry change to update video title
        self.url_entry.bind("<FocusOut>", self.update_video_title)

        # Configure grid resizing
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(3, weight=1)
        self.grid_columnconfigure(4, weight=1)
    
    def create_menu(self):
        menubar = tk.Menu(self)

        # Define a custom font for the menu items
        menu_font = tkfont.Font(family="Helvetica", size=12)
        menu_font_small = tkfont.Font(family="Helvetica", size=8)

        about_menu = tk.Menu(menubar, tearoff=0)

        # Add commands with zero padding
        about_menu.add_command(label="Supported video sites", command=self.open_supported_video_site_list, font=menu_font)
        about_menu.add_command(label="Why Tiling", command=self.open_why_tiling, font=menu_font)
        about_menu.add_command(label="Source code", command=self.open_source_code_web_site, font=menu_font)
        about_menu.add_command(label="Help", command=self.show_help, font=menu_font)

        menubar.add_cascade(label="About", menu=about_menu, font=menu_font_small)

        # Configure the menu bar with zero padding (if applicable)
        self.config(menu=menubar)
        
    def show_help(self):
        help_text = f"Program Version: {PROGRAM_VERSION}\nEmail: {AUTHOR_EMAIL}\nWebsite: {AUTHOR_WEBSITE}"
        messagebox.showinfo("Help", help_text)

    def open_why_tiling(self):
        webbrowser.open(WHY_TILING_URL)
        
    def open_supported_video_site_list(self):
        webbrowser.open(SUPPORTED_WEB_SITES)
        
    def open_source_code_web_site(self):
        webbrowser.open(SOURCE_CODE_GITHUB)


    def update_video_title(self, event=None):
        url = self.url_entry.get()
        if url != (self.yt_video.url if self.yt_video else ""):
            if self.yt_video:
                self.stop_video()  # Stop any currently playing video
            self.yt_video = YouTubeVideo(self, url, int(self.divisions_spinbox.get()))
            self.after(100, self._update_title_label)

    def _update_title_label(self):
        if self.yt_video:
            self.video_title_label.config(text=f"{self.yt_video.title}")

    def play_video(self):
        self.stop_video()  # Stop any currently playing video
        self.is_ffmpeg_visible = False
        self.play_button.config(state=tk.DISABLED)
        
        # Start video playback in a separate thread
        url = self.url_entry.get()
        divisions = int(self.divisions_spinbox.get())
        
        self.yt_video = YouTubeVideo(self, url, divisions)
        if self.yt_video.ytdlp_is_valid == False:
            print("Video URL is not valid")
            messagebox.showerror("URL Error", f"URL '{url}' does not seem to be a valid video.")
            self.play_button.config(state=tk.NORMAL)
            return
            
        
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
        self.after(35000, lambda: self.update_status(f"Playing video '{self.yt_video.title}'"))
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
