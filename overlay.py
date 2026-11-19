"""悬浮字幕窗口 - 置顶、半透明、可拖动"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QColorDialog, QFontDialog,
    QMenu, QAction, QSystemTrayIcon, QStyle
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QIcon, QCursor


class SubtitleOverlay(QWidget):
    """悬浮字幕窗"""

    LANGS = [
        ('lebanon', '黎巴嫩 (阿拉伯语)'),
        ('philippines', '菲律宾 (他加禄语)'),
        ('bangladesh', '孟加拉 (孟加拉语)'),
        ('korea', '韩国 (韩语)'),
        ('english', '英语'),
    ]

    def __init__(self):
        super().__init__()

        # 窗口属性：无边框、置顶、半透明背景
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # 不在 Dock/任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 字幕历史
        self._history = []
        self._max_history = 3

        # 拖动
        self._drag_pos = None

        # 默认位置：屏幕底部居中
        screen = QApplication.primaryScreen().availableGeometry()
        default_w = 900
        default_h = 180
        self.setGeometry(
            (screen.width() - default_w) // 2,
            screen.height() - default_h - 60,
            default_w, default_h
        )

        # 样式
        self.bg_color = QColor(0, 0, 0, 160)  # 半透明黑
        self.text_color = QColor(255, 255, 255)
        self.translated_color = QColor(120, 220, 255)
        self.font = QFont("PingFang SC", 18, QFont.Bold)
        self.opacity = 0.95

        self._build_ui()
        self._setup_tray()

    def _build_ui(self):
        # 主容器
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(4)

        # 历史字幕（淡出显示）
        self.history_labels = []
        for _ in range(self._max_history):
            lbl = QLabel("")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            font = QFont(self.font)
            font.setPointSize(font.pointSize() - 4)
            lbl.setFont(font)
            lbl.setStyleSheet("color: rgba(200,200,200,120);")
            lbl.hide()
            self.history_labels.append(lbl)
            layout.addWidget(lbl)

        # 原文标签
        self.original_label = QLabel("等待语音...")
        self.original_label.setAlignment(Qt.AlignCenter)
        self.original_label.setWordWrap(True)
        self.original_label.setFont(self.font)
        self.original_label.setStyleSheet("color: white;")
        layout.addWidget(self.original_label)

        # 译文标签
        trans_font = QFont(self.font)
        trans_font.setPointSize(trans_font.pointSize() + 2)
        trans_font.setBold(True)
        self.translated_label = QLabel("")
        self.translated_label.setAlignment(Qt.AlignCenter)
        self.translated_label.setWordWrap(True)
        self.translated_label.setFont(trans_font)
        self.translated_label.setStyleSheet("color: rgb(120,220,255);")
        layout.addWidget(self.translated_label)

        # 底部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # 语言选择
        self.lang_combo = QComboBox()
        for key, label in self.LANGS:
            self.lang_combo.addItem(label, key)
        self.lang_combo.setFixedHeight(26)
        self.lang_combo.setStyleSheet(
            "QComboBox { background: rgba(255,255,255,30); color: white; "
            "border: 1px solid rgba(255,255,255,60); border-radius: 4px; padding: 2px 8px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #333; color: white; selection-background-color: #555; }"
        )
        toolbar.addWidget(self.lang_combo)

        # 不透明度滑块
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(int(self.opacity * 100))
        self.opacity_slider.setFixedWidth(100)
        self.opacity_slider.setFixedHeight(20)
        self.opacity_slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,60); border-radius: 2px; }"
            "QSlider::handle:horizontal { background: white; width: 12px; margin: -4px 0; border-radius: 6px; }"
        )
        self.opacity_slider.valueChanged.connect(self._on_opacity_change)
        toolbar.addWidget(self.opacity_slider)

        toolbar.addStretch()

        # 控制按钮
        btn_style = (
            "QPushButton { background: rgba(255,255,255,25); color: white; "
            "border: 1px solid rgba(255,255,255,60); border-radius: 4px; "
            "padding: 3px 10px; font-size: 12px; }"
            "QPushButton:hover { background: rgba(255,255,255,50); }"
        )

        self.toggle_btn = QPushButton("暂停")
        self.toggle_btn.setStyleSheet(btn_style)
        self.toggle_btn.setFixedHeight(26)
        toolbar.addWidget(self.toggle_btn)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setStyleSheet(btn_style)
        self.settings_btn.setFixedHeight(26)
        self.settings_btn.clicked.connect(self._show_settings_menu)
        toolbar.addWidget(self.settings_btn)

        self.close_btn = QPushButton("×")
        self.close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,80,80,150); color: white; "
            "border: none; border-radius: 4px; padding: 2px 8px; font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(255,80,80,220); }"
        )
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.clicked.connect(self.hide)
        toolbar.addWidget(self.close_btn)

        layout.addLayout(toolbar)

        self._running = True

    def _setup_tray(self):
        """系统托盘"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            icon = self.style().standardIcon(QStyle.SP_MediaPlay)
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip("实时字幕翻译")

            menu = QMenu()
            show_action = QAction("显示/隐藏", self)
            show_action.triggered.connect(self._toggle_visible)
            menu.addAction(show_action)

            quit_action = QAction("退出", self)
            quit_action.triggered.connect(QApplication.instance().quit)
            menu.addAction(quit_action)

            self.tray.setContextMenu(menu)
            self.tray.activated.connect(
                lambda reason: self._toggle_visible()
                if reason == QSystemTrayIcon.Trigger else None
            )
            self.tray.show()

    def _toggle_visible(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _on_opacity_change(self, value):
        self.opacity = value / 100.0
        self.setWindowOpacity(self.opacity)

    def _show_settings_menu(self):
        menu = QMenu(self)

        font_action = menu.addAction("字体设置")
        font_action.triggered.connect(self._change_font)

        color_action = menu.addAction("文字颜色")
        color_action.triggered.connect(self._change_color)

        reset_action = menu.addAction("重置位置")
        reset_action.triggered.connect(self._reset_position)

        menu.exec_(QCursor.pos())

    def _change_font(self):
        font, ok = QFontDialog.getFont(self.font, self, "选择字体")
        if ok:
            self.font = font
            self.original_label.setFont(font)
            trans_font = QFont(font)
            trans_font.setPointSize(font.pointSize() + 2)
            trans_font.setBold(True)
            self.translated_label.setFont(trans_font)

    def _change_color(self):
        color = QColorDialog.getColor(self.text_color, self, "选择文字颜色")
        if color.isValid():
            self.text_color = color
            self.original_label.setStyleSheet(f"color: {color.name()};")

    def _reset_position(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            screen.height() - self.height() - 60
        )

    # ===== 外部接口 =====

    def update_subtitle(self, original: str, translated: str):
        """更新字幕"""
        if not original:
            return

        # 当前内容存入历史
        current_orig = self.original_label.text()
        current_trans = self.translated_label.text()
        if current_orig and current_orig != "等待语音...":
            self._history.append((current_orig, current_trans))
            if len(self._history) > self._max_history:
                self._history.pop(0)

        # 更新历史显示
        for i, (orig, trans) in enumerate(reversed(self._history)):
            lbl = self.history_labels[i]
            lbl.setText(f"{orig}")
            lbl.show()

        # 当前字幕
        self.original_label.setText(original)
        self.translated_label.setText(translated if translated else "")

    def clear_subtitle(self):
        """清空字幕"""
        self.original_label.setText("等待语音...")
        self.translated_label.setText("")
        self._history.clear()
        for lbl in self.history_labels:
            lbl.hide()

    def get_selected_language(self) -> str:
        return self.lang_combo.currentData()

    def is_running(self) -> bool:
        return self._running

    def set_running(self, running: bool):
        self._running = running
        self.toggle_btn.setText("暂停" if running else "继续")

    # ===== 拖动支持 =====

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 只有点击空白区域才能拖动（点击标签/按钮不拖动）
            child = self.childAt(event.pos())
            if child is None or isinstance(child, QLabel):
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ===== 绘制圆角背景 =====

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 16, 16)
