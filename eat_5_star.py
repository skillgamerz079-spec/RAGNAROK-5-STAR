"""Eat 5 Star — a small Python desktop idle challenge.

Run with Python 3.10+; Tkinter is included with most Python installations.
On Windows, low-level input hooks detect mouse and keyboard activity anywhere
on the desktop while a round is active. Other platforms monitor this window.
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

COCOA = "#2a140c"
GOLD = "#f6bd2e"
RED = "#d83a2c"
CREAM = "#fff0d0"
MILESTONES = (10, 30, 60, 120, 300)
RANK_TAGS = ("Novice", "Apprentice", "Focused", "Pro", "Motivated", "Motivated Legend")
ENDLESS_TAGS = ("Champion", "Cosmic", "Eternal", "Infinite", "Mythic")


def best_score_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        folder = base / "Eat5Star"
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support" / "Eat5Star"
    else:
        folder = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "eat-5-star"
    return folder / "best.json"


class GlobalInputMonitor:
    """Windows global input hooks. Callbacks are retained for the hook lifetime."""

    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104
    WM_MOUSEMOVE = 0x0200
    WM_LBUTTONDOWN = 0x0201
    WM_RBUTTONDOWN = 0x0204
    WM_MBUTTONDOWN = 0x0207
    WM_MOUSEWHEEL = 0x020A
    WM_XBUTTONDOWN = 0x020B

    def __init__(self, on_input):
        self.on_input = on_input
        self.thread = None
        self.thread_id = None
        self.hooks = []
        self.callbacks = []
        self.running = False
        self.last_xy = None

    def start(self):
        if os.name != "nt" or self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name="Eat5StarInput", daemon=True)
        self.thread.start()

    def stop(self):
        if os.name != "nt" or not self.running:
            return
        import ctypes
        from ctypes import wintypes
        self.running = False
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)

    def _run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.thread_id = kernel32.GetCurrentThreadId()
        hook_proc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = (ctypes.c_int, hook_proc_type, wintypes.HINSTANCE, wintypes.DWORD)
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)

        def mouse_proc(code, message, data):
            if code >= 0:
                msg = int(message)
                if msg == self.WM_MOUSEMOVE:
                    # MSLLHOOKSTRUCT starts with POINT (two signed longs).
                    x, y = ctypes.cast(data, ctypes.POINTER(ctypes.c_long * 2)).contents
                    pos = (int(x), int(y))
                    old = self.last_xy
                    self.last_xy = pos
                    if old is not None and math.hypot(pos[0] - old[0], pos[1] - old[1]) >= 3:
                        self.on_input("You moved the mouse")
                elif msg in (self.WM_LBUTTONDOWN, self.WM_RBUTTONDOWN, self.WM_MBUTTONDOWN, self.WM_XBUTTONDOWN):
                    self.on_input("You clicked")
                elif msg == self.WM_MOUSEWHEEL:
                    self.on_input("You scrolled")
            return user32.CallNextHookEx(None, code, message, data)

        def keyboard_proc(code, message, data):
            if code >= 0 and int(message) in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN):
                self.on_input("You pressed a key")
            return user32.CallNextHookEx(None, code, message, data)

        mouse_callback = hook_proc_type(mouse_proc)
        key_callback = hook_proc_type(keyboard_proc)
        self.callbacks = [mouse_callback, key_callback]
        mouse_hook = user32.SetWindowsHookExW(self.WH_MOUSE_LL, mouse_callback, kernel32.GetModuleHandleW(None), 0)
        key_hook = user32.SetWindowsHookExW(self.WH_KEYBOARD_LL, key_callback, kernel32.GetModuleHandleW(None), 0)
        self.hooks = [h for h in (mouse_hook, key_hook) if h]
        msg = wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        for hook in self.hooks:
            user32.UnhookWindowsHookEx(hook)
        self.hooks.clear()


class Eat5Star:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Eat 5 Star — Do nothing")
        self.root.configure(bg=COCOA)
        self.root.minsize(360, 520)
        self.root.geometry("500x700")
        self.root.resizable(True, True)
        self.state = "idle"
        self.countdown_end = 0.0
        self.started_at = 0.0
        self.best = self._load_best()
        self.active_stars = 0
        self.last_pointer = None
        self.button_bounds = None
        self.button_hover = False
        self.hook = GlobalInputMonitor(self._global_input)
        self.bg = COCOA
        self.canvas = tk.Canvas(self.root, bg=COCOA, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.action_button = tk.Button(
            self.canvas, text="Eat", command=self.start,
            font=("Trebuchet MS", 19, "bold"),
            bg=GOLD, fg=COCOA, activebackground="#ffdc72", activeforeground=COCOA,
            relief="flat", bd=0, highlightthickness=0, cursor="hand2",
            padx=12, pady=4,
        )
        self.canvas.bind("<Configure>", lambda _e: self.draw())
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Button>", self._click)
        self.canvas.bind("<MouseWheel>", lambda _e: self.lose("You scrolled"))
        self.root.bind_all("<KeyPress>", lambda _e: self.lose("You pressed a key"))
        self.root.bind("<FocusOut>", self._focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.draw()
        self.root.after(30, self.update)

    def _load_best(self):
        try:
            return float(json.loads(best_score_path().read_text(encoding="utf-8")).get("best", 0))
        except (OSError, ValueError, TypeError, AttributeError):
            return 0.0

    def _save_best(self):
        try:
            path = best_score_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"best": self.best}), encoding="utf-8")
        except OSError:
            pass

    def _global_input(self, reason):
        # Windows hook callbacks arrive on a worker thread; schedule UI work safely.
        try:
            self.root.after(0, lambda: self.lose(reason))
        except tk.TclError:
            pass

    def _motion(self, event):
        point = (event.x_root, event.y_root)
        if self.state in ("idle", "over") and self.button_bounds:
            b = self.button_bounds
            hovering = b[0] <= event.x <= b[2] and b[1] <= event.y <= b[3]
            if hovering != self.button_hover:
                self.button_hover = hovering
                self.draw()
        if self.last_pointer is None:
            self.last_pointer = point
            return
        moved = math.hypot(point[0] - self.last_pointer[0], point[1] - self.last_pointer[1]) >= 3
        self.last_pointer = point
        if self.state == "run" and moved and os.name != "nt":
            self.lose("You moved the mouse")

    def _click(self, _event):
        if self.state == "run" and os.name != "nt":
            self.lose("You clicked")

    def _focus_out(self, _event):
        if self.state == "run" and os.name != "nt":
            self.lose("You left the window")

    def start(self):
        self.state = "count"
        self.countdown_end = time.monotonic() + 3
        self.bg = COCOA
        self.active_stars = 0
        self.last_pointer = None
        self.button_hover = False
        self.hook.start()
        self.draw()

    def lose(self, reason):
        if self.state != "run":
            return
        elapsed = max(0, time.monotonic() - self.started_at)
        self.state = "over"
        self.bg = "#64180f"
        self.button_hover = False
        is_best = elapsed > self.best
        if is_best:
            self.best = elapsed
            self._save_best()
        rank = self.rank_for(elapsed)
        self.hook.stop()
        self.draw(reason=reason, elapsed=elapsed, rank=rank, is_best=is_best)

    def update(self):
        now = time.monotonic()
        if self.state == "count":
            left = self.countdown_end - now
            if left <= 0:
                self.state = "run"
                self.started_at = now
                self.bg = COCOA
                self.draw()
            else:
                self.draw(countdown=math.ceil(left))
        elif self.state == "run":
            elapsed = now - self.started_at
            stars = sum(elapsed >= mark for mark in MILESTONES)
            if stars != self.active_stars or int(elapsed * 100) != getattr(self, "last_hundredth", -1):
                self.active_stars = stars
                self.last_hundredth = int(elapsed * 100)
                self.draw(elapsed=elapsed)
        self.root.after(30, self.update)

    @staticmethod
    def rank_for(elapsed):
        stars = sum(elapsed >= mark for mark in MILESTONES)
        if elapsed < MILESTONES[-1]:
            return RANK_TAGS[stars]
        prestige = int(elapsed // MILESTONES[-1]) - 1
        if prestige == 0:
            return RANK_TAGS[-1]
        if prestige <= len(ENDLESS_TAGS):
            return f"{ENDLESS_TAGS[prestige-1]} Legend"
        generator_step = prestige - len(ENDLESS_TAGS) - 1
        title = ENDLESS_TAGS[generator_step % len(ENDLESS_TAGS)]
        ascension = generator_step // len(ENDLESS_TAGS) + 2
        return f"{title} Legend · Ascension {ascension}"

    def draw(self, countdown=None, elapsed=None, reason=None, rank=None, is_best=False):
        c = self.canvas
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        # Smooth cocoa gradient, blended between four warm color stops.
        stops = ((0.0, (24, 9, 5)), (0.36, (66, 31, 17)), (0.72, (49, 22, 12)), (1.0, (20, 8, 5)))
        bands = 48
        for i in range(bands):
            t = (i + .5) / bands
            for j in range(len(stops) - 1):
                if stops[j][0] <= t <= stops[j + 1][0]:
                    ta, ca = stops[j]
                    tb, cb = stops[j + 1]
                    f = (t - ta) / (tb - ta)
                    rgb = tuple(round(a + (b-a)*f) for a, b in zip(ca, cb))
                    break
            color = "#%02x%02x%02x" % rgb
            y0 = h * i / bands
            c.create_rectangle(0, y0, w, h * (i + 1) / bands + 1, fill=color, outline="")
        center_x = w / 2
        self.button_bounds = None

        def rounded_rect(x1, y1, x2, y2, radius, fill, outline="", width=1):
            radius = max(0, min(radius, (x2-x1)/2, (y2-y1)/2))
            points = []
            corners = ((x2-radius, y1+radius, -90),
                       (x2-radius, y2-radius, 0),
                       (x1+radius, y2-radius, 90),
                       (x1+radius, y1+radius, 180))
            for cx, cy, start_angle in corners:
                for step in range(7):
                    angle = math.radians(start_angle + step * 15)
                    points.extend((cx + math.cos(angle)*radius,
                                   cy + math.sin(angle)*radius))
            return c.create_polygon(points, fill=fill, outline=outline, width=width)

        def logo(y, scale=1.0):
            if self.state in ("count", "run"):
                phase = time.monotonic() - (self.countdown_end - 3)
                y += math.sin(phase * 2.2) * 3
            bar_w = min(w * .70, 330) * scale
            bar_h = bar_w * .30
            left, right = center_x-bar_w/2, center_x+bar_w/2
            top, bottom = y-bar_h/2, y+bar_h/2
            # Foil wrapper body with a deep lower edge and a warm top sheen.
            rounded_rect(left+4, top+8, right+5, bottom+9, bar_h*.48, "#170905")
            rounded_rect(left, top+3, right, bottom+3, bar_h*.48, "#9c5a13", "#713b12", 1)
            rounded_rect(left+2, top, right-2, bottom-7, bar_h*.47, "#f3ad22")
            rounded_rect(left+4, top+2, right-4, y+bar_h*.20, bar_h*.43, GOLD)
            # Fine foil glints and soft folds give the wrapper a curved, glossy surface.
            c.create_line(left+bar_w*.17, top+bar_h*.13, center_x-bar_w*.12, top+bar_h*.08,
                          center_x+bar_w*.19, top+bar_h*.11, fill="#ffe28a", width=max(2, int(bar_h*.055)),
                          smooth=True, splinesteps=16, capstyle=tk.ROUND)
            c.create_line(left+bar_w*.20, bottom-bar_h*.16, center_x, bottom-bar_h*.11,
                          right-bar_w*.20, bottom-bar_h*.16, fill="#cf8519", width=max(2, int(bar_h*.045)),
                          smooth=True, splinesteps=16, capstyle=tk.ROUND)
            # Crimped foil at both ends.
            for side in (-1, 1):
                edge = left if side < 0 else right
                direction = 1 if side < 0 else -1
                for fold in range(3):
                    fx = edge + direction * bar_w*(.035 + fold*.035)
                    c.create_line(fx, top+bar_h*.16, fx+direction*bar_w*.018, y,
                                  fx, bottom-bar_h*.17, fill="#d99820" if fold else "#ffe07a",
                                  width=max(1, int(bar_h*.018)), smooth=True, splinesteps=10)
            # Red brand band, with a subtle lower shade and rounded ends.
            rounded_rect(left+1, y-bar_h*.15+3, right-1, y+bar_h*.15+3,
                         bar_h*.15, "#a92a1f")
            rounded_rect(left+1, y-bar_h*.15, right-1, y+bar_h*.15,
                         bar_h*.15, RED)
            c.create_line(left+bar_w*.16, y-bar_h*.11, right-bar_w*.16, y-bar_h*.11,
                          fill="#ef6251", width=max(1, int(bar_h*.018)), capstyle=tk.ROUND)
            c.create_text(center_x, y, text="5 STAR", fill=CREAM,
                          font=("Trebuchet MS", max(15, int(bar_w*.095)), "bold"))

        def button(label, y):
            self.action_button.configure(text=label)
            bw = min(230, w*.66)
            rounded_rect(center_x-bw/2, y-34, center_x+bw/2, y+34, 34, "#8f261b")
            rounded_rect(center_x-bw/2, y-38, center_x+bw/2, y+28, 33, GOLD, "#ffdc72", 2)
            self.action_button.place(x=center_x, y=y, anchor="center")
            self.action_button.lift()

        if self.state in ("idle", "over"):
            panel_w = min(w-32, 440)
            panel_top, panel_bottom = h*.09, h*.91
            rounded_rect(center_x-panel_w/2, panel_top+8, center_x+panel_w/2,
                         panel_bottom+8, 34, "#170905")
            rounded_rect(center_x-panel_w/2, panel_top, center_x+panel_w/2,
                         panel_bottom, 34, "#351a0e", "#79451e", 2)
            if self.state == "idle":
                logo(h*.25)
                c.create_text(center_x, h*.385, text="Eat 5 Star", fill=GOLD,
                              font=("Trebuchet MS", max(32, min(52, int(w*.12))), "bold"))
                c.create_text(center_x, h*.465, text="Do nothing.", fill=CREAM,
                              font=("Trebuchet MS", 22))
                c.create_text(center_x, h*.58,
                              text="Press Eat, then let go of everything.\nNo time limit — play as long as you can.\nYour rank keeps rising every 5 minutes.",
                              width=panel_w-36, justify="center", fill="#e5cfad",
                              font=("Trebuchet MS", max(12, min(15, int(w*.037)))))
                button("Eat", h*.755)
                c.create_text(center_x, h*.855, text=f"PERSONAL BEST   {self.best:.2f} s",
                              fill="#c0a47b", font=("Trebuchet MS", 11, "bold"))
            else:
                logo(h*.19, .82)
                c.create_text(center_x, h*.335, text="You moved!", fill=GOLD,
                              font=("Trebuchet MS", max(32, min(48, int(w*.11))), "bold"))
                c.create_text(center_x, h*.425, text=rank or "Fidgety", fill=CREAM,
                              font=("Trebuchet MS", 24))
                c.create_text(center_x, h*.525, text=reason or "You moved!", fill="#e5cfad",
                              width=panel_w-40, justify="center", font=("Trebuchet MS", 14))
                c.create_text(center_x, h*.61, text=f"You lasted  {elapsed:.2f} seconds",
                              fill=CREAM, font=("Trebuchet MS", 16, "bold"))
                best_line = "NEW PERSONAL BEST" if is_best and elapsed > .5 else f"PERSONAL BEST   {self.best:.2f} s"
                c.create_text(center_x, h*.69, text=best_line, fill=GOLD if is_best else "#c0a47b",
                              font=("Trebuchet MS", 11, "bold"))
                button("Eat again", h*.80)
            return

        self.action_button.place_forget()
        logo(h*.17, .86)
        if self.state == "count":
            clock_text = str(countdown or 3)
            hint = "Hands off in..."
        else:
            clock_text = f"{(elapsed if elapsed is not None else time.monotonic()-self.started_at):.2f}"
            hint = "Don't touch anything"
        size = max(64, min(148, int(w*.29)))
        ring_r = max(42, min(88, int(w*.19)))
        ring_y = h*.445
        c.create_oval(center_x-ring_r, ring_y-ring_r, center_x+ring_r, ring_y+ring_r,
                      outline="#73431f", width=4)
        if self.state == "count":
            left = max(0.0, self.countdown_end - time.monotonic())
            sweep = 360 * (1 - left / 3)
            c.create_arc(center_x-ring_r, ring_y-ring_r, center_x+ring_r, ring_y+ring_r,
                         start=90, extent=-sweep, style=tk.ARC, outline=GOLD, width=5)
        else:
            c.create_arc(center_x-ring_r, ring_y-ring_r, center_x+ring_r, ring_y+ring_r,
                         start=90, extent=-360, style=tk.ARC, outline=GOLD, width=5)
        c.create_text(center_x, h*.445, text=clock_text, fill=GOLD,
                      font=("Trebuchet MS", size, "bold"))
        star_y = h*.635
        spacing = min(52, w/8)
        for i in range(5):
            sx = center_x+(i-2)*spacing
            active = i < self.active_stars
            pulse = 1 + (.08 * math.sin(time.monotonic()*4 + i)) if active else 1
            radius = 13 * pulse
            points = []
            glow_points = []
            for k in range(10):
                angle = -math.pi/2 + k*math.pi/5
                r = radius if k % 2 == 0 else radius*.46
                points.extend((sx + math.cos(angle)*r, star_y + math.sin(angle)*r))
                gr = radius+3 if k % 2 == 0 else radius*.46+2
                glow_points.extend((sx + math.cos(angle)*gr, star_y + math.sin(angle)*gr))
            if active:
                c.create_polygon(glow_points, fill="#b87118", outline="")
            c.create_polygon(points, fill=GOLD if active else "#604b39",
                             outline="#ffdf83" if active else "#806144", width=2,
                             smooth=True, splinesteps=12)
        run_elapsed = time.monotonic() - self.started_at if self.state == "run" else 0
        tag = self.rank_for(run_elapsed)
        c.create_text(center_x, h*.755, text=f"∞   {tag.upper()}",
                      fill=GOLD, font=("Trebuchet MS", 11, "bold"))
        milestone_text = "10s       30s       1m        2m        5m"
        c.create_text(center_x, h*.71, text=milestone_text, fill="#c0a47b",
                      font=("Trebuchet MS", max(9, min(11, int(w*.027)))))
        c.create_text(center_x, h*.82, text=hint, fill=CREAM,
                      font=("Trebuchet MS", 17, "bold"))

    def close(self):
        self.hook.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Eat5Star().run()
