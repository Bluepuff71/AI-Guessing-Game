"""Animations for game events - supports GIF popups and ASCII fallback."""

import os
import sys
import time

# Path to assets folder
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
ELIMINATION_GIF = os.path.join(ASSETS_DIR, "elimination.gif")
VICTORY_GIF = os.path.join(ASSETS_DIR, "victory.gif")
ESCAPE_GIF = os.path.join(ASSETS_DIR, "escape.gif")


def play_gif_popup(gif_path: str, duration: float = None):
    """
    Play a GIF in a popup window that auto-closes.

    Args:
        gif_path: Path to the GIF file
        duration: How long to show (seconds). If None, plays once through.

    Returns:
        True if played successfully, False if failed
    """
    if not os.path.exists(gif_path):
        return False

    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except ImportError:
        return False

    try:
        gif = Image.open(gif_path)

        # Get all frames
        frames = []
        frame_delays = []
        try:
            while True:
                frames.append(gif.copy())
                frame_delays.append(gif.info.get('duration', 100))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass

        if not frames:
            return False

        # Create window
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes('-topmost', True)

        # Center on screen
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        gif_width = frames[0].width
        gif_height = frames[0].height
        x = (screen_width - gif_width) // 2
        y = (screen_height - gif_height) // 2
        root.geometry(f"{gif_width}x{gif_height}+{x}+{y}")

        label = tk.Label(root, bg='black')
        label.pack()

        photo_frames = [ImageTk.PhotoImage(frame.convert('RGBA')) for frame in frames]

        current_frame = [0]
        start_time = [time.time()]

        gif_duration = sum(frame_delays) / 1000.0
        if duration is None:
            duration = gif_duration

        def animate():
            if time.time() - start_time[0] >= duration:
                root.quit()
                root.destroy()
                return

            # Stop after playing through all frames once
            if current_frame[0] >= len(photo_frames):
                root.quit()
                root.destroy()
                return

            label.config(image=photo_frames[current_frame[0]])
            delay = frame_delays[current_frame[0]]
            current_frame[0] += 1
            root.after(delay, animate)

        def close_early(event):
            root.quit()
            root.destroy()

        root.bind('<Button-1>', close_early)
        root.bind('<Key>', close_early)

        animate()
        root.mainloop()
        return True

    except Exception:
        return False


def play_elimination_animation():
    """Play the elimination animation when a player fails to escape."""
    # Try GIF first
    if play_gif_popup(ELIMINATION_GIF, duration=4.0):
        return

    # Fallback: simple text flash
    try:
        from rich.console import Console
        console = Console()

        for i in range(3):
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print()
            style = "bold red" if i % 2 == 0 else "bold yellow"
            console.print(f"\n\n                    [{style}]>>> TERMINATED <<<[/{style}]\n")
            time.sleep(0.3)
        time.sleep(0.5)
    except Exception:
        print("\n>>> TERMINATED <<<\n")
        time.sleep(1)


def play_victory_animation():
    """Play the victory animation when a player wins the game."""
    # Try GIF first
    if play_gif_popup(VICTORY_GIF, duration=3.0):
        return

    # Fallback: simple text flash
    try:
        from rich.console import Console
        console = Console()

        for i in range(3):
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print()
            style = "bold green" if i % 2 == 0 else "bold yellow"
            console.print(f"\n\n                    [{style}]>>> VICTORY! <<<[/{style}]\n")
            time.sleep(0.3)
        time.sleep(0.5)
    except Exception:
        print("\n>>> VICTORY! <<<\n")
        time.sleep(1)


def play_escape_animation():
    """Play the escape animation when a player outsmarts the AI."""
    # Try GIF first
    if play_gif_popup(ESCAPE_GIF, duration=2.0):
        return

    # Fallback: simple text flash
    try:
        from rich.console import Console
        console = Console()

        for i in range(2):
            os.system('cls' if os.name == 'nt' else 'clear')
            console.print()
            style = "bold green" if i % 2 == 0 else "bold cyan"
            console.print(f"\n\n                    [{style}]>>> ESCAPED! <<<[/{style}]\n")
            time.sleep(0.25)
        time.sleep(0.3)
    except Exception:
        print("\n>>> ESCAPED! <<<\n")
        time.sleep(0.5)
