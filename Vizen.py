import sys, requests, os, ctypes, time, json, subprocess, hashlib
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QObject, QRunnable, QThreadPool, QSize, qInstallMessageHandler, QUrl
from PySide6.QtGui import QPixmap, QImage, QFont, QColor, QIcon, QIntValidator, QDesktopServices
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QFileDialog, QInputDialog

from qfluentwidgets import (MSFluentWindow, NavigationItemPosition, TitleLabel, 
                            CaptionLabel, SearchLineEdit, FlowLayout, SegmentedWidget, 
                            FluentIcon as FIF, CardWidget, ComboBox, BodyLabel, PushButton, 
                            SmoothScrollArea, RoundMenu, Action, SubtitleLabel, 
                            TextBrowser, MessageBox, setTheme, Theme, 
                            TransparentToolButton, InfoBar, InfoBarPosition, ProgressBar, 
                            SwitchButton, SettingCardGroup, SwitchSettingCard, 
                            PushSettingCard, SettingCard, MessageBoxBase)

from api_handler import TMDBService
from database import DatabaseHandler

# --- GLOBALS ---
CURRENT_VERSION = "1.2.4"
GITHUB_REPO = "xHashii/Vizen-Watchlist"
IMAGE_CACHE = {}  
AMOLED_MODE = False 
ACCENT_PINK = "#ff4da6"
ACCENT_YELLOW = "#ffcc33"

CACHE_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'Vizen', 'Cache')
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)

# --- UTILS ---
def qt_message_handler(mode, context, message):
    if "setPointSize" in message or "pointSize" in message: return

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def get_bg(): return "#000000" if AMOLED_MODE else "#1a1625"
def get_card_bg(): return "#121212" if AMOLED_MODE else "#252033"

def apply_font_guard(widget):
    f = QFont("Segoe UI", 10); f.setPixelSize(14)
    widget.setFont(f)
    for child in widget.findChildren(QWidget): child.setFont(f)

def get_cached_pixmap(url, w, h):
    """Checks memory and disk cache synchronously. Returns QPixmap or None."""
    if not url: return None
    if url in IMAGE_CACHE:
        return QPixmap.fromImage(IMAGE_CACHE[url])
    
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{url_hash}.jpg")
    
    if os.path.exists(cache_path):
        img = QImage(cache_path)
        if not img.isNull():
            scaled = img.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            IMAGE_CACHE[url] = scaled
            return QPixmap.fromImage(scaled)
    return None

# --- UPDATER ENGINE ---
class UpdateWorker(QThread):
    finished = Signal(str)
    progress = Signal(int)
    def __init__(self, url):
        super().__init__(); self.url = url
    def run(self):
        try:
            timestamp = int(time.time())
            path = os.path.join(os.environ['TEMP'], f"Vizen_Setup_{timestamp}.exe")
            response = requests.get(self.url, stream=True, timeout=30)
            total = int(response.headers.get('content-length', 0))
            dl = 0
            with open(path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    if chunk:
                        dl += len(chunk); f.write(chunk)
                        if total: self.progress.emit(int((dl / total) * 100))
            self.finished.emit(path)
        except: pass

class UpdateChecker(QThread):
    update_available = Signal(str, str)
    def run(self):
        try:
            res = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=10).json()
            tag = res['tag_name']
            new_v_str = tag.replace('v', '')
            remote_v = list(map(int, new_v_str.split('.')))
            local_v = list(map(int, CURRENT_VERSION.split('.')))
            if remote_v > local_v:
                for a in res['assets']:
                    if a['name'].endswith('.exe'):
                        self.update_available.emit(new_v_str, a['browser_download_url']); return
        except: pass

class MigrationWorker(QThread):
    finished = Signal()
    def __init__(self, db, tmdb):
        super().__init__()
        self.db = db
        self.tmdb = tmdb

    def run(self):
        incomplete_ids = self.db.get_incomplete_dramas()
        if not incomplete_ids:
            return

        for tid in incomplete_ids:
            detail = self.tmdb.get_detailed_info(tid)
            if detail:
                # We fetch existing status/ep from DB so we don't overwrite them
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT status, current_ep FROM dramas WHERE tmdb_id = ?", (tid,))
                row = cursor.fetchone()
                if row:
                    status, current_ep = row
                    self.db.add_drama(detail, status, current_ep)
            time.sleep(0.2) # Avoid hitting API rate limits
        self.finished.emit()

