import os, sys, json, time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QStyle, QFrame, QSizePolicy
)

try:
    import vlc
except ImportError:
    print("pip install python-vlc"); sys.exit(1)
except OSError as e:
    if getattr(e, "winerror", None) == 193:
        print("Architecture mismatch: Python and VLC must both be 32-bit or both 64-bit.")
    raise

PROGRESS_FILENAME = "watch_progress.json"

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
              '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.ogv', '.3gp'}
SUBTITLE_FILTER = "Subtitles (*.srt *.ass *.ssa *.vtt *.sub);;All files (*)"
SAVE_EVERY = 5

DEBUG = True


def log(*a):
    if DEBUG:
        print("[player]", *a)


def tname(v):
    """Normalize a VLC track name to a real Python str.
    python-vlc returns these as bytes; Qt's QAction and json.dump
    both reject bytes, so we decode here."""
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray)):
        return v.decode("utf-8", "replace")
    return str(v)


def fmt(ms):
    ms = max(0, int(ms))
    s = ms // 1000
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}"


DARK_QSS = """
QMainWindow, QWidget {
    background: #1c1c1e;
    color: #e5e5ea;
    font-family: -apple-system, "SF Pro Text", "Segoe UI", sans-serif;
    font-size: 13px;
}
QFrame#Transport {
    background: #252528;
    border-top: 1px solid #333;
}
QLabel { background: transparent; }
QLabel#TimeLabel {
    color: #aeaeb2;
    font-variant-numeric: tabular-nums;
    min-width: 110px;
}
QLabel#Header {
    color: #8e8e93;
    padding: 6px 10px;
    font-weight: 600;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    font-size: 11px;
}
QPushButton {
    background: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 5px 12px;
    color: #e5e5ea;
}
QPushButton:hover  { background: #3a3a3c; }
QPushButton:pressed{ background: #48484a; }
QPushButton:disabled{ color: #636366; border-color: #2c2c2e; }

QPushButton#IconButton {
    padding: 6px;
    min-width: 30px; max-width: 30px;
    min-height: 30px; max-height: 30px;
    border-radius: 15px;
}
QPushButton#PlayButton {
    background: #0a84ff;
    border: none;
    min-width: 38px; max-width: 38px;
    min-height: 38px; max-height: 38px;
    border-radius: 19px;
    padding: 0;
}
QPushButton#PlayButton:hover   { background: #2b95ff; }
QPushButton#PlayButton:pressed { background: #0066cc; }

QSlider::groove:horizontal {
    height: 4px;
    background: #3a3a3c;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #0a84ff;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover { background: #f2f2f7; }

QListWidget {
    background: #1c1c1e;
    border: none;
    outline: none;
    padding: 4px 8px;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 6px;
    color: #d1d1d6;
}
QListWidget::item:hover     { background: #2c2c2e; }
QListWidget::item:selected  { background: #0a84ff; color: #ffffff; }

QMenuBar { background: #1c1c1e; }
QMenuBar::item:selected { background: #0a84ff; border-radius: 5px; }
QMenu {
    background: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item            { padding: 5px 22px 5px 22px; border-radius: 5px; }
QMenu::item:selected   { background: #0a84ff; color: #ffffff; }
QMenu::separator       { height: 1px; background: #3a3a3c; margin: 4px 8px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: #48484a; border-radius: 5px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #636366; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


class VideoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background: #000;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


class PlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Player")
        self.resize(1180, 760)
        self.setMinimumSize(720, 480)

        self.instance = vlc.Instance(
            "--no-video-title-show",
            "--no-sub-autodetect-file",
        )
        self.player = self.instance.media_player_new()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.video = VideoWidget()
        root.addWidget(self.video, stretch=1)

        transport = QFrame(objectName="Transport")
        root.addWidget(transport)
        t = QHBoxLayout(transport)
        t.setContentsMargins(12, 8, 12, 8)
        t.setSpacing(8)

        style = self.style()

        self.play_btn = QPushButton(objectName="PlayButton")
        self.play_btn.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)
        t.addWidget(self.play_btn)

        self.back_btn = QPushButton(objectName="IconButton")
        self.back_btn.setIcon(style.standardIcon(QStyle.SP_MediaSkipBackward))
        self.back_btn.clicked.connect(lambda: self.seek_relative(-10_000))
        t.addWidget(self.back_btn)

        self.fwd_btn = QPushButton(objectName="IconButton")
        self.fwd_btn.setIcon(style.standardIcon(QStyle.SP_MediaSkipForward))
        self.fwd_btn.clicked.connect(lambda: self.seek_relative(+10_000))
        t.addWidget(self.fwd_btn)

        self.time_label = QLabel("0:00:00 / 0:00:00", objectName="TimeLabel")
        self.time_label.setAlignment(Qt.AlignCenter)
        t.addWidget(self.time_label)

        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderMoved.connect(self.on_seek)
        t.addWidget(self.progress, stretch=1)

        self.fullscreen_btn = QPushButton(objectName="IconButton")
        self.fullscreen_btn.setText("⛶")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        t.addWidget(self.fullscreen_btn)

        self.header = QLabel("PLAYLIST", objectName="Header")
        root.addWidget(self.header)

        self.playlist = QListWidget()
        self.playlist.setFixedHeight(180)
        self.playlist.itemDoubleClicked.connect(self.on_playlist_click)
        root.addWidget(self.playlist)

        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction("Open Folder…", self.open_folder, "Ctrl+O")
        file_menu.addAction("Load Subtitle File…", self.load_subtitle_file, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close, "Ctrl+Q")

        play_menu = mb.addMenu("&Playback")
        play_menu.addAction("Play / Pause", self.toggle_play, "Space")
        play_menu.addAction("Back 10s",  lambda: self.seek_relative(-10_000), "Left")
        play_menu.addAction("Fwd 10s",   lambda: self.seek_relative(+10_000), "Right")
        play_menu.addSeparator()
        play_menu.addAction("Fullscreen", self.toggle_fullscreen, "F")

        self.audio_menu = mb.addMenu("&Audio")
        self.sub_menu   = mb.addMenu("&Subtitles")

        self.folder = None
        self.file_list = []
        self.current_file = None
        self.progress_data = {}
        self._is_seeking = False
        self._seconds_since_save = 0
        self._fullscreen = False
        self._last_a_count = -1
        self._last_s_count = -1
        self._restoring_tracks = False
        self._polling_for = None

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        self.refresh_track_menus()

    # ─────────────────── Fullscreen ───────────────────
    def toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        if self._fullscreen:
            self.menuBar().setVisible(False)
            self.header.setVisible(False)
            self.playlist.setVisible(False)
            self.showFullScreen()
        else:
            self.menuBar().setVisible(True)
            self.header.setVisible(True)
            self.playlist.setVisible(True)
            self.showNormal()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self._fullscreen:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(e)

    # ─────────────────── Progress file ───────────────────
    def progress_path(self):
        return os.path.join(self.folder, PROGRESS_FILENAME)

    def load_progress(self):
        self.progress_data = {}
        if self.folder and os.path.exists(self.progress_path()):
            try:
                with open(self.progress_path(), "r", encoding="utf-8") as f:
                    self.progress_data = json.load(f)
            except Exception as e:
                log("Could not read progress:", e)

    def save_progress(self):
        if not self.folder:
            return
        tmp = self.progress_path() + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.progress_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.progress_path())
        except Exception as e:
            log("Could not save progress:", e)

    # ─────────────────── Folder / playlist ───────────────────
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pick a folder of videos")
        if not folder:
            return
        self.save_current_progress()
        self.folder = folder
        self.load_progress()
        self.refresh_playlist()

    def refresh_playlist(self):
        self.playlist.clear()
        self.file_list = []
        if not self.folder:
            return
        for f in sorted(os.listdir(self.folder)):
            if os.path.splitext(f)[1].lower() not in VIDEO_EXTS:
                continue
            self.file_list.append(f)
            entry = self.progress_data.get(f, {})
            pos, dur = entry.get("position_ms", 0), entry.get("duration_ms", 0)
            tag = ""
            if dur > 0:
                pct = int(pos / dur * 100)
                tag = "   ✔" if pct >= 97 else f"   {pct}%"
            QListWidgetItem(f + tag, self.playlist)

    def on_playlist_click(self, item):
        idx = self.playlist.row(item)
        name = self.file_list[idx]
        self.play_video(os.path.join(self.folder, name), name)

    # ─────────────────── Playback ───────────────────
    def play_video(self, path, name):
        self.save_current_progress()
        self.current_file = name
        self._last_a_count = self._last_s_count = -1
        self._polling_for = name
        log(f"play_video: {name}")

        media = self.instance.media_new(path)
        self.player.set_media(media)
        self.attach_video()
        self.player.play()
        self._set_play_icon(True)

        self._restoring_tracks = True
        QTimer.singleShot(200, lambda: self._poll_for_tracks(name, attempts=40))

    def _poll_for_tracks(self, name, attempts):
        if self._polling_for != name:
            return

        try:
            a_descs = self.player.audio_get_track_description() or []
            s_descs = self.player.video_get_spu_description() or []
        except Exception as e:
            log("poll exception:", e)
            a_descs, s_descs = [], []

        has_real_a = any(tid != -1 for tid, _ in a_descs)
        has_real_s = any(sid != -1 for sid, _ in s_descs)

        log(f"poll [{name}] attempt={attempts} "
            f"a={[(t, tname(n)) for t, n in a_descs]} "
            f"s={[(t, tname(n)) for t, n in s_descs]}")

        if has_real_a or has_real_s or attempts <= 0:
            self.refresh_track_menus()
            self.restore_position()
            QTimer.singleShot(100, self.restore_tracks)
            return

        QTimer.singleShot(250, lambda: self._poll_for_tracks(name, attempts - 1))

    def attach_video(self):
        handle = int(self.video.winId())
        if sys.platform.startswith("win"):
            self.player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self.player.set_nsobject(handle)
        else:
            self.player.set_xwindow(handle)

    def restore_position(self, attempts=15):
        if not self.current_file:
            return
        dur = self.player.get_length()
        if dur <= 0 and attempts > 0:
            QTimer.singleShot(200, lambda: self.restore_position(attempts - 1))
            return
        entry = self.progress_data.get(self.current_file)
        if not entry:
            return
        pos = entry.get("position_ms", 0)
        if 0 < pos < dur - 5000:
            log(f"restore_position: seeking to {pos}")
            self.player.set_time(int(pos))

    def restore_tracks(self):
        if not self.current_file:
            self._restoring_tracks = False
            return

        entry = self.progress_data.get(self.current_file, {})
        saved_a_id, saved_a_name = entry.get("audio_track_id"), entry.get("audio_track_name")
        saved_s_id, saved_s_name = entry.get("sub_track_id"),   entry.get("sub_track_name")
        log(f"restore_tracks: audio=({saved_a_id},{saved_a_name!r}) "
            f"sub=({saved_s_id},{saved_s_name!r})")

        if saved_a_id is None and saved_s_id is None:
            self._restoring_tracks = False
            self.refresh_track_menus()
            return

        a_descs = self.player.audio_get_track_description() or []
        s_descs = self.player.video_get_spu_description() or []

        if saved_a_id is not None:
            tid = self._match_track(a_descs, saved_a_id, saved_a_name)
            if tid is not None:
                log(f"  → audio_set_track({tid})")
                self.player.audio_set_track(tid)

        if saved_s_id is not None:
            sid = self._match_track(s_descs, saved_s_id, saved_s_name)
            if sid is not None:
                log(f"  → video_set_spu({sid})")
                self.player.video_set_spu(sid)

        self._restoring_tracks = False
        self.refresh_track_menus()

    @staticmethod
    def _match_track(descriptions, saved_id, saved_name):
        # Prefer name (str vs str). Fall back to numeric id.
        if saved_name:
            for tid, raw in descriptions:
                if tname(raw) == saved_name:
                    return tid
        if saved_id is not None:
            for tid, _ in descriptions:
                if tid == saved_id:
                    return tid
        return None

    def save_current_progress(self):
        if not self.current_file:
            return
        pos, dur = self.player.get_time(), self.player.get_length()
        if dur <= 0:
            return
        entry = self.progress_data.setdefault(self.current_file, {})
        entry.update({
            "position_ms": pos,
            "duration_ms": dur,
            "last_played": time.time(),
            "completed": pos >= dur - 5000,
        })
        self.save_progress()

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self._set_play_icon(False)
            self.save_current_progress()
        else:
            self.player.play()
            self._set_play_icon(True)

    def _set_play_icon(self, playing):
        icon = (QStyle.SP_MediaPause if playing else QStyle.SP_MediaPlay)
        self.play_btn.setIcon(self.style().standardIcon(icon))

    def seek_relative(self, delta_ms):
        if not self.current_file:
            return
        t, dur = self.player.get_time(), self.player.get_length()
        if dur > 0:
            self.player.set_time(max(0, min(dur, t + delta_ms)))

    def on_seek(self, value):
        if self._is_seeking or not self.current_file:
            return
        dur = self.player.get_length()
        if dur > 0:
            self.player.set_time(int(value / 1000 * dur))

    # ─────────────────── Track menus ───────────────────
    def refresh_track_menus(self):
        # ── Audio ──
        self.audio_menu.clear()
        try:
            current_a = self.player.audio_get_track()
            descs = self.player.audio_get_track_description() or []
        except Exception:
            descs, current_a = [], -1

        real_a = [(tid, tname(name)) for tid, name in descs if tid != -1]
        if real_a:
            grp = QActionGroup(self); grp.setExclusive(True)
            for tid, raw in descs:
                name = tname(raw)
                label = "Disable" if tid == -1 else (name or f"Track {tid}")
                act = QAction(label, self, checkable=True)
                act.setChecked(tid == current_a)
                act.triggered.connect(
                    lambda _=False, t=tid, n=name: self.set_audio_track(t, n))
                grp.addAction(act)
                self.audio_menu.addAction(act)
        else:
            a = QAction("(no audio tracks)", self); a.setEnabled(False)
            self.audio_menu.addAction(a)

        self.audio_menu.addSeparator()
        self.audio_menu.addAction("Refresh Tracks", self.refresh_track_menus)

        # ── Subtitles ──
        self.sub_menu.clear()
        try:
            current_s = self.player.video_get_spu()
            subs = self.player.video_get_spu_description() or []
        except Exception:
            subs, current_s = [], -1

        real_s = [(sid, tname(name)) for sid, name in subs if sid != -1]
        if real_s:
            grp = QActionGroup(self); grp.setExclusive(True)
            for sid, raw in subs:
                name = tname(raw)
                label = "Disable" if sid == -1 else (name or f"Subtitle {sid}")
                act = QAction(label, self, checkable=True)
                act.setChecked(sid == current_s)
                act.triggered.connect(
                    lambda _=False, s=sid, n=name: self.set_sub_track(s, n))
                grp.addAction(act)
                self.sub_menu.addAction(act)
        else:
            a = QAction("(no embedded subtitles)", self); a.setEnabled(False)
            self.sub_menu.addAction(a)

        self.sub_menu.addSeparator()
        self.sub_menu.addAction("Load Subtitle File…", self.load_subtitle_file)
        self.sub_menu.addAction("Refresh Tracks", self.refresh_track_menus)

    # ─────────────────── Track change → persist ───────────────────
    def set_audio_track(self, tid, name):
        log(f"set_audio_track({tid}, {name!r})")
        self.player.audio_set_track(tid)
        if self.current_file:
            entry = self.progress_data.setdefault(self.current_file, {})
            entry["audio_track_id"]   = tid
            entry["audio_track_name"] = tname(name)
            self.save_progress()

    def set_sub_track(self, sid, name):
        log(f"set_sub_track({sid}, {name!r})")
        self.player.video_set_spu(sid)
        if self.current_file:
            entry = self.progress_data.setdefault(self.current_file, {})
            entry["sub_track_id"]   = sid
            entry["sub_track_name"] = tname(name)
            self.save_progress()

    def load_subtitle_file(self):
        if not self.current_file:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a subtitle file", self.folder or "", SUBTITLE_FILTER)
        if not path:
            return
        ok = self.player.video_set_subtitle_file(path)
        if not ok:
            media = self.instance.media_new(
                os.path.join(self.folder, self.current_file))
            media.add_option(f"sub-file={path}")
            pos = self.player.get_time()
            self.player.set_media(media)
            self.player.play()
            QTimer.singleShot(300, lambda: self.player.set_time(pos))
        entry = self.progress_data.setdefault(self.current_file, {})
        entry["external_sub_file"] = os.path.basename(path)
        self.save_progress()
        QTimer.singleShot(500, self.refresh_track_menus)

    # ─────────────────── Main loop ───────────────────
    def tick(self):
        if self.current_file:
            pos, dur = self.player.get_time(), self.player.get_length()
            if dur > 0:
                self._is_seeking = True
                self.progress.setValue(int(pos / dur * 1000))
                self._is_seeking = False
            self.time_label.setText(f"{fmt(pos)} / {fmt(dur)}")

            if self.player.is_playing():
                self._seconds_since_save += 1
                if self._seconds_since_save >= SAVE_EVERY:
                    self._seconds_since_save = 0
                    self.save_current_progress()

            if not self._restoring_tracks:
                try:
                    a_count = self.player.audio_get_track_count()
                    s_count = self.player.video_get_spu_count()
                except Exception:
                    a_count = s_count = -1
                if a_count != self._last_a_count or s_count != self._last_s_count:
                    self._last_a_count, self._last_s_count = a_count, s_count
                    log(f"count-watcher: a={a_count} s={s_count}")
                    self.refresh_track_menus()

    def closeEvent(self, e):
        self.save_current_progress()
        self.player.stop()
        super().closeEvent(e)


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    win = PlayerWindow()
    win.show()
    sys.exit(app.exec())