# --- IMAGE ENGINE ---
class ImageWorkerSignals(QObject): result = Signal(QImage, str)
class ImageWorker(QRunnable):
    def __init__(self, url, w, h):
        super().__init__(); self.url, self.w, self.h = url, w, h
        self.signals = ImageWorkerSignals()
    def run(self):
        if self.url in IMAGE_CACHE: self._safe_emit(IMAGE_CACHE[self.url]); return
        url_hash = hashlib.md5(self.url.encode()).hexdigest()
        cache_path = os.path.join(CACHE_DIR, f"{url_hash}.jpg")
        img = QImage()
        if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < 1209600:
            img.load(cache_path)
        if img.isNull():
            try:
                resp = requests.get(self.url, timeout=7)
                img.loadFromData(resp.content); img.save(cache_path, "JPG", 80)
            except:
                if os.path.exists(cache_path): img.load(cache_path)
                else: return
        if not img.isNull():
            scaled = img.scaled(self.w, self.h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            IMAGE_CACHE[self.url] = scaled; self._safe_emit(scaled)
    def _safe_emit(self, image):
        try: self.signals.result.emit(image, self.url)
        except RuntimeError: pass 

# --- UI COMPONENTS ---
class DetailWorker(QThread):
    finished = Signal(dict)
    def __init__(self, tmdb, tid): 
        super().__init__()
        self.tmdb, self.tid = tmdb, tid
        
    def run(self):
        res = self.tmdb.get_detailed_info(self.tid)
        if res:
            if res.get('streaming'):
                for s in res['streaming']:
                    if s.get('logo'):
                        worker = ImageWorker(s['logo'], 48, 48)
                        worker.run()
            self.finished.emit(res)

class InfoDialog(MessageBoxBase):
    def __init__(self, d, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(d['title'], self)
        self.titleLabel.setStyleSheet("font-size: 22px; font-weight: bold; color: white; border: none;")
        genres = " • ".join(d.get('genres', []))
        self.metaLabel = CaptionLabel(f"{d['year']}  •  {d['total_eps']} Episodes\n{genres}", self)
        self.metaLabel.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold; font-size: 13px; border: none;")
        self.content = TextBrowser(self)
        self.content.setMarkdown(f"**Cast:** {', '.join(d['cast'])}\n\n{d['overview']}")
        self.content.setFixedHeight(250)
        self.content.setStyleSheet("background: transparent; border: none; color: #d0d0d0; font-size: 14px;")
        self.content.setFrameStyle(QFrame.NoFrame) 
        self.viewLayout.addWidget(self.titleLabel); self.viewLayout.addWidget(self.metaLabel); self.viewLayout.addWidget(self.content)

        if d.get('streaming'):
            self.streamLabel = CaptionLabel("Watch on:", self)
            self.streamLabel.setStyleSheet("border: none; font-weight: bold; color: white; margin-top: 10px;")
            self.viewLayout.addWidget(self.streamLabel)
            
            self.stream_container = QWidget()
            self.stream_container.setStyleSheet("background: transparent; border: none;")
            stream_layout = QHBoxLayout(self.stream_container)
            stream_layout.setContentsMargins(0, 5, 0, 5); stream_layout.setSpacing(15) # Increased spacing
            
            for s in d['streaming']:
                if not s['logo']: continue
                btn = TransparentToolButton(self)
                btn.setToolTip(s['name'])
                
                
                btn.setFixedSize(56, 56)
                btn.setIconSize(QSize(48, 48))
                
                
                btn.clicked.connect(lambda checked, url=s['url']: QDesktopServices.openUrl(QUrl(url)))
                
                # Try cache first with new 48x48 size
                cached_pix = get_cached_pixmap(s['logo'], 48, 48)
                if cached_pix:
                    btn.setIcon(QIcon(cached_pix))
                else:
                    # Fallback worker with new 48x48 size
                    logo_worker = ImageWorker(s['logo'], 48, 48)
                    logo_worker.signals.result.connect(lambda img, u, b=btn: b.setIcon(QIcon(QPixmap.fromImage(img))))
                    QThreadPool.globalInstance().start(logo_worker)
                
                stream_layout.addWidget(btn)
            
            stream_layout.addStretch(1)
            self.viewLayout.addWidget(self.stream_container)

        self.yesButton.setText("Close"); self.yesButton.setFixedWidth(120); self.yesButton.setFocusPolicy(Qt.NoFocus)
        self.yesButton.setStyleSheet(f"PushButton {{ background-color: #20f0ff; color: black; border: none; border-radius: 8px; font-weight: bold; height: 32px; }} PushButton:hover {{ background-color: #1ad8e6; }}")
        self.cancelButton.hide(); self.cancelButton.setEnabled(False)
        self.widget.setStyleSheet(f"QWidget {{ background-color: {get_card_bg()}; border: 1px solid {ACCENT_PINK}; border-radius: 12px; }} #buttonGroup {{ border: none; background: transparent; }}")
        for child in self.widget.findChildren(QFrame):
            if child.height() <= 3: child.hide()
        self.viewLayout.setContentsMargins(25, 25, 25, 15); apply_font_guard(self)

class HeartRating(QWidget):
    valueChanged = Signal(int)
    def __init__(self, parent=None, rating=0):
        super().__init__(parent); self.rating = rating; self.hearts = []
        l = QHBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(4)
        icon = FIF.HEART if hasattr(FIF, 'HEART') else FIF.FAVORITE
        for i in range(1, 6):
            btn = TransparentToolButton(icon, self); btn.setFixedSize(30,30); btn.setIconSize(QSize(22,22))
            btn.clicked.connect(lambda c, v=i: self.set_rating(v))
            self.hearts.append(btn); l.addWidget(btn)
        self.update_hearts()
    def set_rating(self, v): self.rating = v; self.update_hearts(); self.valueChanged.emit(v)
    def update_hearts(self):
        icon = FIF.HEART if hasattr(FIF, 'HEART') else FIF.FAVORITE
        for i, b in enumerate(self.hearts):
            color = ACCENT_PINK if i < self.rating else "#3d3654"
            b.setIcon(icon.icon(color=QColor(color)))
            b.setStyleSheet("QToolButton{border:none;background:transparent;border-radius:15px;} QToolButton:hover{background:rgba(255,77,166,0.15);}")

class DramaCard(CardWidget):
    def __init__(self, d, db, tmdb, parent=None, is_lib=False, on_refresh=None):
        super().__init__(parent=parent)
        self.db, self.tmdb, self.data, self.is_lib, self.on_refresh = db, tmdb, d, is_lib, on_refresh
        self.setFixedSize(210, 520 if is_lib else 360); self.update_style(); self.setCursor(Qt.PointingHandCursor)
        l = QVBoxLayout(self); l.setContentsMargins(10,10,10,10); l.setSpacing(8)
        self.img = BodyLabel(self); self.img.setFixedSize(190, 260); self.img.setStyleSheet("border-radius:8px;background:#0d0d0d;")
        if d.get('poster'):
            w = ImageWorker(d['poster'], 190, 260); w.signals.result.connect(self._set_image_safe)
            QThreadPool.globalInstance().start(w)
        l.addWidget(self.img)
        if is_lib:
            self.pb = ProgressBar(self); self.pb.setFixedHeight(4); self.update_pb(); l.addWidget(self.pb)
        self.title = BodyLabel(d['title'], self); self.title.setStyleSheet("color:white;font-weight:bold;font-size:13px;"); self.title.setWordWrap(True)
        l.addWidget(self.title); l.addStretch(1)
        if is_lib:
            self.rw = HeartRating(self, d.get('rating', 0)); self.rw.valueChanged.connect(lambda v: self.db.update_rating(self.data['id'], v))
            l.addWidget(self.rw)
        self.btn = PushButton("Status" if is_lib else "Add to List", self); self.btn.clicked.connect(self.show_menu); l.addWidget(self.btn)
        if is_lib:
            h = QHBoxLayout(); self.ee = QLineEdit(str(d.get('current_ep', 0)), self); self.ee.setFixedWidth(40); self.ee.setAlignment(Qt.AlignCenter)
            self.ee.setValidator(QIntValidator(0, 9999)); self.ee.setStyleSheet(f"background:rgba(0,0,0,0.3);color:{ACCENT_YELLOW};border:1px solid #444;border-radius:4px;")
            self.ee.returnPressed.connect(lambda: self.up_logic(int(self.ee.text() or 0)))
            p = TransparentToolButton(FIF.ADD, self); p.clicked.connect(lambda: self.up_logic(self.data['current_ep']+1))
            h.addWidget(CaptionLabel("Ep:")); h.addWidget(self.ee); h.addWidget(CaptionLabel(f"/ {d.get('total_eps','?')}")); h.addWidget(p); l.addLayout(h)
            self.dbtn = TransparentToolButton(FIF.DELETE, self); self.dbtn.clicked.connect(lambda: [self.db.delete_drama(self.data['id']), self.on_refresh() if self.on_refresh else None]); l.addWidget(self.dbtn, 0, Qt.AlignCenter)

    def _set_image_safe(self, image, url):
        try:
            if not self.img.isHidden(): self.img.setPixmap(QPixmap.fromImage(image))
        except RuntimeError: pass

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            clicked_widget = self.childAt(e.position().toPoint())
            ignore = [self.btn]
            if hasattr(self, 'dbtn'): ignore.append(self.dbtn)
            if hasattr(self, 'ee'): ignore.append(self.ee)
            if clicked_widget not in ignore:
                self.dw = DetailWorker(self.tmdb, self.data['id'])
                self.dw.finished.connect(lambda d: InfoDialog(d, self.window()).exec())
                self.dw.start()
        super().mousePressEvent(e)

    def update_style(self): self.setStyleSheet(f"DramaCard{{background:{get_card_bg()};border:1px solid #333;border-radius:12px;}} DramaCard:hover{{border:1px solid {ACCENT_PINK};}}")
    def update_pb(self):
        t, c = self.data.get('total_eps', 0), self.data.get('current_ep', 0)
        self.pb.setValue(int((c/t)*100) if t > 0 else 0)
    def show_menu(self):
        m = RoundMenu(parent=self)
        for s in ["watching", "plan", "completed"]: m.addAction(Action(s.title(), self, triggered=lambda checked, x=s: self.handle_status(x)))
        m.exec(self.btn.mapToGlobal(self.btn.rect().bottomLeft()))
    def handle_status(self, s):
        if self.is_lib:
            c = self.data['total_eps'] if s == "completed" else self.data['current_ep']
            self.db.update_status(self.data['id'], s, c)
            if self.on_refresh: self.on_refresh()
        else:
            det = self.tmdb.get_detailed_info(self.data['id'])
            if det:
                c = det['total_eps'] if s == "completed" else 0
                self.db.add_drama(det, s, c)
                if self.on_refresh: self.on_refresh()
                InfoBar.success("Added", f"Moved to {s}", parent=self.window())
    def up_logic(self, v):
        t = self.data.get('total_eps', 999); n = max(0, min(v, t))
        self.db.update_episode(self.data['id'], n); self.data['current_ep'] = n; self.ee.setText(str(n)); self.update_pb()
        if n == t and t > 0 and self.data['status'] != 'completed': 
            self.db.update_status(self.data['id'], 'completed', n)
            if self.on_refresh: QTimer.singleShot(300, self.on_refresh)

# --- INTERFACES ---
class BaseInterface(QFrame):
    def __init__(self, db, tmdb, obj_name, parent=None):
        super().__init__(parent=parent); self.setObjectName(obj_name); self.db, self.tmdb = db, tmdb
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 30, 15, 80); self.main_layout.setSpacing(20)
        self.header_layout = QVBoxLayout()
        self.main_layout.addLayout(self.header_layout)
        self.sa = SmoothScrollArea(self); self.sa.setWidgetResizable(True); self.sa.setStyleSheet("background:transparent;border:none;")
        self.container = QWidget(); self.container.setStyleSheet("background:transparent;")
        self.flow = FlowLayout(self.container); self.flow.setContentsMargins(0,0,0,0); self.flow.setHorizontalSpacing(12); self.flow.setVerticalSpacing(25)
        self.sa.setWidget(self.container)
        self.emptyLabel = BodyLabel("No dramas found.", self) 
        self.emptyLabel.setAlignment(Qt.AlignCenter); self.emptyLabel.setStyleSheet("color: #666; font-size: 20px; font-weight: bold; background: transparent;"); self.emptyLabel.hide()
        self.main_layout.addWidget(self.emptyLabel, 1)
        self.main_layout.addWidget(self.sa, 1)
        self.current_page = 1; self.total_pages = 1; self.is_loading_more = False
        self.last_query = None; self.last_genre = None; self.last_country = None
        self.sa.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.queue = []; self.timer = QTimer(self); self.timer.timeout.connect(self.process)

    def _on_scroll(self, value):
        if value > self.sa.verticalScrollBar().maximum() * 0.9 and not self.is_loading_more:
            if self.current_page < self.total_pages: self.load_next_page()

    def load_next_page(self):
        self.is_loading_more = True
        self.current_page += 1
        if hasattr(self, 'search'): self.search(self.last_query, append=True)

    def start_loading(self, items, is_lib=False, cb=None, append=False):
        self.timer.stop(); self.is_lib, self.cb = is_lib, cb
        if not append:
            self.queue = items
            while self.flow.count() > 0:
                it = self.flow.takeAt(0)
                w = it.widget() if hasattr(it, 'widget') else it
                if w: w.deleteLater()
        else:
            self.queue.extend(items)
        if not items and not append: self.sa.hide(); self.emptyLabel.show()
        else: self.emptyLabel.hide(); self.sa.show(); self.timer.start(5)

    def process(self):
        if not self.queue: 
            self.timer.stop()
            self.is_loading_more = False
            return
        self.flow.addWidget(DramaCard(self.queue.pop(0), self.db, self.tmdb, self.container, self.is_lib, self.cb))

class BrowseInterface(BaseInterface):
    def __init__(self, db, tmdb, parent=None):
        super().__init__(db, tmdb, "browseInterface", parent)
        h = QHBoxLayout()
        h.addWidget(TitleLabel("Browse Asian Dramas"))
        h.addStretch(1)
        self.genreCombo = ComboBox(self); self.genreCombo.addItem("All Genres", userData=None)
        for name, val in self.tmdb.genre_map.items(): self.genreCombo.addItem(name, userData=val)
        self.genreCombo.currentIndexChanged.connect(lambda: self.search(self.sb.text()))
        self.countryCombo = ComboBox(self); self.countryCombo.addItems(["All Regions", "KR", "JP", "CN", "TH", "TW"])
        self.countryCombo.currentIndexChanged.connect(lambda: self.search(self.sb.text()))
        self.sb = SearchLineEdit(self); self.sb.setPlaceholderText("Search TMDB..."); self.sb.setFixedWidth(350)
        self.sb.searchSignal.connect(self.search)
        self.sb.returnPressed.connect(lambda: self.search(self.sb.text()))
        h.addWidget(self.genreCombo); h.addWidget(self.countryCombo); h.addWidget(self.sb)
        self.header_layout.addLayout(h)

    def search(self, q, append=False):
        if not append:
            self.current_page = 1; self.last_query = q
            self.last_genre = self.genreCombo.currentData()
            self.last_country = self.countryCombo.currentText() if self.countryCombo.currentText() != "All Regions" else None
        results, total = self.tmdb.search_dramas(self.last_query, self.last_genre, self.last_country, self.current_page)
        self.total_pages = total
        self.start_loading(results, append=append)

    def load_next_page(self):
        self.search(self.last_query, append=True)

class LibraryInterface(BaseInterface):
    def __init__(self, db, tmdb, parent=None):
        super().__init__(db, tmdb, "libraryInterface", parent)
        h = QHBoxLayout()
        h.addWidget(TitleLabel("My Library"))
        h.addStretch(1)
        
        # Genre Filter
        self.libGenreCombo = ComboBox(self); self.libGenreCombo.setFixedWidth(150); self.libGenreCombo.addItem("All Genres")
        for name in self.tmdb.genre_map.keys(): self.libGenreCombo.addItem(name)
        self.libGenreCombo.currentIndexChanged.connect(self.refresh)
        
        # Country Filter (NEW)
        self.libCountryCombo = ComboBox(self); self.libCountryCombo.setFixedWidth(120); self.libCountryCombo.addItem("All Regions")
        self.libCountryCombo.addItems(["KR", "JP", "CN", "TH", "TW"])
        self.libCountryCombo.currentIndexChanged.connect(self.refresh)

        self.libSearch = SearchLineEdit(self); self.libSearch.setPlaceholderText("Search list..."); self.libSearch.setFixedWidth(200)
        self.libSearch.textChanged.connect(self.refresh)
        
        h.addWidget(self.libGenreCombo); h.addWidget(self.libCountryCombo); h.addWidget(self.libSearch)
        self.header_layout.addLayout(h)
        self.piv = SegmentedWidget(self); [self.piv.addItem(k, k.title().replace('Plan', 'Plan to Watch')) for k in ["all", "watching", "plan", "completed"]]
        self.piv.setCurrentItem("all"); self.piv.currentItemChanged.connect(self.refresh); self.header_layout.addWidget(self.piv, 0, Qt.AlignLeft)

    def refresh(self):
        status = self.piv.currentItem().text().replace('Plan to Watch', 'plan').lower()
        search_q = self.libSearch.text().lower()
        genre_q = self.libGenreCombo.currentText()
        country_q = self.libCountryCombo.currentText() # NEW
        
        items = self.db.get_library(
            status_filter=status, 
            search_q=search_q, 
            genre_filter=genre_q, 
            country_filter=country_q
        )
        self.start_loading(items, True, self.refresh)

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Backup", "", "JSON (*.json)")
        if path: self.db.export_data(path); InfoBar.success("Export Successful", f"Saved to {os.path.basename(path)}", duration=3000, parent=self.window())

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Backup", "", "JSON (*.json)")
        if path:
            if self.db.import_data(path): self.refresh(); InfoBar.success("Import Successful", "Library updated.", duration=3000, parent=self.window())
            else: InfoBar.error("Import Failed", "Invalid JSON file.", duration=3000, parent=self.window())

class SettingsInterface(SmoothScrollArea):
    def __init__(self, db, parent=None):
        super().__init__(parent=parent); self.db = db; self.setObjectName("settingsInterface")
        self.view = QWidget(); l = QVBoxLayout(self.view); l.setContentsMargins(30,30,30,30); l.setSpacing(20)
        self.setWidget(self.view); self.setWidgetResizable(True); self.setStyleSheet("background:transparent;border:none;")
        g1 = SettingCardGroup("About", self.view); l.addWidget(g1)
        g1.addSettingCard(SettingCard(FIF.INFO, "Version", f"Current: {CURRENT_VERSION}"))
        c1 = PushSettingCard("Visit GitHub", FIF.PEOPLE, "Developer", "Made with ❤️ by Hashii")
        c1.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}"))); g1.addSettingCard(c1)
        g2 = SettingCardGroup("API Settings", self.view); l.addWidget(g2)
        c2 = PushSettingCard("Update", FIF.VPN, "Custom TMDB Key", "Use your own key if the default is slow")
        c2.clicked.connect(self.change_key); g2.addSettingCard(c2)
        g3 = SettingCardGroup("Personalization", self.view); l.addWidget(g3)
        c3 = SwitchSettingCard(FIF.BRUSH, "AMOLED Mode", "Pure black background")
        c3.switchButton.setChecked(AMOLED_MODE); c3.checkedChanged.connect(self.toggle_amoled); g3.addSettingCard(c3)
        g4 = SettingCardGroup("Data & Backup", self.view); l.addWidget(g4)
        i, e, c = PushSettingCard("Import", FIF.UP, "Import Backup", "Load JSON"), PushSettingCard("Export", FIF.DOWNLOAD, "Export Backup", "Save JSON"), PushSettingCard("Clear", FIF.DELETE, "Clear Cache", "Free RAM")
        i.clicked.connect(lambda: self.window().library.import_json())
        e.clicked.connect(lambda: self.window().library.export_data())
        c.clicked.connect(self.clear_cache)
        [g4.addSettingCard(x) for x in [i, e, c]]; l.addStretch(1)
    def toggle_amoled(self, c): global AMOLED_MODE; AMOLED_MODE = c; self.window().apply_theme()
    def clear_cache(self): 
        global IMAGE_CACHE; IMAGE_CACHE.clear()
        for f in os.listdir(CACHE_DIR): 
            try: os.remove(os.path.join(CACHE_DIR, f))
            except: pass
        InfoBar.success("Success", "Cache cleared", parent=self.window())
    def change_key(self):
        t, ok = QInputDialog.getText(self, "API Key", "Enter TMDB Bearer Token:", QLineEdit.Normal)
        if ok and t:
            path = os.path.join(os.environ['LOCALAPPDATA'], 'Vizen', 'config.json')
            with open(path, "w") as f: json.dump({"api_key": t}, f)
            InfoBar.success("Success", "Restart app to apply.", parent=self.window())

class VizenWindow(MSFluentWindow):
    def __init__(self):
        super().__init__(); setTheme(Theme.DARK); self.db, self.tmdb = DatabaseHandler(), TMDBService()
        QThreadPool.globalInstance().setMaxThreadCount(8)
        self.browse, self.library, self.settings = BrowseInterface(self.db, self.tmdb), LibraryInterface(self.db, self.tmdb), SettingsInterface(self.db, self)
        self.addSubInterface(self.browse, FIF.SEARCH, "Browse")
        self.addSubInterface(self.library, FIF.VIDEO, "Library")
        self.addSubInterface(self.settings, FIF.SETTING, "Settings", position=NavigationItemPosition.BOTTOM)
        logo = resource_path("logo.png")
        if os.path.exists(logo): self.setWindowIcon(QIcon(logo))
        self.setWindowTitle("Vizen Watchlist"); self.resize(1300, 850); self.center(); self.apply_theme()
        self.stackedWidget.currentChanged.connect(lambda i: self.library.refresh() if i==1 else None)
        self.check_updates()
        self.run_migration()
    def run_migration(self):
        self.migrator = MigrationWorker(self.db, self.tmdb)
        # Refresh library once migration finishes so user sees the updated data
        self.migrator.finished.connect(lambda: self.library.refresh())
        self.migrator.start()
    def center(self):
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr = self.frameGeometry(); qr.moveCenter(cp); self.move(qr.topLeft())
    def apply_theme(self):
        bg = get_bg(); self.setStyleSheet(f"MSFluentWindow, QStackedWidget {{ background: {bg}; }}")
        [x.setStyleSheet(f"background:{bg};border:none;") for x in [self.browse, self.library, self.settings.view]]
        for c in self.findChildren(DramaCard): c.update_style()
    def check_updates(self):
        self.checker = UpdateChecker(self); self.checker.update_available.connect(self.prompt_update); self.checker.start()
    def prompt_update(self, v, u):
        msg = MessageBox("Update Found! 🚀", f"Version {v} is available. Install now?", self)
        msg.yesButton.setText("Update Now"); msg.cancelButton.setText("Later")
        if msg.exec(): self.start_download(u)
    def start_download(self, u):
        self.dlg = MessageBox("Downloading Update...", "Please wait.", self); self.p = ProgressBar(self.dlg); self.p.setFixedHeight(4)
        self.dlg.viewLayout.addWidget(self.p); self.dlg.yesButton.hide(); self.dlg.show()
        self.updater_worker = UpdateWorker(u); self.updater_worker.progress.connect(self.p.setValue); self.updater_worker.finished.connect(self.install_update); self.updater_worker.start()
    def install_update(self, p):
        self.dlg.close()
        if os.path.exists(p):
            subprocess.Popen([p, "/SILENT", "/SP-", "/SUPPRESSMSGBOXES"], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
            QApplication.quit()

if __name__ == "__main__":
    qInstallMessageHandler(qt_message_handler)
    app = QApplication(sys.argv); f = QFont("Segoe UI", 10); f.setPixelSize(14); app.setFont(f)
    logo = resource_path("logo.png")
    if os.path.exists(logo): app.setWindowIcon(QIcon(logo))
    w = VizenWindow(); w.show(); sys.exit(app.exec())