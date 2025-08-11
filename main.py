
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import subprocess
import datetime
import tempfile
import shutil
import logging
import traceback
import signal
import threading
import time
import atexit
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QTextEdit, QGridLayout, QFileDialog, QDialog,
                             QLineEdit, QComboBox, QFormLayout, QMessageBox, QProgressBar,
                             QScrollArea, QFrame, QSplitter, QTabWidget, QToolButton, QMenu,
                             QAction, QListWidget, QListWidgetItem, QInputDialog, QGraphicsOpacityEffect,
                             QDesktopWidget, QShortcut, QSizePolicy, QToolTip)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QSize, QTimer, QProcess, QPropertyAnimation, 
                          QEasingCurve, QPoint, QRect, QEvent, QObject, QRectF, QT_VERSION_STR)
from PyQt5.QtGui import (QIcon, QFont, QTextCursor, QColor, QPalette, QLinearGradient, QBrush, 
                         QPainter, QPixmap, QFontDatabase, QPen, QRadialGradient, QKeySequence, QPainterPath)
import random
import math

def get_app_base_dir() -> str:
    """返回运行时可写的基础目录。
    - 开发态：使用源码所在目录
    - 打包(onefile)后：使用可执行文件所在目录（安装目录），避免写到临时解包目录导致重启丢失
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的可执行文件路径
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# 配置文件路径（统一指向可写目录）
APP_BASE_DIR = get_app_base_dir()
CONFIG_FILE = os.path.join(APP_BASE_DIR, 'config.json')
UI_SETTINGS_FILE = os.path.join(APP_BASE_DIR, 'ui_settings.json')
DELETED_COMMANDS_FILE = os.path.join(APP_BASE_DIR, 'deleted_commands.json')

# 全局动画开关（为稳定优先，默认关闭）
ANIMATIONS_ENABLED = False

# 日志配置
LOG_DIR = os.path.join(APP_BASE_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'crash_log.txt')
HEARTBEAT_FILE = os.path.join(LOG_DIR, 'heartbeat.txt')
CRASH_MARKER_FILE = os.path.join(LOG_DIR, 'crash_marker.txt')

# 全局变量
heartbeat_thread = None
heartbeat_running = False

def setup_crash_logging():
    """设置崩溃日志系统"""
    # 创建日志目录
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    
    # 配置文件日志处理器
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # 修改为INFO级别，记录所有日志
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # 配置控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler],
        format=log_format
    )
    
    # 设置全局异常处理器
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = f"未捕获的异常: {exc_type.__name__}: {exc_value}"
        logging.error(error_msg, exc_info=(exc_type, exc_value, exc_traceback))
        
        # 记录系统信息
        logging.error(f"Python版本: {sys.version}")
        logging.error(f"操作系统: {os.name}")
        logging.error(f"工作目录: {os.getcwd()}")
        logging.error(f"应用基础目录: {APP_BASE_DIR}")
        
        print(f"\n=== 崩溃日志已保存到: {LOG_FILE} ===")
        print(f"错误信息: {error_msg}")
        print("请查看日志文件获取详细信息")
    
    sys.excepthook = handle_exception
    
    # 设置信号处理器（Windows下部分信号不可用）
    def signal_handler(signum, frame):
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        error_msg = f"接收到系统信号: {signal_name} ({signum})"
        logging.critical(error_msg)
        logging.critical(f"信号接收时间: {datetime.datetime.now()}")
        logging.critical(f"Python版本: {sys.version}")
        logging.critical(f"工作目录: {os.getcwd()}")
        print(f"\n=== 系统信号崩溃 ===")
        print(f"信号: {signal_name} ({signum})")
        print(f"日志已保存到: {LOG_FILE}")
        sys.exit(1)
    
    # 注册信号处理器（仅注册Windows支持的信号）
    try:
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)  # Windows Ctrl+Break
    except (OSError, ValueError) as e:
        logging.warning(f"部分信号处理器注册失败: {e}")
    
    # 注册程序退出时的清理函数
    def cleanup_on_exit():
        global heartbeat_running
        heartbeat_running = False
        # 移除崩溃标记文件（正常退出）
        try:
            if os.path.exists(CRASH_MARKER_FILE):
                os.remove(CRASH_MARKER_FILE)
        except Exception as e:
            logging.error(f"清理崩溃标记文件失败: {e}")
    
    atexit.register(cleanup_on_exit)
    
    logging.info("崩溃日志系统已启动")
    logging.info(f"日志文件路径: {LOG_FILE}")
    logging.info(f"心跳文件路径: {HEARTBEAT_FILE}")
    logging.info(f"崩溃标记文件路径: {CRASH_MARKER_FILE}")

def start_heartbeat():
    """启动心跳检测线程"""
    global heartbeat_thread, heartbeat_running
    
    def heartbeat_worker():
        while heartbeat_running:
            try:
                with open(HEARTBEAT_FILE, 'w', encoding='utf-8') as f:
                    f.write(f"{datetime.datetime.now().isoformat()}\n")
                    f.write(f"PID: {os.getpid()}\n")
                    f.write(f"Status: Running\n")
                time.sleep(5)  # 每5秒更新一次心跳
            except Exception as e:
                logging.error(f"心跳更新失败: {e}")
                time.sleep(5)
    
    heartbeat_running = True
    heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    heartbeat_thread.start()
    logging.info("心跳检测已启动")

def stop_heartbeat():
    """停止心跳检测"""
    global heartbeat_running
    heartbeat_running = False
    logging.info("心跳检测已停止")

def check_previous_crash():
    """检查上次是否异常退出"""
    crash_detected = False
    
    # 检查崩溃标记文件
    if os.path.exists(CRASH_MARKER_FILE):
        try:
            with open(CRASH_MARKER_FILE, 'r', encoding='utf-8') as f:
                crash_info = f.read()
            logging.warning("检测到上次程序异常退出")
            logging.warning(f"崩溃信息: {crash_info}")
            crash_detected = True
        except Exception as e:
            logging.error(f"读取崩溃标记文件失败: {e}")
    
    # 检查心跳文件
    if os.path.exists(HEARTBEAT_FILE):
        try:
            with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as f:
                heartbeat_info = f.read()
            # 如果心跳文件存在但没有崩溃标记，说明可能是异常退出
            if not crash_detected:
                logging.warning("检测到心跳文件残留，可能发生了异常退出")
                logging.warning(f"上次心跳信息: {heartbeat_info}")
                crash_detected = True
        except Exception as e:
            logging.error(f"读取心跳文件失败: {e}")
    
    if crash_detected:
        logging.warning("=== 上次运行异常退出检测 ===")
        logging.warning("建议检查系统日志或事件查看器获取更多信息")
    
    return crash_detected

def create_crash_marker(reason="Unknown"):
    """创建崩溃标记文件"""
    try:
        with open(CRASH_MARKER_FILE, 'w', encoding='utf-8') as f:
            f.write(f"Crash Time: {datetime.datetime.now().isoformat()}\n")
            f.write(f"Reason: {reason}\n")
            f.write(f"PID: {os.getpid()}\n")
            f.write(f"Python Version: {sys.version}\n")
            f.write(f"Working Directory: {os.getcwd()}\n")
    except Exception as e:
        logging.error(f"创建崩溃标记文件失败: {e}")

# 默认命令配置
DEFAULT_COMMANDS = [
    {
        "name": "设备列表",
        "command": "hdc list targets",
        "type": "normal",
        "icon": "device"
    },
    {
        "name": "设备信息",
        "command": "hdc target mount",
        "type": "normal",
        "icon": "info"
    },
    {
        "name": "上传文件",
        "command": "hdc file send {local_path} {remote_path}",
        "type": "upload",
        "icon": "upload"
    },
    {
        "name": "下载文件",
        "command": "hdc file recv {remote_path} {local_path}",
        "type": "download",
        "icon": "download"
    },
    {
        "name": "安装应用",
        "command": "hdc install {local_path}",
        "type": "upload",
        "icon": "install"
    },
    {
        "name": "卸载应用",
        "command": "hdc uninstall {package_name}",
        "type": "normal",
        "icon": "uninstall"
    }
]

# 流星动画效果类
class ParticleEffect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.effect_type = 'floating_orbs'  # 可选: floating_orbs, wave_ripples, geometric_dance
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(100)  # 100ms更新一次，平衡视觉效果和性能
        
        # 设置透明背景
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.time = 0  # 用于动画时间计算
        # 可定制的调色板与背景色，随主题变化
        self.custom_colors = None  # List[Tuple[int,int,int]]
        self.background_qcolor = QColor(10, 10, 20)
        # 初始化粒子效果
        self.init_particles()
    
    def set_effect(self, effect_type: str, colors: list = None, background: QColor = None):
        """切换动效类型并可选更新调色板与背景色。会重建粒子。"""
        self.effect_type = effect_type
        if colors is not None:
            self.custom_colors = colors
        if background is not None:
            self.background_qcolor = background
        # 彻底清理粒子并重新初始化
        self.particles.clear()
        self.time = 0  # 重置时间计数器
        self.init_particles()
    
    def set_palette(self, colors: list = None, background: QColor = None):
        """仅更新调色板与背景色，并重建粒子。"""
        if colors is not None:
            self.custom_colors = colors
        if background is not None:
            self.background_qcolor = background
        self.particles.clear()
        self.init_particles()
    
    def init_particles(self):
        """初始化粒子效果"""
        if self.effect_type == 'floating_orbs':
            self.init_floating_orbs()
        elif self.effect_type == 'wave_ripples':
            self.init_wave_ripples()
        elif self.effect_type == 'geometric_dance':
            self.init_geometric_dance()
        elif self.effect_type == 'cherry_blossom':
            self.init_cherry_blossom()
        elif self.effect_type == 'forest_fireflies':
            self.init_forest_fireflies()
    
    def init_floating_orbs(self):
        """初始化漂浮光球效果"""
        colors = self.custom_colors or [
            (100, 200, 255),  # 蓝色
            (255, 100, 200),  # 粉色
            (100, 255, 150),  # 绿色
            (255, 200, 100),  # 橙色
            (200, 100, 255),  # 紫色
            (100, 255, 255),  # 青色
        ]
        for _ in range(8):
            color = random.choice(colors)
            particle = {
                'x': random.uniform(0, self.width() or 800),
                'y': random.uniform(0, self.height() or 600),
                'speed_x': random.uniform(-1.5, 1.5),
                'speed_y': random.uniform(-1.5, 1.5),
                'size': random.uniform(15, 35),
                'opacity': random.uniform(0.3, 0.8),
                'color_r': color[0],
                'color_g': color[1],
                'color_b': color[2],
                'pulse_speed': random.uniform(0.02, 0.05),
                'pulse_phase': random.uniform(0, 2 * math.pi)
            }
            self.particles.append(particle)
    
    def init_wave_ripples(self):
        """初始化波纹效果"""
        colors = self.custom_colors or [
            (50, 150, 255),   # 蓝色
            (100, 255, 200),  # 青绿色
            (150, 100, 255),  # 紫色
            (255, 150, 100),  # 橙色
        ]
        for i in range(6):
            color = random.choice(colors)
            particle = {
                'center_x': random.uniform(100, (self.width() or 800) - 100),
                'center_y': random.uniform(100, (self.height() or 600) - 100),
                'radius': 0,
                'max_radius': random.uniform(80, 150),
                'speed': random.uniform(1.5, 3.0),
                'opacity': random.uniform(0.4, 0.7),
                'color_r': color[0],
                'color_g': color[1],
                'color_b': color[2],
                'phase': i * math.pi / 3
            }
            self.particles.append(particle)
    
    def init_geometric_dance(self):
        """初始化几何图形舞蹈效果"""
        center_x = (self.width() or 800) / 2
        center_y = (self.height() or 600) / 2
        
        colors = self.custom_colors or [
            (255, 100, 100),  # 红色
            (100, 255, 100),  # 绿色
            (100, 100, 255),  # 蓝色
            (255, 255, 100),  # 黄色
            (255, 100, 255),  # 洋红
            (100, 255, 255),  # 青色
        ]
        
        for i in range(12):
            angle = i * (2 * math.pi / 12)
            color = colors[i % len(colors)]
            particle = {
                'center_x': center_x,
                'center_y': center_y,
                'orbit_radius': random.uniform(80, 200),
                'angle': angle,
                'angular_speed': random.uniform(0.01, 0.03),
                'size': random.uniform(8, 20),
                'opacity': random.uniform(0.5, 0.9),
                'color_r': color[0],
                'color_g': color[1],
                'color_b': color[2],
                'shape': random.choice(['circle', 'triangle', 'square'])
            }
            self.particles.append(particle)
    
    def update_particles(self):
        """更新粒子位置和状态"""
        self.time += 0.05
        
        if self.effect_type == 'floating_orbs':
            self.update_floating_orbs()
        elif self.effect_type == 'wave_ripples':
            self.update_wave_ripples()
        elif self.effect_type == 'geometric_dance':
            self.update_geometric_dance()
        elif self.effect_type == 'cherry_blossom':
            self.update_cherry_blossom()
        elif self.effect_type == 'forest_fireflies':
            self.update_forest_fireflies()
        
        self.update()  # 触发重绘
    
    def update_floating_orbs(self):
        """更新漂浮光球"""
        for particle in self.particles:
            # 更新位置
            particle['x'] += particle['speed_x']
            particle['y'] += particle['speed_y']
            
            # 边界反弹
            if particle['x'] <= 0 or particle['x'] >= (self.width() or 800):
                particle['speed_x'] *= -1
            if particle['y'] <= 0 or particle['y'] >= (self.height() or 600):
                particle['speed_y'] *= -1
            
            # 脉动效果
            particle['pulse_phase'] += particle['pulse_speed']
            particle['opacity'] = 0.3 + 0.4 * (1 + math.sin(particle['pulse_phase'])) / 2
    
    def update_wave_ripples(self):
        """更新波纹效果"""
        for particle in self.particles:
            particle['radius'] += particle['speed']
            
            # 重置波纹
            if particle['radius'] > particle['max_radius']:
                particle['radius'] = 0
                particle['center_x'] = random.uniform(100, (self.width() or 800) - 100)
                particle['center_y'] = random.uniform(100, (self.height() or 600) - 100)
            
            # 透明度随半径变化
            particle['opacity'] = 0.7 * (1 - particle['radius'] / particle['max_radius'])
    
    def update_geometric_dance(self):
        """更新几何图形舞蹈"""
        for particle in self.particles:
            particle['angle'] += particle['angular_speed']
            
            # 计算轨道位置
            particle['x'] = particle['center_x'] + particle['orbit_radius'] * math.cos(particle['angle'])
            particle['y'] = particle['center_y'] + particle['orbit_radius'] * math.sin(particle['angle'])
            
            # 动态调整轨道半径
            particle['orbit_radius'] += math.sin(self.time + particle['angle']) * 0.5
    
    def paintEvent(self, event):
        """绘制粒子效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 使用主题适配的背景色
        painter.fillRect(self.rect(), self.background_qcolor)
        
        if self.effect_type == 'floating_orbs':
            self.draw_floating_orbs(painter)
        elif self.effect_type == 'wave_ripples':
            self.draw_wave_ripples(painter)
        elif self.effect_type == 'geometric_dance':
            self.draw_geometric_dance(painter)
        elif self.effect_type == 'cherry_blossom':
            self.draw_cherry_blossom(painter)
        elif self.effect_type == 'forest_fireflies':
            self.draw_forest_fireflies(painter)
    
    def draw_floating_orbs(self, painter):
        """绘制漂浮光球"""
        for particle in self.particles:
            x, y = particle['x'], particle['y']
            size = particle['size']
            opacity = particle['opacity']
            
            # 外层光晕
            halo_gradient = QRadialGradient(x, y, size * 3)
            halo_gradient.setColorAt(0, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(50 * opacity)))
            halo_gradient.setColorAt(1, QColor(particle['color_r'], particle['color_g'], particle['color_b'], 0))
            painter.setBrush(QBrush(halo_gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(x - size * 3), int(y - size * 3), int(size * 6), int(size * 6))
            
            # 核心光球
            core_gradient = QRadialGradient(x, y, size)
            core_gradient.setColorAt(0, QColor(255, 255, 255, int(200 * opacity)))
            core_gradient.setColorAt(0.7, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(150 * opacity)))
            core_gradient.setColorAt(1, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(50 * opacity)))
            painter.setBrush(QBrush(core_gradient))
            painter.drawEllipse(int(x - size), int(y - size), int(size * 2), int(size * 2))
    
    def draw_wave_ripples(self, painter):
        """绘制波纹效果"""
        for particle in self.particles:
            center_x, center_y = particle['center_x'], particle['center_y']
            radius = particle['radius']
            opacity = particle['opacity']
            
            if radius > 0:
                # 绘制波纹圆环
                pen = QPen(QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(255 * opacity)))
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(int(center_x - radius), int(center_y - radius), int(radius * 2), int(radius * 2))
                
                # 内层细波纹
                if radius > 10:
                    inner_pen = QPen(QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(100 * opacity)))
                    inner_pen.setWidth(1)
                    painter.setPen(inner_pen)
                    painter.drawEllipse(int(center_x - radius * 0.7), int(center_y - radius * 0.7), 
                                      int(radius * 1.4), int(radius * 1.4))
    
    def draw_geometric_dance(self, painter):
        """绘制几何图形舞蹈"""
        for particle in self.particles:
            x, y = particle['x'], particle['y']
            size = particle['size']
            opacity = particle['opacity']
            shape = particle['shape']
            
            # 设置颜色和透明度
            color = QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(255 * opacity))
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 2))
            
            if shape == 'circle':
                painter.drawEllipse(int(x - size), int(y - size), int(size * 2), int(size * 2))
            elif shape == 'square':
                painter.drawRect(int(x - size), int(y - size), int(size * 2), int(size * 2))
            elif shape == 'triangle':
                points = [
                    QPoint(int(x), int(y - size)),
                    QPoint(int(x - size), int(y + size)),
                    QPoint(int(x + size), int(y + size))
                ]
                painter.drawPolygon(points)
            
            # 连接线到中心
            center_color = QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(50 * opacity))
            painter.setPen(QPen(center_color, 1))
            painter.drawLine(int(particle['center_x']), int(particle['center_y']), int(x), int(y))
    
    def init_cherry_blossom(self):
        """初始化樱花树摇曳动效"""
        self.particles.clear()
        width = self.width() or 800
        height = self.height() or 600
        
        # 创建樱花粒子
        for i in range(15):
            particle = {
                'x': random.uniform(0, width),
                'y': random.uniform(0, height),
                'size': random.uniform(3, 8),
                'speed_x': random.uniform(-0.5, 0.5),
                'speed_y': random.uniform(-1, -0.3),
                'sway_angle': random.uniform(0, 2 * math.pi),
                'sway_speed': random.uniform(0.02, 0.05),
                'sway_amplitude': random.uniform(2, 6),
                'opacity': random.uniform(0.6, 1.0),
                'color_r': random.choice([232, 107, 139, 240]),  # 紫色系
                'color_g': random.choice([180, 61, 93, 230]),    # 紫色系
                'color_b': random.choice([203, 123, 155, 240]),  # 紫色系
                'rotation': random.uniform(0, 360),
                'rotation_speed': random.uniform(-2, 2)
            }
            self.particles.append(particle)
    
    def update_cherry_blossom(self):
        """更新樱花树摇曳动效"""
        width = self.width() or 800
        height = self.height() or 600
        
        for particle in self.particles:
            # 摇曳效果
            particle['sway_angle'] += particle['sway_speed']
            sway_offset = math.sin(particle['sway_angle']) * particle['sway_amplitude']
            
            # 更新位置（添加摇曳偏移）
            particle['x'] += particle['speed_x'] + sway_offset * 0.1
            particle['y'] += particle['speed_y']
            
            # 旋转效果
            particle['rotation'] += particle['rotation_speed']
            
            # 边界处理：从底部重新开始
            if particle['y'] < -10:
                particle['y'] = height + 10
                particle['x'] = random.uniform(0, width)
            
            # 透明度脉动
            particle['opacity'] = 0.6 + 0.4 * (1 + math.sin(self.time * 2 + particle['sway_angle'])) / 2
    
    def draw_cherry_blossom(self, painter):
        """绘制樱花树摇曳动效"""
        for particle in self.particles:
            x, y = particle['x'], particle['y']
            size = particle['size']
            opacity = particle['opacity']
            rotation = particle['rotation']
            
            # 保存当前状态
            painter.save()
            painter.translate(x, y)
            painter.rotate(rotation)
            
            # 绘制樱花花瓣（五瓣花）
            petal_count = 5
            for i in range(petal_count):
                angle = i * (360 / petal_count)
                painter.save()
                painter.rotate(angle)
                
                # 花瓣路径
                petal_path = QPainterPath()
                petal_path.moveTo(0, 0)
                petal_path.quadTo(size * 0.3, -size * 0.5, size * 0.6, -size * 0.3)
                petal_path.quadTo(size * 0.8, -size * 0.1, size * 0.6, size * 0.1)
                petal_path.quadTo(size * 0.4, size * 0.3, 0, size * 0.2)
                petal_path.quadTo(-size * 0.4, size * 0.3, -size * 0.6, size * 0.1)
                petal_path.quadTo(-size * 0.8, -size * 0.1, -size * 0.6, -size * 0.3)
                petal_path.quadTo(-size * 0.3, -size * 0.5, 0, 0)
                
                # 紫色渐变
                gradient = QRadialGradient(0, 0, size)
                gradient.setColorAt(0, QColor(255, 255, 255, int(200 * opacity)))
                gradient.setColorAt(0.5, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(150 * opacity)))
                gradient.setColorAt(1, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(50 * opacity)))
                
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.NoPen)
                painter.drawPath(petal_path)
                painter.restore()
            
            # 花蕊
            center_gradient = QRadialGradient(0, 0, size * 0.3)
            center_gradient.setColorAt(0, QColor(255, 255, 255, int(200 * opacity)))
            center_gradient.setColorAt(1, QColor(232, 180, 203, int(100 * opacity)))
            painter.setBrush(QBrush(center_gradient))
            painter.drawEllipse(int(-size * 0.3), int(-size * 0.3), int(size * 0.6), int(size * 0.6))
            
            # 恢复状态
            painter.restore()
    
    def init_forest_fireflies(self):
        """初始化森林萤火虫动效"""
        self.particles.clear()
        width = self.width() or 800
        height = self.height() or 600
        
        # 创建萤火虫粒子
        for i in range(12):
            particle = {
                'x': random.uniform(0, width),
                'y': random.uniform(0, height),
                'size': random.uniform(2, 5),
                'speed_x': random.uniform(-0.8, 0.8),
                'speed_y': random.uniform(-1.2, 0.5),
                'flicker_phase': random.uniform(0, 2 * math.pi),
                'flicker_speed': random.uniform(0.2, 0.5),
                'flicker_intensity': random.uniform(0.3, 0.8),
                'opacity': random.uniform(0.4, 0.9),
                'color_r': random.choice([0, 255, 255, 255]),  # 绿色系
                'color_g': random.choice([255, 200, 255, 150]),  # 绿色系
                'color_b': random.choice([0, 100, 0, 50]),      # 绿色系
                'trail_length': random.randint(3, 8),
                'trail_points': []
            }
            self.particles.append(particle)
    
    def update_forest_fireflies(self):
        """更新森林萤火虫动效"""
        width = self.width() or 800
        height = self.height() or 600
        
        for particle in self.particles:
            # 闪烁效果
            particle['flicker_phase'] += particle['flicker_speed']
            flicker = math.sin(particle['flicker_phase']) * particle['flicker_intensity']
            
            # 更新位置
            particle['x'] += particle['speed_x']
            particle['y'] += particle['speed_y']
            
            # 添加轨迹点
            particle['trail_points'].append((particle['x'], particle['y']))
            if len(particle['trail_points']) > particle['trail_length']:
                particle['trail_points'].pop(0)
            
            # 边界处理：从另一边重新开始
            if particle['x'] < -10:
                particle['x'] = width + 10
            elif particle['x'] > width + 10:
                particle['x'] = -10
            if particle['y'] < -10:
                particle['y'] = height + 10
            elif particle['y'] > height + 10:
                particle['y'] = -10
            
            # 透明度随闪烁变化
            particle['opacity'] = 0.4 + 0.5 * (1 + flicker) / 2
    
    def draw_forest_fireflies(self, painter):
        """绘制森林萤火虫动效"""
        for particle in self.particles:
            x, y = particle['x'], particle['y']
            size = particle['size']
            opacity = particle['opacity']
            
            # 绘制轨迹
            if len(particle['trail_points']) > 1:
                trail_path = QPainterPath()
                trail_path.moveTo(particle['trail_points'][0][0], particle['trail_points'][0][1])
                
                for i in range(1, len(particle['trail_points'])):
                    trail_path.lineTo(particle['trail_points'][i][0], particle['trail_points'][i][1])
                
                # 轨迹渐变
                trail_pen = QPen(QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(30 * opacity)), 1)
                trail_pen.setCapStyle(Qt.RoundCap)
                painter.setPen(trail_pen)
                painter.drawPath(trail_path)
            
            # 绘制萤火虫主体
            # 外层光晕
            halo_gradient = QRadialGradient(x, y, size * 4)
            halo_gradient.setColorAt(0, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(80 * opacity)))
            halo_gradient.setColorAt(1, QColor(particle['color_r'], particle['color_g'], particle['color_b'], 0))
            painter.setBrush(QBrush(halo_gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(x - size * 4), int(y - size * 4), int(size * 8), int(size * 8))
            
            # 核心光点
            core_gradient = QRadialGradient(x, y, size)
            core_gradient.setColorAt(0, QColor(255, 255, 255, int(200 * opacity)))
            core_gradient.setColorAt(0.5, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(150 * opacity)))
            core_gradient.setColorAt(1, QColor(particle['color_r'], particle['color_g'], particle['color_b'], int(50 * opacity)))
            painter.setBrush(QBrush(core_gradient))
            painter.drawEllipse(int(x - size), int(y - size), int(size * 2), int(size * 2))
    
    def resizeEvent(self, event):
        """窗口大小改变时重新初始化粒子"""
        super().resizeEvent(event)
        if hasattr(self, 'particles'):
            self.particles.clear()
            self.init_particles()

# 音乐播放器对话框
class MusicPlayerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.is_playing = False
        self.current_song = "No Song Selected"
        self.current_time = "00:00"
        self.total_time = "00:00"
        self.volume = 50
        self.progress_value = 0
        
        self.init_ui()
        self.apply_theme()
        
        # 模拟播放定时器
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.update_progress)
    
    def init_ui(self):
        self.setWindowTitle("🎵 Cyber Music Player")
        self.setFixedSize(400, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 设置窗口图标
        if self.parent_window:
            icon_path = os.path.join(APP_BASE_DIR, 'icons', 'music-player.svg')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title = QLabel("🎵 CYBER MUSIC PLAYER")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #00ffff;
            margin-bottom: 10px;
            padding: 10px;
            border: 2px solid #00ffff;
            border-radius: 10px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #1a1a2e, stop:1 #16213e);
        """)
        layout.addWidget(title)
        
        # 专辑封面区域
        cover_frame = QFrame()
        cover_frame.setFixedSize(200, 200)
        cover_frame.setStyleSheet("""
            QFrame {
                border: 3px solid #00ffff;
                border-radius: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0a0a0a, stop:0.5 #1a1a2e, stop:1 #16213e);
            }
        """)
        
        cover_layout = QVBoxLayout(cover_frame)
        cover_icon = QLabel("🎼")
        cover_icon.setAlignment(Qt.AlignCenter)
        cover_icon.setStyleSheet("font-size: 80px; color: #00ffff;")
        cover_layout.addWidget(cover_icon)
        
        # 居中显示专辑封面
        cover_container = QHBoxLayout()
        cover_container.addStretch()
        cover_container.addWidget(cover_frame)
        cover_container.addStretch()
        layout.addLayout(cover_container)
        
        # 歌曲信息
        self.song_label = QLabel(self.current_song)
        self.song_label.setAlignment(Qt.AlignCenter)
        self.song_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #ffffff;
            margin: 10px 0;
        """)
        layout.addWidget(self.song_label)
        
        # 进度条
        progress_container = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(self.progress_value)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #00ffff;
                border-radius: 8px;
                background-color: #1a1a2e;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ffff, stop:1 #ff6b6b);
                border-radius: 6px;
            }
        """)
        
        # 时间标签
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel(self.current_time)
        self.total_time_label = QLabel(self.total_time)
        self.current_time_label.setStyleSheet("color: #00ffff; font-size: 12px;")
        self.total_time_label.setStyleSheet("color: #00ffff; font-size: 12px;")
        
        time_layout.addWidget(self.current_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.total_time_label)
        
        progress_container.addWidget(self.progress_bar)
        progress_container.addLayout(time_layout)
        layout.addLayout(progress_container)
        
        # 控制按钮
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        
        # 上一首按钮
        prev_btn = QPushButton("⏮")
        prev_btn.setFixedSize(50, 50)
        prev_btn.clicked.connect(self.prev_song)
        
        # 播放/暂停按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(60, 60)
        self.play_btn.clicked.connect(self.toggle_play)
        
        # 下一首按钮
        next_btn = QPushButton("⏭")
        next_btn.setFixedSize(50, 50)
        next_btn.clicked.connect(self.next_song)
        
        # 设置按钮样式
        button_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                color: #00ffff;
                border: 2px solid #00ffff;
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00ffff, stop:1 #ff6b6b);
                color: #000000;
            }
            QPushButton:pressed {
                background: #ff6b6b;
            }
        """
        
        prev_btn.setStyleSheet(button_style)
        self.play_btn.setStyleSheet(button_style + "border-radius: 30px;")
        next_btn.setStyleSheet(button_style)
        
        controls_layout.addStretch()
        controls_layout.addWidget(prev_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(next_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # 音量控制
        volume_layout = QHBoxLayout()
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("color: #00ffff; font-size: 16px;")
        
        self.volume_slider = QProgressBar()
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.volume)
        self.volume_slider.setStyleSheet("""
            QProgressBar {
                border: 2px solid #00ffff;
                border-radius: 8px;
                background-color: #1a1a2e;
                height: 15px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff00, stop:1 #ffff00);
                border-radius: 6px;
            }
        """)
        
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        layout.addLayout(volume_layout)
        
        # 返回按钮
        back_btn = QPushButton("🔙 返回主界面")
        back_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3a8a, stop:1 #1e40af);
                color: #60a5fa;
                border: 2px solid #60a5fa;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                border-color: #93c5fd;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #60a5fa;
                color: #000000;
            }
        """)
        back_btn.clicked.connect(self.close)
        layout.addWidget(back_btn)
    
    def apply_theme(self):
        """应用主题样式"""
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0a0a, stop:0.5 #1a1a2e, stop:1 #16213e);
                color: #00ffff;
            }
        """)
    
    def toggle_play(self):
        """切换播放/暂停状态"""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.play_btn.setText("⏸")
            self.play_timer.start(1000)  # 每秒更新一次
            if self.parent_window:
                self.parent_window.log_message("🎵 开始播放音乐", success=True)
        else:
            self.play_btn.setText("▶")
            self.play_timer.stop()
            if self.parent_window:
                self.parent_window.log_message("⏸ 音乐已暂停", info=True)
    
    def prev_song(self):
        """上一首歌"""
        songs = ["Cyber Dreams", "Neon Nights", "Digital Love", "Future Bass", "Synthwave"]
        current_index = songs.index(self.current_song) if self.current_song in songs else 0
        self.current_song = songs[(current_index - 1) % len(songs)]
        self.song_label.setText(self.current_song)
        self.progress_value = 0
        self.progress_bar.setValue(self.progress_value)
        if self.parent_window:
            self.parent_window.log_message(f"⏮ 切换到: {self.current_song}", info=True)
    
    def next_song(self):
        """下一首歌"""
        songs = ["Cyber Dreams", "Neon Nights", "Digital Love", "Future Bass", "Synthwave"]
        current_index = songs.index(self.current_song) if self.current_song in songs else 0
        self.current_song = songs[(current_index + 1) % len(songs)]
        self.song_label.setText(self.current_song)
        self.progress_value = 0
        self.progress_bar.setValue(self.progress_value)
        if self.parent_window:
            self.parent_window.log_message(f"⏭ 切换到: {self.current_song}", info=True)
    
    def update_progress(self):
        """更新播放进度"""
        if self.is_playing:
            self.progress_value += 2  # 每秒增加2%
            if self.progress_value >= 100:
                self.progress_value = 0
                self.next_song()  # 自动播放下一首
            
            self.progress_bar.setValue(self.progress_value)
            
            # 更新时间显示
            current_seconds = int(self.progress_value * 3.6)  # 假设总时长3分钟
            total_seconds = 180
            
            self.current_time = f"{current_seconds // 60:02d}:{current_seconds % 60:02d}"
            self.total_time = f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"
            
            self.current_time_label.setText(self.current_time)
            self.total_time_label.setText(self.total_time)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        self.play_timer.stop()
        if self.parent_window:
            self.parent_window.log_message("🔙 音乐播放器已关闭", info=True)
        event.accept()

# 命令执行线程
class CommandThread(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, command, theme=None):
        super().__init__()
        self.command = command
        self.process = None
        self.theme = theme
        
    def run(self):
        try:
            logging.info(f"CommandThread开始执行: {self.command}")
            
            # 展开Windows环境变量
            import os
            expanded_command = os.path.expandvars(self.command)
            logging.debug(f"环境变量展开后的命令: {expanded_command}")
            
            # 创建进程
            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.handle_output)
            
            # 设置环境变量以确保正确的编码
            env = self.process.processEnvironment()
            env.insert("PYTHONIOENCODING", "utf-8")
            env.insert("CHCP", "65001")  # UTF-8代码页
            self.process.setProcessEnvironment(env)
            
            # 启动进程 - 使用cmd执行命令，先设置代码页为UTF-8
            full_command = f"chcp 65001 >nul 2>&1 && {expanded_command}"
            logging.debug(f"执行完整命令: {full_command}")
            self.process.start("cmd", ["/c", full_command])
            
            # 等待进程完成
            if self.process.waitForFinished(-1):
                exit_code = self.process.exitCode()
                logging.info(f"命令执行完成，退出代码: {exit_code}")
                
                # 特殊处理：explorer命令即使成功也可能返回非零退出代码
                is_explorer_command = 'explorer' in expanded_command.lower()
                
                if exit_code == 0 or is_explorer_command:
                    if is_explorer_command and exit_code != 0:
                        logging.info(f"Explorer命令特殊处理：忽略退出代码{exit_code}，视为成功")
                    self.finished_signal.emit(True, "命令执行成功")
                else:
                    error_msg = f"命令执行失败，退出代码: {exit_code}"
                    logging.warning(error_msg)
                    self.finished_signal.emit(False, error_msg)
            else:
                error_msg = "命令执行超时或失败"
                logging.error(error_msg)
                self.finished_signal.emit(False, error_msg)
                
        except Exception as e:
            error_msg = f"CommandThread执行异常: {e}"
            logging.error(error_msg, exc_info=True)
            self.output_signal.emit(f"错误: {str(e)}\n")
            self.finished_signal.emit(False, f"执行出错: {str(e)}")
    
    def handle_output(self):
        try:
            raw_data = self.process.readAllStandardOutput().data()
            # 尝试多种编码方式
            for encoding in ['utf-8', 'gbk', 'cp936', 'gb2312']:
                try:
                    data = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # 如果所有编码都失败，使用utf-8并忽略错误
                data = raw_data.decode('utf-8', errors='ignore')
        except Exception as e:
            data = f"编码错误: {str(e)}\n"
            
        # 对输出进行颜色处理，只对特定类型的消息添加颜色标签
        if 'error' in data.lower() or 'failed' in data.lower() or 'exception' in data.lower():
            # 错误信息使用红色显示
            data = f"<span style='color:#e74c3c;'>{data}</span>"
        elif 'warning' in data.lower():
            # 警告信息使用黄色显示
            data = f"<span style='color:#f39c12;'>{data}</span>"
        elif 'success' in data.lower() or 'completed' in data.lower():
            # 成功信息使用绿色显示
            data = f"<span style='color:#2ecc71;'>{data}</span>"
        elif data.strip().startswith('>'):
            # 命令提示符使用蓝色显示
            color = self.theme['accent_color'] if self.theme else '#3498db'
            data = f"<span style='color:{color}; font-weight:bold;'>{data}</span>"
        # 普通输出不添加颜色标签，让终端使用默认样式
            
        self.output_signal.emit(data)
        
    def stop(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()

# 主窗口类
class CommandManager(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            logging.info("开始初始化CommandManager...")
            self.commands = []
            self.deleted_commands = []  # 回收站命令列表
            self.command_thread = None
            self.current_theme = 'light'  # 默认主题
            self.command_states = {}  # 命令状态记录字典，用于支持录屏等状态切换命令
            self._edit_dialog_open = False  # 防止重复打开编辑对话框
            
            # 音乐播放器相关
            self.ready_click_count = 0  # READY按钮点击计数
            self.music_player_dialog = None
            
            logging.info("初始化主题...")
            self.init_themes()
            
            logging.info("加载UI设置...")
            self.load_ui_settings()
            
            logging.info("初始化UI...")
            self.init_ui()
            
            logging.info("加载配置...")
            self.load_config()
            
            logging.info("加载删除的命令...")
            self.load_deleted_commands()
            
            logging.info("CommandManager初始化完成")
        except Exception as e:
            error_msg = f"CommandManager初始化失败: {e}"
            logging.error(error_msg, exc_info=True)
            print(error_msg)
            raise
        
    def init_themes(self):
        """初始化主题配置"""
        self.themes = {
            'cyber': {
                'name': '⚡ CYBER',
                'window_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a0a0a, stop:0.3 #1a1a2e, stop:0.7 #16213e, stop:1 #0f3460)',
                'title_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00ffff, stop:0.5 #ff6b6b, stop:1 #00ffff)',
                'title_color': '#ffffff',
                'button_bg': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2c3e50, stop:1 #34495e)',
                'button_border': '#00ffff',
                'button_hover': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00ffff, stop:1 #0099cc)',
                'button_text': '#ffffff',
                'terminal_bg': '#1a1a2e',
                'terminal_border': '#00ffff',
                'terminal_text': '#ffffff',
                'accent_color': '#00ffff'
            },
            'light': {
                'name': '☀️ LIGHT',
                'window_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:0.3 #f8f9fa, stop:0.7 #f1f3f4, stop:1 #e9ecef)',
                'title_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8f9fa, stop:0.5 #e9ecef, stop:1 #f8f9fa)',
                'title_color': '#000000',
                'button_bg': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f9fa, stop:1 #e9ecef)',
                'button_border': '#2563eb',
                'button_hover': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8)',
                'button_text': '#000000',
                'terminal_bg': '#ffffff',
                'terminal_border': '#2563eb',
                'terminal_text': '#495057',
                'accent_color': '#000000'
            },
            'dark': {
                'name': '🌲 FOREST',
                'window_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d1117, stop:0.3 #161b22, stop:0.7 #21262d, stop:1 #30363d)',
                'title_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d4aa, stop:0.5 #39ff14, stop:1 #00d4aa)',
                'title_color': '#ffffff',
                'button_bg': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #21262d, stop:1 #161b22)',
                'button_border': '#00d4aa',
                'button_hover': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00d4aa, stop:1 #00a085)',
                'button_text': '#ffffff',
                'terminal_bg': '#161b22',
                'terminal_border': '#00d4aa',
                'terminal_text': '#ffffff',
                'accent_color': '#00d4aa'
            },
            'nord': {
                'name': '❄️ NORD',
                'window_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2E3440, stop:0.5 #3B4252, stop:1 #434C5E)',
                'title_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5E81AC, stop:1 #88C0D0)',
                'title_color': '#ECEFF4',
                'button_bg': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4C566A, stop:1 #3B4252)',
                'button_border': '#88C0D0',
                'button_hover': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #88C0D0, stop:1 #5E81AC)',
                'button_text': '#ECEFF4',
                'terminal_bg': '#2E3440',
                'terminal_border': '#88C0D0',
                'terminal_text': '#D8DEE9',
                'accent_color': '#88C0D0'
            },
            'amoled': {
                'name': '💜 LAVENDER',
                'window_bg': '#1a1a1a',
                'title_bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2d1b3d, stop:0.5 #4a2c5a, stop:1 #6b3d7b)',
                'title_color': '#FFFFFF',
                'button_bg': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a2c5a, stop:1 #6b3d7b)',
                'button_border': '#e8b4cb',
                'button_hover': 'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6b3d7b, stop:1 #8b5d9b)',
                'button_text': '#FFFFFF',
                'terminal_bg': '#2d1b3d',
                'terminal_border': '#e8b4cb',
                'terminal_text': '#f0e6f0',
                'accent_color': '#e8b4cb'
            }
        }
        
    def init_ui(self):
        # 设置窗口属性
        self.setWindowTitle("命令管理器")
        self.setMinimumSize(1200, 800)  # 增加窗口尺寸
        self.resize(1400, 900)  # 设置默认大小
        
        # 设置窗口图标
        self.set_window_icon()
        
        # 设置窗口居中
        self.center_window()
        
        # 设置毛玻璃效果
        self.setup_glass_effect()
        
        # 设置赛博朋克风格样式
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0a0a, stop:0.5 #1a1a2e, stop:1 #16213e);
            }
            QDialog {
                background-color: #1a1a2e;
                color: #00ffff;
            }
            QLabel {
                color: #00ffff;
                font-family: 'Consolas', 'Monaco', monospace;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                color: #00ffff;
                border: 2px solid #00ffff;
                padding: 12px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                font-family: 'Consolas', 'Monaco', monospace;
                /* text-shadow removed for Qt compatibility */
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00ffff, stop:1 #0099cc);
                border-color: #ff6b6b;
                color: #000000;
                /* text-shadow removed for Qt compatibility */
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6b6b, stop:1 #ee5a24);
                border-color: #ff6b6b;
                color: #000000;
            }
            QProgressBar {
                border: 2px solid #00ffff;
                border-radius: 4px;
                text-align: center;
                background-color: #1a1a2e;
                color: #00ffff;
                height: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff00, stop:1 #00ffff);
                border-radius: 4px;
            }
            QScrollArea {
                border: 2px solid #00ffff;
                border-radius: 8px;
                background-color: #1a1a2e;
            }
            QSplitter::handle {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ffff, stop:0.5 #ff6b6b, stop:1 #00ffff);
                border-radius: 3px;
            }
            QComboBox, QLineEdit {
                border: 2px solid #00ffff;
                border-radius: 4px;
                padding: 8px 12px;
                background-color: #1a1a2e;
                color: #00ffff;
                font-size: 13px;
                font-family: 'Consolas', 'Monaco', monospace;
            }
            QComboBox:focus, QLineEdit:focus {
                border-color: #ff6b6b;
                /* text-shadow removed for Qt compatibility */
            }
        """)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 8, 15, 15)  # 减少上边距
        main_layout.setSpacing(8)  # 减少间距
        
        # 简洁的标题栏
        title_widget = QWidget()
        title_widget.setFixedHeight(120)  # 继续增加高度确保上下边距一致
        title_widget.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 4px;
            }
        """)
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(20, 22, 20, 22)  # 调整内边距以统一视觉高度
        title_layout.setAlignment(Qt.AlignVCenter)  # 设置垂直居中对齐
        # 标题栏控件统一高度，保证两侧等高
        self.header_control_height = 56
        
        # 主题切换按钮 + 下拉菜单
        self.theme_button = QPushButton(self.themes[self.current_theme]['name'] + " THEME")
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setStyleSheet("""
            QPushButton {
                font-size: 18px; 
                font-weight: 700; 
                margin: 0;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                padding: 8px 16px;
                border-radius: 8px;
                min-height: 48px;
                max-height: 48px;
            }
        """)
        self.theme_button.setFixedHeight(self.header_control_height)
        self.theme_button.clicked.connect(self.switch_theme)
        theme_menu = QMenu(self)
        # 主题菜单样式
        theme_menu.setStyleSheet(self.get_menu_stylesheet(self.themes[self.current_theme]))
        for theme_key, theme_cfg in self.themes.items():
            action = QAction(theme_cfg['name'], self)
            action.triggered.connect(lambda checked, k=theme_key: self.set_theme(k))
            theme_menu.addAction(action)
        self.theme_button.setMenu(theme_menu)
        title_layout.addWidget(self.theme_button)
        
        # 移除日志按钮，将其移动到左侧面板
        
        # 中部诗句轮播标签
        self.poem_label = QLabel()
        self.poem_label.setObjectName("poemLabel")
        self.poem_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.poem_label.setAlignment(Qt.AlignCenter)
        self.poem_label.setFixedHeight(self.header_control_height)
        # 默认样式：透明背景，居中显示
        self.poem_label.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            padding: 8px 16px;
            background: transparent;
            border: none;
        """)
        title_layout.addWidget(self.poem_label)
        
        title_layout.addStretch()  # 添加弹性空间推动时间标签到右侧
        
        # 当前时间显示
        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"""
            font-size: 20px; 
            font-weight: 700;
            color: #ffffff;
            background: transparent;
            padding: 10px 20px;
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            min-height: {self.header_control_height}px;
            max-height: {self.header_control_height}px;
        """)
        self.time_label.setAlignment(Qt.AlignCenter)  # 设置文本居中对齐
        self.time_label.setFixedHeight(self.header_control_height)
        self.update_time()
        
        # 创建定时器更新时间
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # 每秒更新一次
        
        # 诗句轮播：每3分钟更换一次
        self.poems = [
            "西风寒露深林下，任是无人也自香",
            "疏影横斜水清浅，暗香浮动月黄昏",
            "非淡泊无以明志，非宁静无以致远",
            "天行健，君子以自强不息",
            "知者不惑，仁者不忧，勇者不惧",
            "路漫漫其修远兮，吾将上下而求索",
            "纸上得来终觉浅，绝知此事要躬行",
            "人生如逆旅，我亦是行人",
            "山川异域，风月同天",
            "愿你出走半生，归来仍是少年",
            "生活不止眼前的苟且，还有诗和远方",
            "世界那么大，我想去看看",
            "你若盛开，蝴蝶自来",
            "心有猛虎，细嗅蔷薇",
            "愿有岁月可回首，且以深情共白头",
            "既然选择了远方，便只顾风雨兼程",
            "时光不老，我们不散",
            "愿你被这个世界温柔以待",
            "做自己的太阳，无需凭借谁的光",
            "努力到无能为力，拼搏到感动自己",
            "不负青春，不负梦想"
        ]
        self._poem_index = 0
        self.update_poem()
        self.poem_timer = QTimer(self)
        self.poem_timer.timeout.connect(self.update_poem)
        self.poem_timer.start(3 * 60 * 1000)  # 3分钟
        
        title_layout.addWidget(self.time_label)
        
        # 缩放控制按钮组
        scale_widget = QWidget()
        scale_layout = QHBoxLayout(scale_widget)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.setSpacing(5)
        
        # 初始化缩放比例
        self.scale_factor = 1.0
        
        # 缩小按钮
        self.scale_down_btn = QPushButton("－")
        self.scale_down_btn.setFixedSize(32, 22)
        self.scale_down_btn.setToolTip("缩小界面 (Ctrl+-)")
        self.scale_down_btn.setCursor(Qt.PointingHandCursor)
        self.scale_down_btn.clicked.connect(self.scale_down)
        
        # 重置按钮
        self.scale_reset_btn = QPushButton("100%")
        self.scale_reset_btn.setFixedSize(42, 22)
        self.scale_reset_btn.setToolTip("重置界面大小 (Ctrl+0)")
        self.scale_reset_btn.setCursor(Qt.PointingHandCursor)
        self.scale_reset_btn.clicked.connect(self.scale_reset)
        
        # 放大按钮
        self.scale_up_btn = QPushButton("＋")
        self.scale_up_btn.setFixedSize(32, 22)
        self.scale_up_btn.setToolTip("放大界面 (Ctrl++)")
        self.scale_up_btn.setCursor(Qt.PointingHandCursor)
        self.scale_up_btn.clicked.connect(self.scale_up)
        
        # 禁用焦点以去除焦点效果
        self.scale_down_btn.setFocusPolicy(Qt.NoFocus)
        self.scale_reset_btn.setFocusPolicy(Qt.NoFocus)
        self.scale_up_btn.setFocusPolicy(Qt.NoFocus)
        
        # 设置按钮为扁平样式以去除大块区域效果
        self.scale_down_btn.setFlat(True)
        self.scale_reset_btn.setFlat(True)
        self.scale_up_btn.setFlat(True)
        
        # 设置缩放按钮样式 - 高对比度，清晰可见，去掉焦点红色背景
        theme = self.themes[self.current_theme]
        scale_button_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {theme['accent_color']};
                border: 2px solid {theme['accent_color']};
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                padding: 2px;
                margin: 1px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
                color: {theme['accent_color']};
                border-color: {theme['accent_color']};
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.2);
                color: {theme['accent_color']};
                border-color: {theme['button_text']};
            }}
            QPushButton:focus {{
                outline: none;
                background-color: transparent;
                border: 2px solid {theme['accent_color']};
            }}
        """
        
        self.scale_down_btn.setStyleSheet(scale_button_style)
        self.scale_reset_btn.setStyleSheet(scale_button_style)
        self.scale_up_btn.setStyleSheet(scale_button_style)
        
        scale_layout.addWidget(self.scale_down_btn)
        scale_layout.addWidget(self.scale_reset_btn)
        scale_layout.addWidget(self.scale_up_btn)
        
        title_layout.addWidget(scale_widget)
        
        # 添加快捷键
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self.scale_down)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self.scale_up)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.scale_reset)
        
        main_layout.addWidget(title_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)  # 增加分割条宽度
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ffff, stop:0.5 #ff6b6b, stop:1 #00ffff);
                border-radius: 3px;
                margin: 2px;
                border: 1px solid #00ffff;
            }
            QSplitter::handle:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b6b, stop:0.5 #00ff00, stop:1 #ff6b6b);
                border-color: #ff6b6b;
            }
        """)
        main_layout.addWidget(splitter)
        
        # 左侧面板 - 命令按钮区域（含搜索）
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        # 初始化时使用当前主题的样式
        theme = self.themes[self.current_theme]
        panel_bg = theme['terminal_bg'] if self.current_theme == 'light' else theme['window_bg']
        left_panel.setStyleSheet(f"""
            #leftPanel {{ 
                background: {panel_bg};
                border-radius: 15px;
                border: 2px solid {theme['accent_color']};
            }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        
        # 添加粒子动画效果到左侧面板
        self.left_particle_effect = ParticleEffect(left_panel)
        self.left_particle_effect.setGeometry(0, 0, left_panel.width(), left_panel.height())
        self.left_particle_effect.lower()  # 确保在其他控件下方
        # 根据当前主题设置动效类型
        if self.current_theme == 'dark':
            self.left_particle_effect.set_effect('forest_fireflies')
        elif self.current_theme == 'amoled':
            self.left_particle_effect.set_effect('cherry_blossom')
        elif self.current_theme == 'nord':
            self.left_particle_effect.set_effect('wave_ripples')
        else:
            self.left_particle_effect.set_effect('floating_orbs')
        self.left_particle_effect.show()
        
        # 命令区域标题
        commands_header_widget = QWidget()
        commands_header_layout = QHBoxLayout(commands_header_widget)
        commands_header_layout.setContentsMargins(0, 0, 0, 0)
        
        commands_header = QLabel("📋 COMMANDS LIST")
        commands_header.setObjectName("commandsHeader")
        # 初始使用当前主题的颜色
        theme = self.themes[self.current_theme]
        title_color = theme['terminal_text'] if self.current_theme == 'light' else theme['accent_color']
        commands_header.setStyleSheet(f"""
            font-size: 18px; 
            font-weight: 700; 
            color: {title_color};
            margin-bottom: 5px;
            padding: 8px 16px;
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
        """)
        
        self.commands_count = QLabel(f"({len(self.commands)} 个命令)")
        self.commands_count.setStyleSheet("""
            font-size: 12px; 
            color: #ff6b6b;
            background-color: #16213e;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid #ff6b6b;
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
        """)
        
        commands_header_layout.addWidget(commands_header)
        commands_header_layout.addWidget(self.commands_count, alignment=Qt.AlignCenter)
        commands_header_layout.addStretch()
        
        # 搜索框
        search_row = QWidget()
        search_row_layout = QHBoxLayout(search_row)
        search_row_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索命令名称或内容...")
        self.search_input.textChanged.connect(self.filter_commands)
        search_icon = QLabel("🔎")
        search_row_layout.addWidget(search_icon)
        search_row_layout.addWidget(self.search_input)
        # 快捷键 Ctrl+F 聚焦搜索
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)

        left_layout.addWidget(commands_header_widget)
        left_layout.addWidget(search_row)
        
        # 命令按钮网格布局
        self.commands_grid = QGridLayout()
        self.commands_grid.setSpacing(12)
        self.commands_grid.setContentsMargins(5, 5, 5, 5)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setContentsMargins(0, 15, 0, 0)  # 添加上边距以对齐右侧终端
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1a1a2e;
                width: 10px;
                border-radius: 5px;
                margin: 0;
                border: 1px solid #00ffff;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ffff, stop:1 #ff6b6b);
                border-radius: 5px;
                min-height: 20px;
                border: 1px solid #00ffff;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b6b, stop:1 #00ff00);
                border-color: #ff6b6b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_content.setLayout(self.commands_grid)
        scroll_area.setWidget(scroll_content)
        left_layout.addWidget(scroll_area)
        
        # 添加管理按钮与提示
        manage_btn = QPushButton("SYSTEM CONFIG")
        manage_btn.setIcon(self.create_icon("settings"))
        manage_btn.setIconSize(QSize(16, 16))
        manage_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                color: #ffffff;
                border: 2px solid #00ffff;
                padding: 12px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00ffff, stop:1 #0099cc);
                border-color: #ff6b6b;
                color: #000000;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff6b6b, stop:1 #ee5a24);
                border-color: #ff6b6b;
                color: #000000;
            }
        """)
        manage_btn.clicked.connect(self.show_command_manager)
        manage_btn.setCursor(Qt.PointingHandCursor)
        left_layout.addWidget(manage_btn)
        
        # 回收站和日志按钮区域
        recycle_log_layout = QHBoxLayout()
        recycle_log_layout.setSpacing(10)
        
        # 回收站按钮
        recycle_btn = QPushButton("🗑️ 查看回收站")
        recycle_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2d3748, stop:1 #1a202c);
                color: #ffd700;
                border: 2px solid #ffd700;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                margin: 5px 0px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a5568, stop:1 #2d3748);
                border-color: #ffed4e;
                color: #ffed4e;
                margin-top: 3px;
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffd700, stop:1 #f6e05e);
                border-color: #ffd700;
                color: #000000;
            }}
        """)
        recycle_btn.clicked.connect(self.show_recycle_bin)
        recycle_btn.setCursor(Qt.PointingHandCursor)
        recycle_log_layout.addWidget(recycle_btn)
        
        # 日志查看按钮
        self.log_button = QPushButton("📋 查看日志")
        self.log_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3a8a, stop:1 #1e40af);
                color: #60a5fa;
                border: 2px solid #60a5fa;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                margin: 5px 0px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                border-color: #93c5fd;
                color: #ffffff;
                margin-top: 3px;
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #60a5fa, stop:1 #3b82f6);
                border-color: #60a5fa;
                color: #000000;
            }}
        """)
        self.log_button.clicked.connect(self.show_log_viewer)
        self.log_button.setCursor(Qt.PointingHandCursor)
        recycle_log_layout.addWidget(self.log_button)
        
        left_layout.addLayout(recycle_log_layout)
        
        hint = QLabel("右键命令可 快速编辑/删除/复制")
        hint.setStyleSheet("color: #cccccc; font-size: 12px; font-weight: 500;")
        left_layout.addWidget(hint)
        
        # 右侧面板 - 终端输出区域
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        # 初始化时使用当前主题的样式
        panel_bg = theme['terminal_bg'] if self.current_theme == 'light' else theme['window_bg']
        right_panel.setStyleSheet(f"""
            #rightPanel {{ 
                background: {panel_bg};
                border-radius: 15px;
                border: 2px solid {theme['accent_color']};
            }}
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)
        
        # 添加粒子动画效果到右侧面板
        self.right_particle_effect = ParticleEffect(right_panel)
        self.right_particle_effect.setGeometry(0, 0, right_panel.width(), right_panel.height())
        self.right_particle_effect.lower()  # 确保在其他控件下方
        # 根据当前主题设置动效类型
        if self.current_theme == 'dark':
            self.right_particle_effect.set_effect('forest_fireflies')
        elif self.current_theme == 'amoled':
            self.right_particle_effect.set_effect('cherry_blossom')
        elif self.current_theme == 'nord':
            self.right_particle_effect.set_effect('wave_ripples')
        else:
            self.right_particle_effect.set_effect('floating_orbs')
        self.right_particle_effect.show()
        
        # 终端区域标题
        terminal_header_widget = QWidget()
        terminal_header_layout = QHBoxLayout(terminal_header_widget)
        terminal_header_layout.setContentsMargins(0, 0, 0, 0)
        
        terminal_label = QLabel("📟 SYSTEM OUTPUT")
        terminal_label.setStyleSheet("""
            font-size: 18px; 
            font-weight: 700; 
            color: #ffffff;
            margin-bottom: 5px;
            padding: 8px 16px;
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
        """)
        
        # 添加状态标签以匹配左侧的命令计数
        self.terminal_status = QLabel("(READY)")
        self.terminal_status.setStyleSheet("""
            font-size: 12px; 
            color: #00ff00;
            background-color: #16213e;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid #00ff00;
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
        """)
        # 为READY标签添加点击事件
        self.terminal_status.mousePressEvent = self.ready_clicked
        self.terminal_status.setCursor(Qt.PointingHandCursor)  # 设置鼠标悬停时显示手型光标
        
        terminal_header_layout.addWidget(terminal_label)
        terminal_header_layout.addWidget(self.terminal_status, alignment=Qt.AlignCenter)
        
        # 按钮容器布局
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # 打开文件夹按钮
        folder_btn = QPushButton("📁")
        folder_btn.setToolTip("打开当前命令管理器文件夹")
        folder_btn.setFixedSize(40, 40)
        folder_btn.setStyleSheet("""
            QPushButton {
                border-radius: 8px;
                padding: 8px;
                font-weight: 700;
                font-size: 16px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            }
        """)
        folder_btn.clicked.connect(self.open_current_folder)
        folder_btn.setCursor(Qt.PointingHandCursor)
        buttons_layout.addWidget(folder_btn)
        
        # 清除按钮
        clear_btn = QPushButton("PURGE")
        clear_btn.setIcon(self.create_icon("trash"))
        clear_btn.setIconSize(QSize(14, 14))
        # 初始样式将由apply_theme函数设置
        clear_btn.setStyleSheet("""
            QPushButton {
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 18px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            }
        """)
        clear_btn.clicked.connect(self.clear_terminal)
        clear_btn.setCursor(Qt.PointingHandCursor)
        buttons_layout.addWidget(clear_btn)
        
        # 创建按钮容器widget
        buttons_widget = QWidget()
        buttons_widget.setLayout(buttons_layout)
        terminal_header_layout.addWidget(buttons_widget, alignment=Qt.AlignRight)
        
        right_layout.addWidget(terminal_header_widget)
        
        # 终端输出区域
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        # 添加点击事件处理
        self.terminal.mousePressEvent = self.terminal_clicked
        # 初始样式将由apply_theme函数设置
        self.terminal.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
                padding: 12px;
                border-radius: 8px;
                margin-top: 15px;
            }
            QScrollBar:vertical {
                background-color: #1a1a2e;
                width: 12px;
                border-radius: 6px;
                margin: 0;
                border: 1px solid #00ffff;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ffff, stop:1 #ff6b6b);
                border-radius: 6px;
                min-height: 20px;
                border: 1px solid #00ffff;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6b6b, stop:1 #00ff00);
                border-color: #ff6b6b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        # 初始化终端消息将在apply_theme中设置
        self.init_terminal_message()
        right_layout.addWidget(self.terminal)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumHeight(20)
        right_layout.addWidget(self.progress_bar)
        
        # 添加面板到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # 设置分割器比例 (左侧:右侧 = 2:3)
        splitter.setSizes([500, 750])
        splitter.setStretchFactor(0, 2)  # 左侧面板拉伸因子
        splitter.setStretchFactor(1, 3)  # 右侧面板拉伸因子
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 显示窗口
        self.show()
        # 主窗口淡入（受全局开关控制）
        if ANIMATIONS_ENABLED:
            # 使用图形淡入而非窗口淡入，避免任何系统误判
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.0)
            self.setGraphicsEffect(effect)
            self.fade_in_animation = QPropertyAnimation(effect, b"opacity")
            self.fade_in_animation.setDuration(400)
            self.fade_in_animation.setStartValue(0.0)
            self.fade_in_animation.setEndValue(1.0)
            self.fade_in_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.fade_in_animation.start()
        
        # 连接分割器大小变化事件
        splitter.splitterMoved.connect(self.on_splitter_moved)
        
        # 保存面板引用以便后续使用
        self.left_panel = left_panel
        self.right_panel = right_panel
        
        # 延迟初始化粒子效果
        QTimer.singleShot(500, self.init_particle_effects)
        
        # 应用默认主题
        self.apply_theme()
    
    def init_particle_effects(self):
        """延迟初始化粒子效果"""
        if hasattr(self, 'left_particle_effect'):
            self.left_particle_effect.setGeometry(0, 0, self.left_particle_effect.parent().width(), self.left_particle_effect.parent().height())
            self.left_particle_effect.particles.clear()
            self.left_particle_effect.init_particles()
        
        if hasattr(self, 'right_particle_effect'):
            self.right_particle_effect.setGeometry(0, 0, self.right_particle_effect.parent().width(), self.right_particle_effect.parent().height())
            self.right_particle_effect.particles.clear()
            self.right_particle_effect.init_particles()
    
    def on_splitter_moved(self, pos, index):
        """分割器移动时更新粒子效果"""
        self.update_particle_effects_size()
    
    def resizeEvent(self, event):
        """主窗口大小变化时更新粒子效果"""
        super().resizeEvent(event)
        # 延迟更新粒子效果，确保面板大小已经更新
        QTimer.singleShot(50, self.update_particle_effects_size)
    
    def update_particle_effects_size(self):
        """更新粒子效果大小"""
        if hasattr(self, 'left_particle_effect') and hasattr(self, 'left_panel'):
            self.left_particle_effect.setGeometry(0, 0, self.left_panel.width(), self.left_panel.height())
            # 重新初始化粒子以适应新的尺寸
            self.left_particle_effect.particles.clear()
            self.left_particle_effect.init_particles()
        
        if hasattr(self, 'right_particle_effect') and hasattr(self, 'right_panel'):
            self.right_particle_effect.setGeometry(0, 0, self.right_panel.width(), self.right_panel.height())
            # 重新初始化粒子以适应新的尺寸
            self.right_particle_effect.particles.clear()
            self.right_particle_effect.init_particles()
    
    def set_window_icon(self):
        """设置窗口图标"""
        # 获取资源路径
        if getattr(sys, 'frozen', False):
            # 如果是打包的应用，使用_MEIPASS中的资源路径
            try:
                base_path = sys._MEIPASS
                icon_dir = os.path.join(base_path, 'icons')
            except Exception:
                # 如果无法获取_MEIPASS，回退到应用程序目录
                icon_dir = os.path.join(os.path.dirname(sys.executable), 'icons')
        else:
            # 如果是开发环境，使用脚本目录
            icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        
        # 尝试加载ICO图标
        ico_path = os.path.join(icon_dir, 'cyber_terminal.ico')
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))
        else:
            # 备用方案：使用SVG图标
            svg_path = os.path.join(icon_dir, 'cyber_terminal.svg')
            if os.path.exists(svg_path):
                self.setWindowIcon(QIcon(svg_path))
            else:
                # 最后备用方案：使用原始图标
                fallback_path = os.path.join(icon_dir, 'terminal.ico')
                if os.path.exists(fallback_path):
                    self.setWindowIcon(QIcon(fallback_path))

    def load_ui_settings(self):
        # 读取UI偏好（主题）
        try:
            if os.path.exists(UI_SETTINGS_FILE):
                with open(UI_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    theme_key = data.get('theme')
                    if theme_key in self.themes:
                        self.current_theme = theme_key
        except Exception:
            pass

    def save_ui_settings(self):
        # 保存UI偏好（主题）
        try:
            with open(UI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump({'theme': self.current_theme}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def focus_search(self):
        if hasattr(self, 'search_input'):
            self.search_input.setFocus()
    
    def setup_glass_effect(self):
        """设置毛玻璃效果"""
        try:
            # 设置窗口透明度
            self.setWindowOpacity(0.95)
            
            # 设置半透明背景属性
            self.setAttribute(Qt.WA_TranslucentBackground)
            
            # Windows平台特定的毛玻璃效果
            if sys.platform == 'win32':
                try:
                    import ctypes
                    from ctypes import wintypes
                    
                    # 获取窗口句柄
                    hwnd = int(self.winId())
                    
                    # 启用亚克力模糊效果 (Windows 10/11)
                    DWM_BB_ENABLE = 0x00000001
                    DWM_BB_BLURREGION = 0x00000002
                    
                    class DWM_BLURBEHIND(ctypes.Structure):
                        _fields_ = [
                            ('dwFlags', wintypes.DWORD),
                            ('fEnable', wintypes.BOOL),
                            ('hRgnBlur', wintypes.HANDLE),
                            ('fTransitionOnMaximized', wintypes.BOOL)
                        ]
                    
                    bb = DWM_BLURBEHIND()
                    bb.dwFlags = DWM_BB_ENABLE
                    bb.fEnable = True
                    bb.hRgnBlur = None
                    bb.fTransitionOnMaximized = False
                    
                    # 调用DWM API
                    ctypes.windll.dwmapi.DwmEnableBlurBehindWindow(hwnd, ctypes.byref(bb))
                    
                except Exception:
                    # 如果Windows API调用失败，忽略错误
                    pass
                    
        except Exception:
            # 如果设置毛玻璃效果失败，忽略错误
            pass

    def filter_commands(self, text):
        keyword = (text or '').strip().lower()
        self.filtered_commands = None
        if keyword:
            self.filtered_commands = [c for c in self.commands if keyword in c.get('name', '').lower() or keyword in c.get('command', '').lower()]
        # 重建按钮网格
        # 清除现有按钮（彻底销毁，避免无父级窗口）
        try:
            while self.commands_grid.count():
                item = self.commands_grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
        except Exception:
            pass
        self.add_new_command_buttons()
    
    def center_window(self):
        # 获取屏幕几何信息
        screen_geometry = QDesktopWidget().availableGeometry()
        # 计算窗口居中位置
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        # 移动窗口
        self.move(x, y)
    
    def update_time(self):
        # 更新时间显示
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(current_time)
    
    def update_poem(self):
        """轮播诗句显示到标题栏中部标签，用半角括号包围。"""
        try:
            if not hasattr(self, 'poems') or not self.poems:
                return
            self._poem_index = (getattr(self, '_poem_index', 0)) % len(self.poems)
            poem_text = self.poems[self._poem_index]
            # 用半角括号包围诗句
            self.poem_label.setText(f"[ {poem_text} ]")
            self._poem_index = (self._poem_index + 1) % len(self.poems)
        except Exception:
            pass
    
    def load_config(self):
        # 加载配置文件
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.commands = json.load(f)
            else:
                self.commands = DEFAULT_COMMANDS
                self.save_config()
        except Exception as e:
            self.log_message(f"加载配置失败: {str(e)}", error=True)
            self.commands = DEFAULT_COMMANDS
        
        # 更新命令按钮
        self.update_command_buttons()
    
    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.commands, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log_message(f"保存配置失败: {str(e)}", error=True)
    
    def load_deleted_commands(self):
        """加载被删除的命令"""
        try:
            if os.path.exists(DELETED_COMMANDS_FILE):
                with open(DELETED_COMMANDS_FILE, 'r', encoding='utf-8') as f:
                    self.deleted_commands = json.load(f)
            else:
                self.deleted_commands = []
        except Exception as e:
            self.log_message(f"加载回收站失败: {str(e)}", error=True)
            self.deleted_commands = []
    
    def save_deleted_commands(self):
        """保存被删除的命令"""
        try:
            with open(DELETED_COMMANDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.deleted_commands, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log_message(f"保存回收站失败: {str(e)}", error=True)
    
    def move_to_recycle_bin(self, cmd):
        """将命令移动到回收站"""
        import datetime
        # 添加删除时间戳
        deleted_cmd = cmd.copy()
        deleted_cmd['deleted_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.deleted_commands.append(deleted_cmd)
        self.save_deleted_commands()
    
    def restore_from_recycle_bin(self, deleted_cmd):
        """从回收站恢复命令"""
        # 移除删除时间戳
        restored_cmd = deleted_cmd.copy()
        if 'deleted_at' in restored_cmd:
            del restored_cmd['deleted_at']
        
        # 添加到命令列表
        self.commands.append(restored_cmd)
        self.save_config()
        
        # 从回收站移除
        self.deleted_commands.remove(deleted_cmd)
        self.save_deleted_commands()
        
        # 更新界面
        self.update_command_buttons()
        self.log_message(f"命令 '{restored_cmd['name']}' 已恢复", info=True)
    
    def update_command_buttons(self):
        # 清除现有按钮
        try:
            while self.commands_grid.count():
                item = self.commands_grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    # 彻底销毁，避免变成无父级顶层窗口出现在任务栏
                    widget.deleteLater()
        except Exception:
            # 兜底清理
            for i in reversed(range(self.commands_grid.count())):
                widget = self.commands_grid.itemAt(i).widget()
                if widget:
                    widget.hide()
                    widget.deleteLater()
        
        # 立即添加新按钮
        self.add_new_command_buttons()
        # 保证网格所在的滚动内容可见
        try:
            scroll_area = self.findChildren(QScrollArea)[0]
            scroll_area.viewport().update()
        except Exception:
            pass

        # 若存在搜索词，则维持过滤视图
        if hasattr(self, 'search_input'):
            self.filter_commands(self.search_input.text())
    
    def create_command_tooltip(self, cmd):
        """创建命令的工具提示"""
        tooltip = f"<b></b>"
        
        # 添加命令内容
        tooltip += f"<b>命令:</b> {cmd['command']}</b>"
        
        # 不显示类型和分类信息
        
        return tooltip
        
    def get_command_icon_symbol(self, icon_name):
        """根据图标名称返回对应的Unicode符号图标"""
        icon_map = {
            # 基本图标
            'terminal': '💡',
            'file': '📁',
            'download': '📥',
            'upload': '📤',
            'screenshot': '📷',
            'screen_record': '🎬',
            'list': '📋',
            'info': '🔍',  # 更改为放大镜图标
            'network': '🌐',
            'disk': '💾',
            'memory': '🧠',
            'cpu': '⚙️',
            'system': '💡',
            'process': '📊',
            'service': '🔧',
            'user': '👤',
            'group': '👥',
            'time': '⏰',
            'date': '📅',
            'log': '📝',
            'help': '❓',
            'search': '🔍',
            'config': '⚙️',
            'install': '📦',
            'update': '🔄',
            'remove': '🗑️',
            'start': '▶️',
            'stop': '⏹️',
            'restart': '🔄',
            'status': '📊',
            'mount': '📂',
            'unmount': '📤',
            'backup': '💾',
            'restore': '🔄',
            'compress': '📦',
            'extract': '📂',
            'encrypt': '🔒',
            'decrypt': '🔓',
            'send': '📤',
            'receive': '📥',
            'connect': '🔌',
            'disconnect': '🔌',
            
            # 新增图标
            'star': '⭐',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅',
            'cloud': '☁️',
            'database': '🗄️',
            'code': '📝',
            'bug': '🐞',
            'chart': '💡',
            'folder': '📁',
            'document': '📄',
            'image': '🖼️',
            'video': '🎬',
            'audio': '🔊',
            'link': '🔗',
            'key': '🔑',
            'gear': '⚙️',
            'clock': '🕒',
            'calendar': '📅',
            'mail': '📧',
            'phone': '📱',
            'location': '📍',
            'heart': '❤️',
            'flag': '🚩',
            'rocket': '🚀',
            'fire': '🔥',
            'light': '💡',
            
            # 兼容旧版命令名称
            '设备列表': '🔗',
            '设备信息': '💡',
            '上传文件': '🚀',
            '下载文件': '💾',
            '安装应用': '⚙️',
            '卸载应用': '❌',
            '截图': '📷',
            '查看任务': '🔍'
        }
        return icon_map.get(icon_name, '⭐')
    
    def switch_theme(self):
        """切换主题"""
        themes_list = list(self.themes.keys())
        current_index = themes_list.index(self.current_theme)
        next_index = (current_index + 1) % len(themes_list)
        self.set_theme(themes_list[next_index])

    def set_theme(self, theme_key):
        if theme_key not in self.themes:
            return
        self.current_theme = theme_key
        self.apply_theme()
        self.save_ui_settings()
        
    def apply_theme(self):
        """应用当前主题"""
        theme = self.themes[self.current_theme]
        
        # 更新主题按钮文本和样式
        self.theme_button.setText(theme['name'] + " THEME")
        self.theme_button.setStyleSheet(f"""
            QPushButton {{
                font-size: 18px; 
                font-weight: 700; 
                color: {theme['button_text']};
                margin: 0;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                background: {theme['button_bg']};
                border: 2px solid {theme['accent_color']};
                padding: 10px 18px;
                border-radius: 8px;
                min-height: {self.header_control_height}px;
                max-height: {self.header_control_height}px;
            }}
            QPushButton::menu-indicator {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QPushButton:hover {{
                background: {theme['button_hover']};
                border-color: {theme['accent_color']};
                color: {theme['button_text']};
            }}
            QPushButton:pressed {{
                background: {theme['button_hover']};
                border-color: {theme['accent_color']};
                color: {theme['button_text']};
            }}
        """)
        
        # 更新窗口背景
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {theme['window_bg']};
            }}
        """)
        
        # 更新标题栏样式
        title_widget = self.theme_button.parent()
        title_widget.setStyleSheet(f"""
            QWidget {{
                background: {theme['title_bg']};
                border-radius: 12px;
                margin: 8px;
                min-height: 50px;
            }}
        """)
        
        # 更新时间标签样式
        time_color = theme['button_text']
        self.time_label.setStyleSheet(f"""
            font-size: 22px; 
            font-weight: 700;
            color: {time_color};
            background: transparent;
            padding: 10px 20px;
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            min-height: {self.header_control_height}px;
            max-height: {self.header_control_height}px;
        """)
        
        # 更新诗句标签样式（透明背景，高对比度文字）
        if hasattr(self, 'poem_label'):
            # 根据主题选择合适的文字颜色，确保清晰可见
            if self.current_theme == 'light':
                poem_color = '#000000'  # 浅色主题用黑色
            elif self.current_theme == 'cyber':
                poem_color = '#ffffff'  # 赛博主题用白色
            elif self.current_theme == 'dark':
                poem_color = '#ffffff'  # 深色主题用白色
            elif self.current_theme == 'nord':
                poem_color = '#ECEFF4'  # Nord主题用浅色
            elif self.current_theme == 'amoled':
                poem_color = '#e8b4cb'  # AMOLED主题用淡紫色
            else:
                poem_color = theme['title_color']
            
            self.poem_label.setStyleSheet(f"""
                font-size: 18px;
                font-weight: 600;
                color: {poem_color};
                background: transparent;
                padding: 10px 16px;
                border: none;
                min-height: {self.header_control_height}px;
                max-height: {self.header_control_height}px;
            """)
        # 保持标题栏两侧控件等高
        if hasattr(self, 'header_control_height'):
            self.theme_button.setFixedHeight(self.header_control_height)
            self.time_label.setFixedHeight(self.header_control_height)
            if hasattr(self, 'poem_label'):
                self.poem_label.setFixedHeight(self.header_control_height)
        
        # 更新命令按钮样式
        self.update_command_buttons()
        
        # 更新终端样式
        self.update_terminal_style()
        
        # 更新状态栏样式
        self.update_status_bar_style()
        
        # 更新左侧面板样式
        self.update_left_panel_style()
        
        # 更新右侧面板样式
        self.update_right_panel_style()
        
        # 更新粒子效果显示
        self.update_particle_effects()
        
        # 更新缩放按钮样式
        self.update_scale_buttons_style()

        # 更新主题菜单当前项文本
        if self.theme_button and self.theme_button.menu():
            self.theme_button.setText(theme['name'] + " THEME")
            # 重建菜单以反映顺序与可点击态
            self.theme_button.menu().clear()
            # 应用菜单样式，确保菜单项在各主题下可见
            self.theme_button.menu().setStyleSheet(self.get_menu_stylesheet(theme))
            for theme_key, theme_cfg in self.themes.items():
                action = QAction(theme_cfg['name'], self)
                action.setCheckable(True)
                action.setChecked(theme_key == self.current_theme)
                action.triggered.connect(lambda checked, k=theme_key: self.set_theme(k))
                self.theme_button.menu().addAction(action)
        
        # 设置全局悬浮提示样式
        self.apply_tooltip_style(theme)

    def get_menu_stylesheet(self, theme):
        # 通用 QMenu/QAction 样式，保证在深色/浅色/高对比主题下可读
        text_color = theme.get('terminal_text', '#ffffff')
        bg_color = theme.get('terminal_bg', '#222')
        hover_bg = theme.get('button_hover', '#444')
        border = theme.get('accent_color', '#00ffff')
        return f"""
            QMenu {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid {border};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                background-color: transparent;
                color: {text_color};
            }}
            QMenu::item:selected {{
                background: {hover_bg};
                color: {text_color};
            }}
            QMenu::separator {{
                height: 1px;
                background: {border};
                margin: 4px 2px;
            }}
        """
    
    def apply_tooltip_style(self, theme):
        """设置全局悬浮提示样式"""
        # 为不同主题设计专门的悬浮提示样式，确保高对比度和可读性
        if self.current_theme == 'light':
            # 浅色主题：使用柔和的白色背景配深灰文字，蓝色边框更友好
            tooltip_bg = '#ffffff'
            tooltip_text = '#333333'
            tooltip_border = '#4a90e2'
        elif self.current_theme == 'cyber':
            # 赛博主题：深蓝背景配亮青文字，柔和边框
            tooltip_bg = '#0f172a'
            tooltip_text = '#22d3ee'
            tooltip_border = '#06b6d4'
        elif self.current_theme == 'dark':
            # 森林主题：深绿背景配浅绿文字，友好边框
            tooltip_bg = '#022c22'
            tooltip_text = '#6ee7b7'
            tooltip_border = '#10b981'
        elif self.current_theme == 'nord':
            # Nord主题：柔和深蓝背景配浅色文字，冰蓝边框
            tooltip_bg = '#3B4252'
            tooltip_text = '#E5E9F0'
            tooltip_border = '#81A1C1'
        elif self.current_theme == 'amoled':
            # AMOLED主题：深黑背景配柔和粉文字，友好边框
            tooltip_bg = '#000000'
            tooltip_text = '#f9a8d4'
            tooltip_border = '#f472b6'
        else:
            # 默认样式
            tooltip_bg = theme.get('terminal_bg', '#2b2b2b')
            tooltip_text = theme.get('terminal_text', '#ffffff')
            tooltip_border = theme.get('accent_color', '#00ffff')
        
        # 设置全局悬浮提示样式
        QToolTip.setFont(QFont('Microsoft YaHei', 10))
        
        # 使用更简单直接的样式设置方法
        tooltip_style = f"""
        QToolTip {{
            background-color: {tooltip_bg} !important;
            color: {tooltip_text} !important;
            border: 2px solid {tooltip_border} !important;
            border-radius: 8px !important;
            padding: 12px 16px !important;
            font-size: 12px !important;
            font-family: 'Microsoft YaHei', 'Arial', sans-serif !important;
            font-weight: 500 !important;
            min-width: 250px !important;
            max-width: 700px !important;
            min-height: 60px !important;
            line-height: 1.6 !important;
        }}
        """
        
        # 直接设置样式，使用!important确保优先级
        QApplication.instance().setStyleSheet(tooltip_style)
        
        # 同时设置调色板以确保工具提示颜色生效
        palette = QApplication.instance().palette()
        palette.setColor(QPalette.ToolTipBase, QColor(tooltip_bg))
        palette.setColor(QPalette.ToolTipText, QColor(tooltip_text))
        QApplication.instance().setPalette(palette)
        
        # 输出调试信息
        print(f"Qt version: {QT_VERSION_STR}")
        print(f"当前主题: {self.current_theme}")
        print(f"悬浮提示背景色: {tooltip_bg}")
        print(f"悬浮提示文字色: {tooltip_text}")
        print(f"悬浮提示边框色: {tooltip_border}")
    
    def apply_button_tooltip_style(self, button):
        """为单个按钮应用悬浮提示样式"""
        theme = self.themes[self.current_theme]
        
        # 使用与apply_tooltip_style相同的颜色逻辑
        if self.current_theme == 'light':
            # 浅色主题：使用柔和的白色背景配深灰文字，蓝色边框更友好
            tooltip_bg = '#ffffff'
            tooltip_text = '#333333'
            tooltip_border = '#4a90e2'
        elif self.current_theme == 'cyber':
            # 赛博主题：深蓝背景配亮青文字，柔和边框
            tooltip_bg = '#0f172a'
            tooltip_text = '#22d3ee'
            tooltip_border = '#06b6d4'
        elif self.current_theme == 'dark':
            # 森林主题：深绿背景配浅绿文字，友好边框
            tooltip_bg = '#022c22'
            tooltip_text = '#6ee7b7'
            tooltip_border = '#10b981'
        elif self.current_theme == 'nord':
            # Nord主题：柔和深蓝背景配浅色文字，冰蓝边框
            tooltip_bg = '#3B4252'
            tooltip_text = '#E5E9F0'
            tooltip_border = '#81A1C1'
        elif self.current_theme == 'amoled':
            # AMOLED主题：深黑背景配柔和粉文字，友好边框
            tooltip_bg = '#000000'
            tooltip_text = '#f9a8d4'
            tooltip_border = '#f472b6'
        else:
            # 默认样式
            tooltip_bg = theme.get('terminal_bg', '#2b2b2b')
            tooltip_text = theme.get('terminal_text', '#ffffff')
            tooltip_border = theme.get('accent_color', '#00ffff')
        
        # 获取按钮当前样式
        current_style = button.styleSheet()
        
        # 构建工具提示样式
        tooltip_style = f"""
            QToolTip {{
                background-color: {tooltip_bg} !important;
                color: {tooltip_text} !important;
                border: 2px solid {tooltip_border} !important;
                border-radius: 8px !important;
                padding: 8px 12px !important;
                font-size: 13px !important;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif !important;
                font-weight: 500 !important;
                min-width: 120px !important;
                max-width: 300px !important;
                line-height: 1.4 !important;
            }}
        """
        
        # 合并样式
        combined_style = current_style + tooltip_style
        button.setStyleSheet(combined_style)
    
    def update_status_bar_style(self):
        """更新状态栏样式"""
        theme = self.themes[self.current_theme]
        
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {theme['terminal_bg']};
                color: {theme['terminal_text']};
                padding: 5px;
                border-top: 2px solid {theme['accent_color']};
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }}
        """)
        
    def update_left_panel_style(self):
        """更新左侧面板样式"""
        theme = self.themes[self.current_theme]
        
        # 更新左侧面板背景
        left_panel = self.findChild(QWidget, "leftPanel")
        if left_panel:
            # 为light主题使用更明显的背景色
            panel_bg = theme['terminal_bg'] if self.current_theme == 'light' else theme['window_bg']
            left_panel.setStyleSheet(f"""
                #leftPanel {{ 
                    background: {panel_bg};
                    border-radius: 15px;
                    border: 2px solid {theme['accent_color']};
                }}
            """)
        
        # 更新命令区域标题
        commands_header = self.findChild(QLabel, "commandsHeader")
        if commands_header:
            header_text = "📋 COMMANDS LIST"
            commands_header.setText(header_text)
            # 根据主题设置合适的颜色
            title_color = theme['terminal_text'] if self.current_theme == 'light' else theme['accent_color']
            commands_header.setStyleSheet(f"""
                font-size: 18px; 
                font-weight: 700; 
                color: {title_color};
                margin-bottom: 5px;
                padding: 8px 16px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            """)
        
        # 更新命令计数标签
        if hasattr(self, 'commands_count'):
            self.commands_count.setStyleSheet(f"""
                font-size: 12px; 
                color: {theme['accent_color']};
                background-color: {theme['terminal_bg']};
                padding: 2px 8px;
                border-radius: 10px;
                border: 1px solid {theme['accent_color']};
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            """)
        
        # 更新滚动区域样式
        scroll_areas = self.findChildren(QScrollArea)
        for scroll_area in scroll_areas:
            scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    background: transparent;
                    border: none;
                }}
                QScrollBar:vertical {{
                    background-color: {theme['terminal_bg']};
                    width: 10px;
                    border-radius: 5px;
                    margin: 0;
                    border: 1px solid {theme['accent_color']};
                }}
                QScrollBar::handle:vertical {{
                    background: {theme['accent_color']};
                    border-radius: 5px;
                    min-height: 20px;
                    border: 1px solid {theme['accent_color']};
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {theme['terminal_text']};
                    border-color: {theme['accent_color']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)
        
        # 更新管理按钮样式
        manage_buttons = self.findChildren(QPushButton)
        for btn in manage_buttons:
            if "SYSTEM CONFIG" in btn.text():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {theme['terminal_bg']};
                        color: {theme['terminal_text']};
                        border: 2px solid {theme['accent_color']};
                        padding: 12px 20px;
                        border-radius: 8px;
                        font-weight: 600;
                        font-size: 12px;
                        font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                    }}
                    QPushButton:hover {{
                        background: {theme['accent_color']};
                        border-color: {theme['terminal_text']};
                        color: {theme['window_bg']};
                    }}
                    QPushButton:pressed {{
                        background: {theme['terminal_text']};
                        border-color: {theme['accent_color']};
                        color: {theme['window_bg']};
                    }}
                """)

        # 更新提示文字样式
        hint_labels = self.findChildren(QLabel)
        for label in hint_labels:
            if "右键命令可" in label.text():
                # 根据主题设置合适的颜色
                if self.current_theme == 'light':
                    hint_color = '#666666'
                    hint_bg = 'rgba(0,0,0,0.1)'
                else:
                    hint_color = '#cccccc'
                    hint_bg = 'rgba(255,255,255,0.1)'
                
                label.setStyleSheet(f"""
                    color: {hint_color};
                    font-size: 12px;
                    font-weight: 500;
                    font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                """)

        # 搜索框样式
        if hasattr(self, 'search_input'):
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 8px;
                    padding: 6px 10px;
                    font-size: 12px;
                }}
                QLineEdit:focus {{
                    border-color: {theme['button_border']};
                }}
            """)
                
    def update_right_panel_style(self):
        """更新右侧面板样式"""
        theme = self.themes[self.current_theme]
        
        # 更新右侧面板背景
        right_panel = self.findChild(QWidget, "rightPanel")
        if right_panel:
            # 为light主题使用更明显的背景色
            panel_bg = theme['terminal_bg'] if self.current_theme == 'light' else theme['window_bg']
            right_panel.setStyleSheet(f"""
                #rightPanel {{ 
                    background: {panel_bg};
                    border-radius: 15px;
                    border: 2px solid {theme['accent_color']};
                }}
            """)
        
        # 更新终端区域标题
        terminal_labels = self.findChildren(QLabel)
        for label in terminal_labels:
            if "SYSTEM OUTPUT" in label.text():
                header_text = "📟 SYSTEM OUTPUT" if self.current_theme == 'light' else "📟 SYSTEM OUTPUT"
                label.setText(header_text)
                label.setStyleSheet(f"""
                    font-size: 18px; 
                    font-weight: 700; 
                    color: {theme['terminal_text']};
                    margin-bottom: 5px;
                    padding: 8px 16px;
                    font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                """)
                break
        
        # 更新终端状态标签
        if hasattr(self, 'terminal_status'):
            status_color = theme['accent_color'] if self.current_theme != 'light' else '#28a745'
            self.terminal_status.setStyleSheet(f"""
                font-size: 12px; 
                color: {status_color};
                background-color: {theme['terminal_bg']};
                padding: 2px 8px;
                border-radius: 10px;
                border: 1px solid {status_color};
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            """)
        
        # 更新清除按钮和文件夹按钮样式
        clear_buttons = self.findChildren(QPushButton)
        for btn in clear_buttons:
            if "PURGE" in btn.text():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {theme['button_bg']};
                        color: {theme['button_text']};
                        border: 2px solid {theme['accent_color']};
                        border-radius: 8px;
                        padding: 8px 16px;
                        font-weight: 700;
                        font-size: 18px;
                        font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                    }}
                    QPushButton:hover {{
                        background: {theme['button_hover']};
                        color: {theme['button_text']};
                        border-color: {theme['accent_color']};
                    }}
                    QPushButton:pressed {{
                        background: {theme['button_hover']};
                        border-color: {theme['accent_color']};
                        color: {theme['button_text']};
                    }}
                """)
            elif "📁" in btn.text():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {theme['button_bg']};
                        color: {theme['button_text']};
                        border: 2px solid {theme['accent_color']};
                        border-radius: 8px;
                        padding: 8px;
                        font-weight: 700;
                        font-size: 16px;
                        font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                    }}
                    QPushButton:hover {{
                        background: {theme['button_hover']};
                        color: {theme['button_text']};
                        border-color: {theme['accent_color']};
                    }}
                    QPushButton:pressed {{
                        background: {theme['button_hover']};
                        border-color: {theme['accent_color']};
                        color: {theme['button_text']};
                    }}
                """)
            
    def update_particle_effects(self):
        """更新粒子效果显示"""
        # light主题隐藏粒子效果，其他主题显示
        show_particles = self.current_theme != 'light'
        
        # 为不同主题配置专属动效与配色
        def apply_theme_effect(effect_widget: ParticleEffect, theme_key: str):
            if not effect_widget:
                return
            if theme_key == 'nord':
                # 冰蓝系极光/波纹
                nord_colors = [
                    (136, 192, 208),  # #88C0D0
                    (94, 129, 172),   # #5E81AC
                    (129, 161, 193),  # #81A1C1
                    (216, 222, 233),  # #D8DEE9
                ]
                effect_widget.set_effect(
                    effect_type='wave_ripples',
                    colors=nord_colors,
                    background=QColor(46, 52, 64, 160)  # 半透明NORD深蓝
                )
            elif theme_key == 'amoled':
                # 优雅紫色樱花摇曳动效
                purple_colors = [
                    (232, 180, 203),  # 淡紫色
                    (107, 61, 123),   # 深紫色
                    (139, 93, 155),   # 中紫色
                    (240, 230, 240),  # 浅紫白
                ]
                effect_widget.set_effect(
                    effect_type='cherry_blossom',
                    colors=purple_colors,
                    background=QColor(45, 27, 61, 120)  # 半透明深紫
                )
            elif theme_key == 'dark':
                # 森林萤火虫动效
                forest_colors = [
                    (0, 255, 0),      # 亮绿色
                    (255, 200, 0),    # 金黄色
                    (255, 255, 0),    # 黄色
                    (0, 200, 0),      # 深绿色
                ]
                effect_widget.set_effect(
                    effect_type='forest_fireflies',
                    colors=forest_colors,
                    background=QColor(13, 17, 22, 120)  # 半透明森林深色
                )
            else:
                # 其他主题使用默认配置
                effect_widget.set_effect('floating_orbs')  # 强制使用默认动效
        
        if hasattr(self, 'left_particle_effect'):
            if show_particles:
                # 先停止当前动效
                self.left_particle_effect.timer.stop()
                # 应用新主题动效
                apply_theme_effect(self.left_particle_effect, self.current_theme)
                # 显示并启动
                self.left_particle_effect.show()
                self.left_particle_effect.timer.start(200)
            else:
                self.left_particle_effect.hide()
                self.left_particle_effect.timer.stop()
        
        if hasattr(self, 'right_particle_effect'):
            if show_particles:
                # 先停止当前动效
                self.right_particle_effect.timer.stop()
                # 应用新主题动效
                apply_theme_effect(self.right_particle_effect, self.current_theme)
                # 显示并启动
                self.right_particle_effect.show()
                self.right_particle_effect.timer.start(200)
            else:
                self.right_particle_effect.hide()
                self.right_particle_effect.timer.stop()
        
    def init_terminal_message(self):
        """初始化终端消息"""
        theme = self.themes[self.current_theme]
        
        if self.current_theme == 'light':
            # Light主题的初始化消息
            self.terminal.append(f"<span style='color:{theme['terminal_text']}; font-weight:bold; font-size:18px;'>☀️ LIGHT TERMINAL INITIALIZED v2.0</span>")
            self.terminal.append(f"<span style='color:{theme['accent_color']}; font-size:18px;'>" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + " - 系统准备就绪，请选择要执行的命令...</span>")
        else:
            # Dark/Cyber主题的初始化消息
            self.terminal.append(f"<span style='color:{theme['terminal_text']}; font-weight:bold; font-size:18px;'>⚡ CYBER TERMINAL INITIALIZED v2.0</span>")
            self.terminal.append(f"<span style='color:{theme['accent_color']}; font-size:18px;'>" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + " - 系统准备就绪，请选择要执行的命令...</span>")
        # 提示搜索与快捷键
        self.terminal.append(f"<span style='color:{theme['terminal_text']}; font-size:14px;'>提示：Ctrl+F 搜索命令，右键命令可编辑/删除/复制。</span>")
    
    def update_terminal_style(self):
        """更新终端样式"""
        theme = self.themes[self.current_theme]
        
        # 清除终端内容并重新初始化
        self.terminal.clear()
        self.init_terminal_message()
        
        # 更新终端输出区域
        self.terminal.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme['terminal_bg']};
                color: {theme['terminal_text']};
                border: 2px solid {theme['terminal_border']};
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
            }}
        """)
        
        # 更新进度条样式
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {theme['accent_color']};
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                color: {theme['terminal_text']};
                background-color: {theme['terminal_bg']};
                height: 18px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {theme['accent_color']}, stop:1 rgba(255,255,255,0.3));
                border-radius: 6px;
            }}
        """)
    
    def add_new_command_buttons(self):
        # 更新命令计数
        self.commands_count.setText(f"({len(self.commands)} 个命令)")
        
        # 添加命令按钮（按过滤结果）
        commands_to_show = getattr(self, 'filtered_commands', None) or self.commands
        for i, cmd in enumerate(commands_to_show):
            row, col = divmod(i, 3)
            
            # 创建按钮
            btn = QPushButton(cmd['name'])
            btn.setMinimumSize(110, 80)  # 调整按钮尺寸以显示更多
            # 稳定优先：不使用不透明度效果，直接显示
            
            # 为按钮添加符号图标
            icon_symbol = self.get_command_icon_symbol(cmd.get('icon', 'terminal'))
            # 处理文本长度，如果太长则截断并添加省略号
            display_name = self.truncate_text(cmd['name'])
            btn.setText(f"{icon_symbol} {display_name}")
            
            # 添加工具提示
            tooltip = self.create_command_tooltip(cmd)
            btn.setToolTip(tooltip)
            
            # 手动为按钮设置QToolTip样式，确保应用
            theme = self.themes[self.current_theme]
            tooltip_bg = theme.get('terminal_bg', '#2b2b2b')
            tooltip_text = theme.get('terminal_text', '#ffffff')
            tooltip_border = theme.get('accent_color', '#00ffff')
            # 设置按钮样式（不包括工具提示样式）
            theme = self.themes[self.current_theme]
            button_style = f"""
            QPushButton {{
                background: {theme['button_bg']};
                color: {theme['button_text']};
                border: 3px solid {theme['button_border']};
                border-radius: 12px;
                padding: 8px 6px;
                font-weight: 700;
                font-size: 14px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                text-align: center;
                min-height: 65px;
            }}
            QPushButton:hover {{
                background: {'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 ' + theme['button_hover'] + ', stop:1 rgba(0, 255, 255, 0.3))' if self.current_theme == 'cyber' else theme['button_hover']};
                color: {theme['button_text']};
                border: 3px solid {theme['accent_color']};
                border-style: solid;
            }}
            QPushButton:pressed {{
                background: {'qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 ' + theme['button_hover'] + ', stop:1 rgba(255, 107, 107, 0.3))' if self.current_theme == 'cyber' else theme['button_hover']};
                color: {theme['button_text']};
                border: 2px solid {theme['accent_color']};
            }}
            QPushButton:focus {{
                outline: none;
                border: 3px solid {theme['accent_color']};
            }}
            """
            btn.setStyleSheet(button_style)
            
            # 单独应用工具提示样式
            self.apply_button_tooltip_style(btn)
            
            # 设置鼠标悬停为手型
            btn.setCursor(Qt.PointingHandCursor)
            
            # 为按钮添加命令数据属性，用于状态更新时识别
            btn.setProperty('command_data', cmd)
            
            # 连接点击事件
            btn.clicked.connect(lambda checked, cmd=cmd: self.execute_command(cmd))

            # 右键菜单：编辑/删除/复制
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            def show_ctx_menu(pos, button=btn, command=cmd):
                menu = QMenu(button)
                # 设置菜单样式以保证可读性
                theme = self.themes[self.current_theme]
                menu.setStyleSheet(self.get_menu_stylesheet(theme))
                edit_act = QAction("编辑", menu)
                del_act = QAction("删除", menu)
                copy_act = QAction("复制命令", menu)
                edit_act.triggered.connect(lambda: self.open_edit_dialog(command))
                del_act.triggered.connect(lambda: self.delete_command_from_ui(command))
                copy_act.triggered.connect(lambda: self.copy_command_text(command))
                for a in (edit_act, del_act, copy_act):
                    menu.addAction(a)
                menu.exec_(button.mapToGlobal(pos))
            btn.customContextMenuRequested.connect(show_ctx_menu)
            
            # 添加到网格
            self.commands_grid.addWidget(btn, row, col)
            
            # 可选淡入动画，默认关闭以避免任何兼容性问题
            if ANIMATIONS_ENABLED:
                # 若用户开启动画，再使用图形效果淡入，避免任务栏问题
                effect = QGraphicsOpacityEffect(btn)
                effect.setOpacity(0.0)
                btn.setGraphicsEffect(effect)
                fade_in = QPropertyAnimation(effect, b"opacity")
                fade_in.setDuration(300)
                fade_in.setStartValue(0.0)
                fade_in.setEndValue(1.0)
                fade_in.setEasingCurve(QEasingCurve.InOutQuad)
                QTimer.singleShot(i * 80, fade_in.start)
    
    def truncate_text(self, text, max_length=15):
        """截断文本，如果超过最大长度则添加省略号"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    def create_icon(self, icon_name):
        """创建图标，优先使用SVG，失败时使用备用方案"""
        # 图标映射
        icons = {
            'terminal': 'cyber_terminal.svg',
            'upload': 'upload.svg',
            'download': 'download.svg',
            'device': 'smartphone.svg',
            'info': 'info-circle.svg',
            'install': 'box-arrow-in-down.svg',
            'uninstall': 'trash.svg',
            'settings': 'cyber_settings.svg',
            'trash': 'trash.svg',
            'file': 'file-earmark.svg',
            'package': 'cyber_package.svg'
        }
        
        # 获取图标文件名
        icon_filename = icons.get(icon_name, 'terminal.svg')
        
        # 获取资源路径
        if getattr(sys, 'frozen', False):
            # 如果是打包的应用，使用_MEIPASS中的资源路径
            try:
                base_path = sys._MEIPASS
                icon_dir = os.path.join(base_path, 'icons')
            except Exception:
                # 如果无法获取_MEIPASS，回退到应用程序目录
                icon_dir = os.path.join(os.path.dirname(sys.executable), 'icons')
        else:
            # 如果是开发环境，使用脚本目录
            icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        
        icon_path = os.path.join(icon_dir, icon_filename)
        
        # 尝试加载SVG图标
        if os.path.exists(icon_path):
            try:
                # 读取SVG文件
                with open(icon_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                
                # 将SVG中的颜色替换为白色
                svg_content = svg_content.replace('fill="black"', 'fill="white"')
                svg_content = svg_content.replace('fill="#000"', 'fill="white"')
                svg_content = svg_content.replace('fill="#000000"', 'fill="white"')
                svg_content = svg_content.replace('stroke="black"', 'stroke="white"')
                svg_content = svg_content.replace('stroke="#000"', 'stroke="white"')
                svg_content = svg_content.replace('stroke="#000000"', 'stroke="white"')
                
                # 如果没有指定颜色，添加白色填充
                if 'fill=' not in svg_content:
                    svg_content = svg_content.replace('<path', '<path fill="white"')
                if 'stroke=' not in svg_content and '<path' in svg_content:
                    svg_content = svg_content.replace('<path', '<path stroke="white"')
                
                # 创建QPixmap并加载SVG
                svg_bytes = svg_content.encode('utf-8')
                pixmap = QPixmap()
                pixmap.loadFromData(svg_bytes, 'SVG')
                
                if not pixmap.isNull():
                    # 缩放到合适大小
                    scaled_pixmap = pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return QIcon(scaled_pixmap)
            except Exception as e:
                print(f"加载SVG图标失败 {icon_name}: {e}")
        
        # 备用方案：使用Unicode符号
        icon_map = {
            'smartphone': '📱',
            'info-circle': 'ℹ️', 
            'upload': '⬆️',
            'download': '⬇️',
            'box-arrow-in-down': '📥',
            'trash': '🗑️',
            'gear': '⚙️',
            'file-earmark': '📄',
            'terminal': '💻'
        }
        symbol = icon_map.get(icon_name, '●')
        
        # 创建文本图标
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setPen(QColor('white'))
        painter.setFont(QFont('Arial', 10))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, symbol)
        painter.end()
        
        return QIcon(pixmap)
    
    def create_default_icon(self, icon_path):
        # 创建一个简单的SVG图标
        icon_name = os.path.basename(icon_path).split('.')[0]
        
        # 基本SVG模板
        svg_content = f'''
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <text x="8" y="12" font-size="14" text-anchor="middle">{icon_name[0].upper()}</text>
        </svg>
        '''
        
        try:
            with open(icon_path, 'w') as f:
                f.write(svg_content)
        except Exception:
            pass
    
    def execute_command(self, cmd):
        try:
            # 获取命令类型和内容
            cmd_type = cmd.get('type', 'normal')
            cmd_content = cmd['command']
            cmd_name = cmd.get('name', '未命名命令')
            
            logging.info(f"开始执行命令: {cmd_name} (类型: {cmd_type})")
            logging.debug(f"命令内容: {cmd_content}")
            
            # 特殊处理录屏命令的状态切换
            if cmd_type == 'screen_record' or '录屏' in cmd_name:
                cmd_id = f"{cmd_name}_{cmd_content}"  # 使用命令名和内容作为唯一标识
                
                if cmd_id not in self.command_states:
                    # 第一次点击：开始录屏，生成时间戳并保存
                    import datetime
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    
                    # 保存时间戳到命令状态中，确保整个录屏会话使用相同的时间戳
                    self.command_states[cmd_id] = {'status': 'recording', 'timestamp': timestamp}
                    
                    try:
                        # 尝试解析JSON格式的录屏命令
                        screen_commands = json.loads(cmd_content)
                        start_cmd = screen_commands.get('start', '')
                        
                        # 替换时间戳占位符
                        start_cmd = start_cmd.replace('{timestamp}', timestamp)
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是JSON格式，使用原有逻辑（兼容旧版本）
                        start_cmd = cmd_content.replace('stop', 'start') if 'stop' in cmd_content else cmd_content
                        
                        # 替换时间戳占位符
                        start_cmd = start_cmd.replace('{timestamp}', timestamp)
                    
                    self.log_message(f"🔴 开始录屏: {cmd_name} (时间戳: {timestamp})", info=True)
                    
                    # 更新按钮显示状态
                    self.update_recording_button_state(cmd, True)
                    
                    # 执行开始录屏命令
                    if start_cmd:
                        self.run_command_with_progress(start_cmd, f"开始录屏 {cmd_name}")
                    return
                else:
                    # 第二次点击：结束录屏并导出，使用保存的时间戳
                    saved_state = self.command_states[cmd_id]
                    timestamp = saved_state['timestamp']  # 使用开始录屏时保存的时间戳
                    del self.command_states[cmd_id]
                    
                    try:
                        # 尝试解析JSON格式的录屏命令
                        screen_commands = json.loads(cmd_content)
                        stop_cmd = screen_commands.get('stop', '')
                        export_cmd = screen_commands.get('export', '')
                        
                        # 替换时间戳占位符
                        stop_cmd = stop_cmd.replace('{timestamp}', timestamp)
                        export_cmd = export_cmd.replace('{timestamp}', timestamp)
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是JSON格式，使用原有逻辑（兼容旧版本）
                        stop_cmd = cmd_content.replace('start', 'stop') if 'start' in cmd_content else cmd_content + ' stop'
                        export_cmd = ''
                        
                        # 替换时间戳占位符
                        stop_cmd = stop_cmd.replace('{timestamp}', timestamp)
                        export_cmd = export_cmd.replace('{timestamp}', timestamp)
                    
                    self.log_message(f"⏹️ 结束录屏并导出: {cmd_name} (时间戳: {timestamp})", info=True)
                    
                    # 更新按钮显示状态
                    self.update_recording_button_state(cmd, False)
                    
                    # 执行结束录屏命令
                    if stop_cmd:
                        self.run_command_with_progress(stop_cmd, f"结束录屏 {cmd_name}")
                    
                    # 执行导出命令（如果有）
                    if export_cmd:
                        # 延迟执行导出命令，确保停止命令先完成
                        QTimer.singleShot(2000, lambda: self.run_command_with_progress(export_cmd, f"导出录屏 {cmd_name}"))
                    return
        
            # 显示命令执行提示
            self.log_message(f"准备执行: {cmd_name}", info=True)
            
            # 创建命令执行动画效果
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.progress_bar.setFormat(f"正在准备 {cmd_name} %p%")
            
            # 进度条动画
            self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
            self.progress_animation.setDuration(800)
            self.progress_animation.setStartValue(0)
            self.progress_animation.setEndValue(20)
            self.progress_animation.setEasingCurve(QEasingCurve.OutCubic)
            self.progress_animation.start()
            
            # 根据命令类型处理
            if cmd_type == 'upload':
                # 选择本地文件
                local_path, _ = QFileDialog.getOpenFileName(self, "选择要上传的文件")
                if not local_path:
                    self.progress_bar.setVisible(False)
                    self.log_message("已取消文件上传", info=True)
                    return
                
                # 获取远程路径
                input_dialog = QInputDialog(self)
                input_dialog.setWindowFlags(input_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
                input_dialog.setInputMode(QInputDialog.TextInput)
                input_dialog.setWindowTitle("远程路径")
                input_dialog.setLabelText("请输入远程设备上的路径:")
                input_dialog.resize(400, 200)
                ok = input_dialog.exec_()
                remote_path = input_dialog.textValue()
                if not ok or not remote_path:
                    self.progress_bar.setVisible(False)
                    self.log_message("已取消文件上传", info=True)
                    return
                
                # 替换命令中的占位符
                cmd_content = cmd_content.replace('{local_path}', f'"{local_path}"')
                cmd_content = cmd_content.replace('{remote_path}', f'"{remote_path}"')
                self.log_message(f"已选择文件: {local_path}", info=True)
                
            elif cmd_type == 'download':
                # 获取远程文件路径
                input_dialog = QInputDialog(self)
                input_dialog.setWindowFlags(input_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
                input_dialog.setInputMode(QInputDialog.TextInput)
                input_dialog.setWindowTitle("远程文件")
                input_dialog.setLabelText("请输入要下载的远程文件路径:")
                input_dialog.resize(400, 200)
                ok = input_dialog.exec_()
                remote_path = input_dialog.textValue()
                if not ok or not remote_path:
                    self.progress_bar.setVisible(False)
                    self.log_message("已取消文件下载", info=True)
                    return
                
                # 选择本地保存路径
                local_path, _ = QFileDialog.getSaveFileName(self, "保存文件到")
                if not local_path:
                    # 如果用户没有选择保存路径，使用当前目录
                    local_path = os.path.join(os.getcwd(), os.path.basename(remote_path))
                
                # 替换命令中的占位符
                cmd_content = cmd_content.replace('{remote_path}', f'"{remote_path}"')
                cmd_content = cmd_content.replace('{local_path}', f'"{local_path}"')
                self.log_message(f"将保存到: {local_path}", info=True)
                
            elif cmd_type == 'screenshot':
                # 自动处理截图命令，不需要用户输入
                import datetime
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                
                # 替换命令中的时间戳占位符
                cmd_content = cmd_content.replace('{timestamp}', timestamp)
                self.log_message(f"截图将保存在程序目录下: screenshot_{timestamp}.png", info=True)
                
            elif cmd_type == 'normal' and '{' in cmd_content and '}' in cmd_content:
                # 处理包含占位符的普通命令
                placeholders = [p.split('}')[0] for p in cmd_content.split('{')[1:]]
                
                for placeholder in placeholders:
                    input_dialog = QInputDialog(self)
                    input_dialog.setWindowFlags(input_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
                    input_dialog.setInputMode(QInputDialog.TextInput)
                    input_dialog.setWindowTitle(f"输入{placeholder}")
                    input_dialog.setLabelText(f"请输入{placeholder}:")
                    input_dialog.resize(400, 200)
                    ok = input_dialog.exec_()
                    value = input_dialog.textValue()
                    if not ok:
                        self.progress_bar.setVisible(False)
                        self.log_message("已取消命令执行", info=True)
                        return
                    
                    cmd_content = cmd_content.replace(f'{{{placeholder}}}', f'"{value}"')
            
            # 更新进度条状态
            self.progress_animation.stop()
            self.progress_animation.setStartValue(20)
            self.progress_animation.setEndValue(40)
            self.progress_animation.setDuration(500)
            self.progress_animation.start()
            
            # 检查是否包含多个命令（分号分隔）
            if ';' in cmd_content and cmd_type == 'normal':
                # 分割命令并依次执行
                commands = [cmd.strip() for cmd in cmd_content.split(';') if cmd.strip()]
                if len(commands) > 1:
                    self.log_message(f"检测到 {len(commands)} 个命令，将依次执行", info=True)
                    self.execute_multiple_commands(commands, cmd_name)
                    return
            
            # 执行单个命令
            QTimer.singleShot(300, lambda: self.run_command(cmd_content))
        
        except Exception as e:
            error_msg = f"执行命令失败: {cmd_name} - {e}"
            logging.error(error_msg, exc_info=True)
            self.log_message(error_msg, error=True)
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setVisible(False)
    
    def execute_multiple_commands(self, commands, cmd_name):
        """依次执行多个命令"""
        try:
            self.command_queue = commands.copy()
            self.current_command_index = 0
            self.total_commands = len(commands)
            self.base_cmd_name = cmd_name
            
            # 开始执行第一个命令
            self.execute_next_command()
            
        except Exception as e:
            error_msg = f"执行多命令失败: {cmd_name} - {e}"
            logging.error(error_msg, exc_info=True)
            self.log_message(error_msg, error=True)
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setVisible(False)
    
    def execute_next_command(self):
        """执行队列中的下一个命令"""
        if self.current_command_index < len(self.command_queue):
            current_cmd = self.command_queue[self.current_command_index]
            self.current_command_index += 1
            
            self.log_message(f"执行命令 {self.current_command_index}/{self.total_commands}: {current_cmd}", info=True)
            
            # 更新进度条显示
            progress_percent = int((self.current_command_index / self.total_commands) * 100)
            self.progress_bar.setFormat(f"执行命令 {self.current_command_index}/{self.total_commands} - {self.base_cmd_name} {progress_percent}%")
            
            # 执行当前命令
            self.run_command(current_cmd)
        else:
            # 所有命令执行完成
            self.log_message(f"所有命令执行完成: {self.base_cmd_name}", success=True)
            self.command_queue = None
            self.current_command_index = 0
            # 调用完成清理方法
            self.finish_all_commands(True)
    
    def run_command(self, command):
        try:
            logging.info(f"准备运行命令: {command}")
            
            # 如果有正在运行的命令，先停止它
            if self.command_thread and self.command_thread.isRunning():
                logging.info("停止之前运行的命令")
                self.command_thread.stop()
                self.command_thread.wait()
            
            # 创建并启动新的命令线程，传递当前主题
            current_theme = self.themes[self.current_theme]
            self.command_thread = CommandThread(command, current_theme)
            self.command_thread.output_signal.connect(self.update_terminal)
            self.command_thread.progress_signal.connect(self.update_progress)
            self.command_thread.finished_signal.connect(self.command_finished)
            
            # 显示进度条并更新状态
            self.progress_bar.setValue(40)
            self.progress_bar.setVisible(True)
            self.progress_bar.setFormat("正在执行命令 %p%")
            
            # 添加命令执行提示到终端，使用主题颜色，并在其后加一空行，便于与输出分隔
            self.terminal.moveCursor(QTextCursor.End)
            prompt_color = current_theme['accent_color']
            self.terminal.append(f"<span style='color:{prompt_color}; font-weight:bold; font-size:18px;'>$ {command}</span>")
            self.terminal.append("")
            self.terminal.moveCursor(QTextCursor.End)
            
            # 更新进度条动画
            self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
            self.progress_animation.setStartValue(40)
            self.progress_animation.setEndValue(70)
            self.progress_animation.setDuration(1000)
            self.progress_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.progress_animation.start()
            
            # 禁用所有命令按钮，直到命令执行完成
            for i in range(self.commands_grid.count()):
                widget = self.commands_grid.itemAt(i).widget()
                if widget:
                    widget.setEnabled(False)
                    
            # 启动线程
            self.command_thread.start()
            logging.info("命令线程已启动")
        
        except Exception as e:
            error_msg = f"运行命令失败: {command} - {e}"
            logging.error(error_msg, exc_info=True)
            self.log_message(error_msg, error=True)
            if hasattr(self, 'progress_bar'):
                self.progress_bar.setVisible(False)
            # 重新启用按钮
            for i in range(self.commands_grid.count()):
                widget = self.commands_grid.itemAt(i).widget()
                if widget:
                    widget.setEnabled(True)

    def update_recording_button_state(self, cmd, is_recording):
        """更新录屏按钮的显示状态"""
        # 查找对应的按钮并更新其显示
        for i in range(self.commands_grid.count()):
            widget = self.commands_grid.itemAt(i).widget()
            if widget and hasattr(widget, 'property'):
                # 检查按钮是否对应当前命令
                button_cmd = widget.property('command_data')
                if button_cmd and button_cmd.get('name') == cmd.get('name'):
                    theme = self.themes[self.current_theme]
                    if is_recording:
                        # 录屏中状态：红色边框，显示停止图标
                        widget.setStyleSheet(f"""
                            QPushButton {{
                                background: {theme['button_bg']};
                                color: #ff4444;
                                border: 3px solid #ff4444;
                                border-radius: 12px;
                                font-weight: bold;
                                font-size: 14px;
                                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                                text-align: center;
                                min-height: 65px;
                            }}
                            QPushButton:hover {{
                                background: {theme['button_hover']};
                                border: 3px solid #ff6666;
                            }}
                        """)
                        # 更新按钮文本显示录屏状态
                        icon_symbol = "⏹️"  # 停止图标
                        display_name = self.truncate_text(cmd['name'])
                        widget.setText(f"{icon_symbol} {display_name}")
                    else:
                        # 正常状态：恢复原始样式
                        widget.setStyleSheet(f"""
                            QPushButton {{
                                background: {theme['button_bg']};
                                color: {theme['button_text']};
                                border: 3px solid {theme['button_border']};
                                border-radius: 12px;
                                font-weight: bold;
                                font-size: 14px;
                                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                                text-align: center;
                                min-height: 65px;
                            }}
                            QPushButton:hover {{
                                background: {theme['button_hover']};
                                border: 3px solid {theme['accent_color']};
                            }}
                        """)
                        # 恢复原始按钮文本
                        icon_symbol = self.get_command_icon_symbol(cmd.get('icon', 'terminal'))
                        display_name = self.truncate_text(cmd['name'])
                        widget.setText(f"{icon_symbol} {display_name}")
                    break

    def run_command_with_progress(self, command, description):
        """执行命令并显示进度"""
        # 创建命令执行动画效果
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat(f"正在执行 {description} %p%")
        
        # 进度条动画
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(800)
        self.progress_animation.setStartValue(0)
        self.progress_animation.setEndValue(20)
        self.progress_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.progress_animation.start()
        
        # 延迟执行命令
        QTimer.singleShot(300, lambda: self.run_command(command))

    def copy_command_text(self, cmd):
        clipboard = QApplication.clipboard()
        clipboard.setText(cmd.get('command', ''))
        self.log_message("命令已复制到剪贴板", info=True)

    def open_edit_dialog(self, cmd):
        # 防止重复打开对话框
        if hasattr(self, '_edit_dialog_open') and self._edit_dialog_open:
            return
        
        try:
            self._edit_dialog_open = True
            # 打开对话框并自动定位到指定命令进行编辑
            dialog = CommandManagerDialog(self.commands, self)
            def do_focus():
                try:
                    # 1) 切到列表页
                    tabs = dialog.findChild(QTabWidget)
                    if tabs:
                        tabs.setCurrentIndex(0)
                    # 2) 在列表中选中该命令
                    for i in range(dialog.command_list.count()):
                        item = dialog.command_list.item(i)
                        data = item.data(Qt.UserRole)
                        if data.get('name') == cmd.get('name') and data.get('command') == cmd.get('command'):
                            dialog.command_list.setCurrentRow(i)
                            break
                    # 3) 触发编辑
                    dialog.edit_command()
                except Exception as e:
                    print(f"对话框焦点设置出错: {e}")
            QTimer.singleShot(0, do_focus)
            dialog.exec_()
        except Exception as e:
            print(f"打开编辑对话框出错: {e}")
        finally:
            self._edit_dialog_open = False

    def delete_command_from_ui(self, cmd):
        # 根据名称和内容匹配删除
        before = len(self.commands)
        self.commands = [c for c in self.commands if not (c.get('name') == cmd.get('name') and c.get('command') == cmd.get('command'))]
        if len(self.commands) != before:
            # 将命令移动到回收站
            self.move_to_recycle_bin(cmd)
            self.save_config()
            self.update_command_buttons()
            self.log_message(f"命令 '{cmd['name']}' 已移至回收站", info=True)
    
    def update_terminal(self, text):
        # 更新终端输出
        self.terminal.moveCursor(QTextCursor.End)
        self.terminal.insertPlainText(text)
        self.terminal.moveCursor(QTextCursor.End)
    
    def update_progress(self, value):
        # 更新进度条
        self.progress_bar.setValue(value)
    
    def command_finished(self, success, message):
        # 命令执行完成
        self.progress_animation.stop()
        
        # 检查是否在多命令执行模式
        if hasattr(self, 'command_queue') and self.command_queue is not None:
            # 多命令执行模式
            if success:
                self.log_message(f"命令 {self.current_command_index}/{self.total_commands} 执行成功", success=True)
                # 继续执行下一个命令
                QTimer.singleShot(500, self.execute_next_command)
            else:
                # 命令失败，询问是否继续
                self.log_message(f"命令 {self.current_command_index}/{self.total_commands} 执行失败: {message}", error=True)
                reply = QMessageBox.question(self, "命令执行失败", 
                                           f"命令 {self.current_command_index}/{self.total_commands} 执行失败。\n\n是否继续执行剩余命令？",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    QTimer.singleShot(500, self.execute_next_command)
                else:
                    # 用户选择停止，清理多命令状态
                    self.command_queue = None
                    self.current_command_index = 0
                    self.finish_all_commands(False)
            return
        
        # 单命令执行模式
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setStartValue(self.progress_bar.value())
        self.progress_animation.setEndValue(100 if success else 0)
        self.progress_animation.setDuration(500)
        self.progress_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.progress_animation.start()
        
        # 添加完成消息
        if success:
            self.log_message(message, success=True)
            self.progress_bar.setFormat("命令执行成功 100%")
        else:
            self.log_message(message, error=True)
            self.progress_bar.setFormat("命令执行失败")
        
        # 重新启用所有命令按钮
        for i in range(self.commands_grid.count()):
            widget = self.commands_grid.itemAt(i).widget()
            if widget:
                widget.setEnabled(True)
                
                # 重新应用悬浮提示样式
                self.apply_button_tooltip_style(widget)
                
                # 添加按钮启用动画
                enable_anim = QPropertyAnimation(widget, b"geometry")
                enable_anim.setDuration(300)
                current_geo = widget.geometry()
                enable_anim.setStartValue(current_geo)
                enable_anim.setEndValue(QRect(current_geo.x(), current_geo.y(), current_geo.width(), current_geo.height()))
                enable_anim.setEasingCurve(QEasingCurve.OutBack)
                enable_anim.start()
        
        # 播放提示音
        if success:
            QApplication.beep()
            
        # 3秒后隐藏进度条
        QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))
    
    def finish_all_commands(self, success):
        """完成所有命令执行的清理工作"""
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setStartValue(self.progress_bar.value())
        self.progress_animation.setEndValue(100 if success else 0)
        self.progress_animation.setDuration(500)
        self.progress_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.progress_animation.start()
        
        if success:
            self.progress_bar.setFormat("所有命令执行完成 100%")
        else:
            self.progress_bar.setFormat("命令执行中断")
        
        # 重新启用所有命令按钮
        for i in range(self.commands_grid.count()):
            widget = self.commands_grid.itemAt(i).widget()
            if widget:
                widget.setEnabled(True)
                self.apply_button_tooltip_style(widget)
        
        # 播放提示音
        if success:
            QApplication.beep()
            
        # 3秒后隐藏进度条
        QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))
    
    def log_message(self, message, error=False, success=False, info=False):
        # 添加带颜色和样式的消息到终端
        self.terminal.moveCursor(QTextCursor.End)
        
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 获取当前主题
        theme = self.themes[self.current_theme]
        
        # 根据消息类型设置颜色和图标
        if error:
            color = "#e74c3c"
            icon = "🔴"
            style = "font-weight:bold;"
        elif success:
            color = "#2ecc71"
            icon = "🟢"
            style = "font-weight:bold;"
        elif info:
            color = theme['accent_color']
            icon = "🔵"
            style = ""
        else:
            color = theme['terminal_text']
            icon = "⚡"
            style = ""
        
        # 时间戳颜色根据主题调整
        timestamp_color = theme['accent_color'] if self.current_theme != 'light' else '#6c757d'
        
        # 创建带时间戳、图标和样式的消息
        formatted_message = f"<span style='color:{timestamp_color}; font-size:18px;'>[{current_time}]</span> <span style='color:{color}; {style} font-size:18px;'>{icon} {message}</span>"
        
        # 插入带样式的文本
        self.terminal.append(formatted_message)
        self.terminal.moveCursor(QTextCursor.End)
        
        # 如果是错误消息，播放提示音
        if error:
            QApplication.beep()
    
    def clear_terminal(self):
        # 清除终端输出
        self.terminal.clear()
        # 使用主题颜色显示清除消息
        theme = self.themes[self.current_theme]
        self.terminal.append(f"<span style='color:{theme['terminal_text']}; font-size:18px;'>终端已清除。准备就绪...</span>")
    
    def show_command_manager(self):
        # 防止重复打开对话框
        if hasattr(self, '_command_manager_dialog_open') and self._command_manager_dialog_open:
            return
            
        try:
            self._command_manager_dialog_open = True
            # 显示命令管理对话框
            dialog = CommandManagerDialog(self.commands, self)
            # 设置默认显示模板库选项卡
            tabs = dialog.findChild(QTabWidget)
            if tabs:
                tabs.setCurrentIndex(2)  # 索引2对应模板库选项卡
            dialog.exec_()
        finally:
            self._command_manager_dialog_open = False
        # 关闭返回后刷新（防止子对话框变更未刷）
        self.update_command_buttons()
    
    def show_recycle_bin(self):
        """显示回收站对话框"""
        dialog = RecycleBinDialog(self.deleted_commands, self)
        dialog.exec_()
        # 刷新回收站数据
        self.load_deleted_commands()
    
    def ready_clicked(self, event):
        """READY标签点击事件处理"""
        self.ready_click_count += 1
        self.log_message(f"🎵 READY点击次数: {self.ready_click_count}/5", info=True)
        
        if self.ready_click_count >= 5:
            # 点击5次后打开音乐播放器
            self.ready_click_count = 0  # 重置计数
            self.show_music_player()
        
        # 调用原始的鼠标点击事件
        QLabel.mousePressEvent(self.terminal_status, event)
    
    def terminal_clicked(self, event):
        """终端区域点击事件处理"""
        # 调用原始的鼠标点击事件
        QTextEdit.mousePressEvent(self.terminal, event)
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        # 调用父类的键盘事件处理
        super().keyPressEvent(event)
    
    def show_music_player(self):
        """显示音乐播放器"""
        if self.music_player_dialog is None:
            self.music_player_dialog = MusicPlayerDialog(self)
        
        self.log_message("🎵 音乐播放器已启动！", success=True)
        self.music_player_dialog.show()
        self.music_player_dialog.raise_()
        self.music_player_dialog.activateWindow()
    
    def scale_down(self):
        """缩小界面"""
        if self.scale_factor > 0.5:
            self.scale_factor -= 0.1
            self.apply_scale()
    
    def scale_up(self):
        """放大界面"""
        if self.scale_factor < 2.0:
            self.scale_factor += 0.1
            self.apply_scale()
    
    def scale_reset(self):
        """重置界面大小"""
        self.scale_factor = 1.0
        self.apply_scale()
    
    def apply_scale(self):
        """应用缩放比例"""
        # 更新重置按钮显示的百分比
        percentage = int(self.scale_factor * 100)
        self.scale_reset_btn.setText(f"{percentage}%")
        
        # 获取当前窗口大小
        current_size = self.size()
        
        # 计算新的窗口大小
        base_width = 1400  # 基础宽度
        base_height = 900  # 基础高度
        
        new_width = int(base_width * self.scale_factor)
        new_height = int(base_height * self.scale_factor)
        
        # 设置新的窗口大小
        self.resize(new_width, new_height)
        
        # 居中显示窗口
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - new_width) // 2
        y = (screen.height() - new_height) // 2
        self.move(x, y)
    
    def update_scale_buttons_style(self):
        """更新缩放按钮样式以适配当前主题"""
        if not hasattr(self, 'scale_down_btn'):
            return
            
        theme = self.themes[self.current_theme]
        scale_button_style = f"""
            QPushButton {{
                background-color: {theme['window_bg']};
                color: {theme['accent_color']};
                border: 2px solid {theme['accent_color']};
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                padding: 2px;
                margin: 1px;
            }}
            QPushButton:hover {{
                background-color: {theme['accent_color']};
                color: {theme['window_bg']};
                border-color: {theme['accent_color']};
            }}
            QPushButton:pressed {{
                background-color: {theme['button_text']};
                color: {theme['window_bg']};
                border-color: {theme['button_text']};
            }}
            QPushButton:focus {{
                outline: none;
                background-color: {theme['window_bg']};
                border: 2px solid {theme['accent_color']};
            }}
        """
        
        self.scale_down_btn.setStyleSheet(scale_button_style)
        self.scale_reset_btn.setStyleSheet(scale_button_style)
        self.scale_up_btn.setStyleSheet(scale_button_style)

    def show_log_viewer(self):
        """显示日志查看器"""
        try:
            logging.info("打开日志查看器")
            
            # 创建日志查看对话框
            log_dialog = QDialog(self)
            log_dialog.setWindowTitle("崩溃日志查看器")
            log_dialog.setWindowFlags(log_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            log_dialog.resize(800, 600)
            
            # 设置对话框样式
            theme = self.themes[self.current_theme]
            log_dialog.setStyleSheet(f"""
                QDialog {{
                    background: {theme['window_bg']};
                    color: {theme['terminal_text']};
                }}
                QTextEdit {{
                    background: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 8px;
                    padding: 10px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 12px;
                }}
                QPushButton {{
                    background: {theme['button_bg']};
                    color: {theme['button_text']};
                    border: 2px solid {theme['button_border']};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 100px;
                }}
                QPushButton:hover {{
                    background: {theme['button_hover']};
                }}
                QLabel {{
                    color: {theme['terminal_text']};
                    font-weight: bold;
                    font-size: 14px;
                }}
            """)
            
            layout = QVBoxLayout(log_dialog)
            
            # 标题
            title_label = QLabel("📋 应用程序崩溃日志")
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # 日志文件路径信息
            path_label = QLabel(f"日志文件位置: {LOG_FILE}")
            layout.addWidget(path_label)
            
            # 日志内容显示区域
            log_text = QTextEdit()
            log_text.setReadOnly(True)
            
            # 读取日志文件内容
            try:
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                        if log_content.strip():
                            log_text.setPlainText(log_content)
                        else:
                            log_text.setPlainText("日志文件为空，暂无崩溃记录。")
                else:
                    log_text.setPlainText("日志文件不存在，可能是首次运行或尚未发生崩溃。")
            except Exception as e:
                log_text.setPlainText(f"读取日志文件失败: {e}")
                logging.error(f"读取日志文件失败: {e}", exc_info=True)
            
            layout.addWidget(log_text)
            
            # 按钮区域
            button_layout = QHBoxLayout()
            
            # 刷新按钮
            refresh_btn = QPushButton("🔄 刷新")
            refresh_btn.clicked.connect(lambda: self.refresh_log_content(log_text))
            button_layout.addWidget(refresh_btn)
            
            # 清空日志按钮
            clear_btn = QPushButton("🗑️ 清空日志")
            clear_btn.clicked.connect(lambda: self.clear_log_file(log_text))
            button_layout.addWidget(clear_btn)
            
            # 打开日志文件夹按钮
            folder_btn = QPushButton("📁 打开文件夹")
            folder_btn.clicked.connect(self.open_log_folder)
            button_layout.addWidget(folder_btn)
            
            layout.addLayout(button_layout)
            
            # 显示对话框
            log_dialog.exec_()
            
        except Exception as e:
            error_msg = f"打开日志查看器失败: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)
    
    def refresh_log_content(self, log_text):
        """刷新日志内容"""
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                    if log_content.strip():
                        log_text.setPlainText(log_content)
                    else:
                        log_text.setPlainText("日志文件为空，暂无崩溃记录。")
            else:
                log_text.setPlainText("日志文件不存在，可能是首次运行或尚未发生崩溃。")
            logging.info("日志内容已刷新")
        except Exception as e:
            error_msg = f"刷新日志内容失败: {e}"
            logging.error(error_msg, exc_info=True)
            log_text.setPlainText(error_msg)
    
    def clear_log_file(self, log_text):
        """清空日志文件"""
        try:
            reply = QMessageBox.question(self, "确认清空", "确定要清空所有日志记录吗？", 
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, 'w', encoding='utf-8') as f:
                        f.write('')
                log_text.setPlainText("日志已清空")
                logging.info("日志文件已清空")
                QMessageBox.information(self, "清空成功", "日志文件已清空")
        except Exception as e:
            error_msg = f"清空日志文件失败: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)
    
    def open_log_folder(self):
        """打开日志文件夹"""
        try:
            log_dir = os.path.dirname(LOG_FILE)
            if os.path.exists(log_dir):
                os.startfile(log_dir)
                logging.info(f"已打开日志文件夹: {log_dir}")
            else:
                QMessageBox.warning(self, "警告", "日志文件夹不存在")
        except Exception as e:
            error_msg = f"打开日志文件夹失败: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)
    
    def open_current_folder(self):
        """打开当前命令管理器文件夹"""
        try:
            current_dir = APP_BASE_DIR
            if os.path.exists(current_dir):
                os.startfile(current_dir)
                logging.info(f"已打开当前文件夹: {current_dir}")
                self.log_message(f"已打开文件夹: {current_dir}", info=True)
            else:
                QMessageBox.warning(self, "警告", "当前文件夹不存在")
        except Exception as e:
            error_msg = f"打开当前文件夹失败: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)

# 命令管理对话框
class CommandManagerDialog(QDialog):
    # 添加信号，用于通知主窗口更新命令按钮
    commands_changed = pyqtSignal()
    
    def __init__(self, commands, parent=None):
        super().__init__(parent)
        # 去掉标题栏的问号按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.commands = commands.copy()
        self.parent_window = parent
        self.init_ui()
    
    def init_ui(self):
        # 设置对话框属性
        self.setWindowTitle("命令管理")
        self.setMinimumSize(600, 400)
        
        # 设置对话框图标
        self.set_dialog_icon()
        
        # 应用主题样式
        self.apply_theme()
        
        # 主布局
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # 命令列表选项卡
        commands_tab = QWidget()
        commands_layout = QVBoxLayout(commands_tab)
        
        # 命令列表
        self.command_list = QListWidget()
        self.command_list.setSelectionMode(QListWidget.SingleSelection)
        self.update_command_list()
        commands_layout.addWidget(self.command_list)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        
        # 添加按钮
        add_btn = QPushButton("添加命令")
        add_btn.clicked.connect(self.add_command)
        buttons_layout.addWidget(add_btn)
        
        # 编辑按钮
        edit_btn = QPushButton("编辑命令")
        edit_btn.clicked.connect(self.edit_command)
        buttons_layout.addWidget(edit_btn)
        
        # 删除按钮
        delete_btn = QPushButton("删除命令")
        delete_btn.clicked.connect(self.delete_command)
        buttons_layout.addWidget(delete_btn)
        
        # 上移按钮
        up_btn = QPushButton("上移")
        up_btn.clicked.connect(self.move_command_up)
        buttons_layout.addWidget(up_btn)
        
        # 下移按钮
        down_btn = QPushButton("下移")
        down_btn.clicked.connect(self.move_command_down)
        buttons_layout.addWidget(down_btn)
        
        commands_layout.addLayout(buttons_layout)
        
        # 添加命令选项卡
        add_tab = QWidget()
        add_layout = QFormLayout(add_tab)
        
        # 命令名称
        self.name_input = QLineEdit()
        add_layout.addRow("命令名称:", self.name_input)
        
        # 命令内容
        command_row = QWidget()
        command_row_layout = QHBoxLayout(command_row)
        command_row_layout.setContentsMargins(0, 0, 0, 0)
        
        self.command_input = QLineEdit()
        command_row_layout.addWidget(self.command_input)
        
        # 添加扩展按钮
        expand_btn = QPushButton("📝")
        expand_btn.setToolTip("扩大输入框")
        expand_btn.setFixedSize(30, 30)
        expand_btn.clicked.connect(self.expand_command_input)
        command_row_layout.addWidget(expand_btn)
        
        add_layout.addRow("命令内容:", command_row)
        
        # 命令类型
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "normal", "upload", "download", "screenshot", "screen_record", "terminal", "device", "file", "app",
            "system", "network", "memory", "cpu", "process", "service", "user", "group",
            "log", "config", "install", "uninstall", "update", "backup", "restore",
            "compress", "extract", "encrypt", "decrypt", "database", "web", "api"
        ])
        add_layout.addRow("命令类型:", self.type_combo)
        
        # 录屏专用字段（初始隐藏）
        self.screen_record_widget = QWidget()
        screen_record_layout = QFormLayout(self.screen_record_widget)
        
        # 开始录屏命令
        start_command_row = QWidget()
        start_command_row_layout = QHBoxLayout(start_command_row)
        start_command_row_layout.setContentsMargins(0, 0, 0, 0)
        
        self.start_command_input = QLineEdit()
        self.start_command_input.setPlaceholderText("例如: hdc shell screenrecord /data/local/tmp/screen_{timestamp}.mp4")
        start_command_row_layout.addWidget(self.start_command_input)
        
        # 添加扩展按钮
        start_expand_btn = QPushButton("📝")
        start_expand_btn.setToolTip("扩大输入框")
        start_expand_btn.setFixedSize(30, 30)
        start_expand_btn.clicked.connect(lambda: self._expand_input_field(self.start_command_input))
        start_command_row_layout.addWidget(start_expand_btn)
        
        screen_record_layout.addRow("开始录屏命令:", start_command_row)
        
        # 停止录屏命令
        stop_command_row = QWidget()
        stop_command_row_layout = QHBoxLayout(stop_command_row)
        stop_command_row_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stop_command_input = QLineEdit()
        self.stop_command_input.setPlaceholderText("例如: hdc shell pkill screenrecord")
        stop_command_row_layout.addWidget(self.stop_command_input)
        
        # 添加扩展按钮
        stop_expand_btn = QPushButton("📝")
        stop_expand_btn.setToolTip("扩大输入框")
        stop_expand_btn.setFixedSize(30, 30)
        stop_expand_btn.clicked.connect(lambda: self._expand_input_field(self.stop_command_input))
        stop_command_row_layout.addWidget(stop_expand_btn)
        
        screen_record_layout.addRow("停止录屏命令:", stop_command_row)
        
        # 导出命令
        export_command_row = QWidget()
        export_command_row_layout = QHBoxLayout(export_command_row)
        export_command_row_layout.setContentsMargins(0, 0, 0, 0)
        
        self.export_command_input = QLineEdit()
        self.export_command_input.setPlaceholderText("例如: hdc file recv /data/local/tmp/screen_{timestamp}.mp4 ./")
        export_command_row_layout.addWidget(self.export_command_input)
        
        # 添加扩展按钮
        export_expand_btn = QPushButton("📝")
        export_expand_btn.setToolTip("扩大输入框")
        export_expand_btn.setFixedSize(30, 30)
        export_expand_btn.clicked.connect(lambda: self._expand_input_field(self.export_command_input))
        export_command_row_layout.addWidget(export_expand_btn)
        
        screen_record_layout.addRow("导出命令:", export_command_row)
        
        add_layout.addRow(self.screen_record_widget)
        self.screen_record_widget.setVisible(False)
        
        # 添加类型变化监听，显示当前选择的图标
        self.icon_preview = QLabel()
        self.icon_preview.setStyleSheet("font-size: 24px;")
        
        # 初始显示默认图标
        self.update_icon_preview(self.type_combo.currentText())
        
        # 连接类型选择变化信号
        self.type_combo.currentTextChanged.connect(self.update_icon_preview)
        self.type_combo.currentTextChanged.connect(self.toggle_screen_record_fields)
        
        # 添加图标预览
        add_layout.addRow("图标预览:", self.icon_preview)
        
        # 提示信息
        help_text = QLabel("提示: 使用 {placeholder} 语法添加占位符，例如 {local_path} 或 {remote_path}")
        help_text.setWordWrap(True)
        add_layout.addRow(help_text)
        
        # 添加按钮
        add_command_btn = QPushButton("添加命令")
        add_command_btn.clicked.connect(self.add_command_from_form)
        add_layout.addRow(add_command_btn)
        
        # 模板库选项卡
        templates_tab = QWidget()
        templates_layout = QVBoxLayout(templates_tab)
        
        # 模板分类和列表的水平布局
        templates_split = QHBoxLayout()
        
        # 左侧分类列表
        self.category_list = QListWidget()
        self.category_list.setFixedWidth(150)
        templates_split.addWidget(self.category_list)
        
        # 右侧模板列表
        templates_right = QVBoxLayout()
        self.templates_list = QListWidget()
        templates_right.addWidget(self.templates_list)
        
        # 模板详情
        self.template_detail = QTextEdit()
        self.template_detail.setReadOnly(True)
        self.template_detail.setFixedHeight(80)
        templates_right.addWidget(self.template_detail)
        
        # 添加到模板按钮
        add_template_btn = QPushButton("添加到我的命令")
        add_template_btn.clicked.connect(self.add_template_to_commands)
        templates_right.addWidget(add_template_btn)
        
        templates_split.addLayout(templates_right)
        templates_layout.addLayout(templates_split)
        
        # 加载模板数据
        self.load_templates()
        
        # 连接分类选择事件
        self.category_list.currentRowChanged.connect(self.on_category_selected)
        
        # 连接模板选择事件
        self.templates_list.currentRowChanged.connect(self.on_template_selected)
        
        # 添加选项卡
        tabs.addTab(commands_tab, "命令列表")
        tabs.addTab(add_tab, "添加命令")
        tabs.addTab(templates_tab, "模板库")
        
        # 对话框按钮
        buttons = QHBoxLayout()
        save_btn = QPushButton("保存更改 (Ctrl+S)")
        cancel_btn = QPushButton("取消 (Esc)")
        
        save_btn.clicked.connect(self.save_changes)
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        # 快捷键：保存 / 关闭
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_changes)
        QShortcut(QKeySequence("Esc"), self, activated=self.reject)
    
    def update_icon_preview(self, cmd_type):
        """根据命令类型更新图标预览"""
        if self.parent_window:
            # 使用父窗口的图标映射方法获取图标
            icon_symbol = self.parent_window.get_command_icon_symbol(cmd_type)
            self.icon_preview.setText(icon_symbol)
        else:
            # 如果没有父窗口，使用默认图标
            self.icon_preview.setText("⭐")
    
    def toggle_screen_record_fields(self, cmd_type):
        """根据命令类型显示或隐藏录屏专用字段"""
        is_screen_record = cmd_type == "screen_record"
        self.screen_record_widget.setVisible(is_screen_record)
        # 当选择录屏类型时，隐藏普通命令输入框
        self.command_input.setVisible(not is_screen_record)
    
    def apply_theme(self):
        """根据父窗口主题应用样式"""
        if not self.parent_window:
            return
            
        # 获取父窗口的主题配置
        theme = self.parent_window.themes[self.parent_window.current_theme]
        
        # 根据主题设置样式
        if self.parent_window.current_theme == 'light':
            # Light主题样式 - 使用更明亮的颜色
            self.setStyleSheet(f"""
                QDialog {{
                    background: #ffffff;
                    color: #000000;
                }}
                QTabWidget {{
                    background-color: transparent;
                    color: #000000;
                }}
                QTabWidget::pane {{
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    background-color: #ffffff;
                }}
                QTabWidget::tab-bar {{
                    alignment: center;
                }}
                QTabBar::tab {{
                    background: #f8f9fa;
                    color: #000000;
                    border: 2px solid #007bff;
                    border-bottom: none;
                    border-radius: 6px 6px 0 0;
                    padding: 8px 16px;
                    margin-right: 2px;
                    font-weight: bold;
                }}
                QTabBar::tab:selected {{
                    background: #007bff;
                    color: #ffffff;
                }}
                QTabBar::tab:hover {{
                    background: rgba(0, 123, 255, 0.1);
                    color: #000000;
                }}
                QListWidget {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 12px;
                    selection-background-color: #007bff;
                    selection-color: #ffffff;
                }}
                QListWidget::item {{
                    background-color: #f8f9fa;
                    color: #000000;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 8px;
                    margin: 2px;
                }}
                QListWidget::item:selected {{
                    background-color: #007bff;
                    color: #ffffff;
                    border-color: #007bff;
                    font-weight: 900;
                }}
                QListWidget::item:selected:hover {{
                    background-color: #0056b3;
                    color: #ffffff;
                    border-color: #0056b3;
                    font-weight: 900;
                }}
                QListWidget::item:hover {{
                    background-color: rgba(0, 123, 255, 0.1);
                    border-color: #007bff;
                    color: #000000;
                }}
                QLabel {{
                    color: #000000;
                    font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                    font-size: 12px;
                }}
                QLineEdit {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 2px solid #007bff;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                    font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                }}
                QLineEdit:focus {{
                    border-color: #0056b3;
                    background-color: #f8f9fa;
                }}
                QComboBox {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 2px solid #007bff;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                    font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                }}
                QComboBox:hover {{
                    border-color: #0056b3;
                }}
                QComboBox::drop-down {{
                    border: none;
                    background-color: #007bff;
                    border-radius: 3px;
                    width: 20px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #ffffff;
                    width: 0;
                    height: 0;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #ffffff;
                    color: #000000;
                    border: 2px solid #007bff;
                    selection-background-color: #007bff;
                    selection-color: #ffffff;
                }}
                QPushButton {{
                    background: #f8f9fa;
                    color: #000000;
                    border: 2px solid #007bff;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 12px;
                    font-family: 'Arial', 'Microsoft YaHei', sans-serif;
                }}
                QPushButton:hover {{
                    background: #007bff;
                    color: #ffffff;
                }}
                QPushButton:pressed {{
                    background: #0056b3;
                    color: #ffffff;
                }}
            """)
        else:
            # Dark/Cyber主题样式
            self.setStyleSheet(f"""
                QDialog {{
                    background: {theme['window_bg']};
                    color: {theme['accent_color']};
                }}
                QTabWidget {{
                    background-color: transparent;
                    color: {theme['accent_color']};
                }}
                QTabWidget::pane {{
                    border: 2px solid {theme['accent_color']};
                    border-radius: 8px;
                    background-color: {theme['terminal_bg']};
                }}
                QTabWidget::tab-bar {{
                    alignment: center;
                }}
                QTabBar::tab {{
                    background: {theme['button_bg']};
                    color: {theme['accent_color']};
                    border: 2px solid {theme['accent_color']};
                    border-bottom: none;
                    border-radius: 6px 6px 0 0;
                    padding: 8px 16px;
                    margin-right: 2px;
                    font-weight: bold;
                }}
                QTabBar::tab:selected {{
                    background: {theme['button_hover']};
                    color: #000000;
                }}
                QTabBar::tab:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a4a5a, stop:1 #2c5a6a);
                }}
                QListWidget {{
                    background-color: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 12px;
                    selection-background-color: {theme['accent_color']};
                    selection-color: #000000;
                }}
                QListWidget::item {{
                    background-color: #2c3e50;
                    color: {theme['terminal_text']};
                    border: 1px solid #34495e;
                    border-radius: 4px;
                    padding: 8px;
                    margin: 2px;
                }}
                QListWidget::item:selected {{
                    background-color: {'#007bff' if theme['accent_color'] == '#000000' else theme['accent_color']};
                    color: {'#ffffff' if theme['accent_color'] == '#000000' else '#000000'};
                    border-color: {'#007bff' if theme['accent_color'] == '#000000' else '#66ffff'};
                    font-weight: 900;
                }}
                QListWidget::item:selected:hover {{
                    background-color: {'#0056b3' if theme['accent_color'] == '#000000' else theme['accent_color']};
                    color: {'#ffffff' if theme['accent_color'] == '#000000' else '#ffffff'};
                    border-color: {'#0056b3' if theme['accent_color'] == '#000000' else '#66ffff'};
                    font-weight: 900;
                }}
                QLabel {{
                    color: {theme['accent_color']};
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 12px;
                }}
                QLineEdit {{
                    background-color: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                    font-family: 'Consolas', 'Monaco', monospace;
                }}
                QLineEdit:focus {{
                    border-color: #66ffff;
                    background-color: #1a2332;
                }}
                QComboBox {{
                    background-color: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                    font-family: 'Consolas', 'Monaco', monospace;
                }}
                QComboBox:hover {{
                    border-color: #66ffff;
                }}
                QComboBox::drop-down {{
                    border: none;
                    background-color: {theme['accent_color']};
                    border-radius: 3px;
                    width: 20px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #000000;
                    width: 0;
                    height: 0;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    selection-background-color: {theme['accent_color']};
                    selection-color: #000000;
                }}
                QPushButton {{
                    background: {theme['button_bg']};
                    color: {theme['accent_color']};
                    border: 2px solid {theme['accent_color']};
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 12px;
                    font-family: 'Consolas', 'Monaco', monospace;
                }}
                QPushButton:hover {{
                    background: {theme['button_hover']};
                    color: #000000;
                }}
                QPushButton:pressed {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #0099cc, stop:1 #006699);
                }}
                QTextEdit {{
                    background-color: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 6px;
                    padding: 8px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 12px;
                    selection-background-color: {theme['accent_color']};
                    selection-color: #000000;
                }}
            """)
    
    def set_dialog_icon(self):
        """设置对话框图标"""
        # 使用类级别的标志来防止重复加载
        if not hasattr(self.__class__, '_global_icon_loaded'):
            self.__class__._global_icon_loaded = False
            
        if self.__class__._global_icon_loaded:
            return
        
        # 获取资源路径
        if getattr(sys, 'frozen', False):
            # 如果是打包的应用，使用_MEIPASS中的资源路径
            try:
                base_path = sys._MEIPASS
                icon_dir = os.path.join(base_path, 'icons')
            except Exception:
                # 如果无法获取_MEIPASS，回退到应用程序目录
                icon_dir = os.path.join(os.path.dirname(sys.executable), 'icons')
        else:
            # 如果是开发环境，使用脚本目录
            icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
        
        # 尝试加载设置图标
        svg_path = os.path.join(icon_dir, 'cyber_settings.svg')
        if os.path.exists(svg_path):
            self.setWindowIcon(QIcon(svg_path))
            print(f"已加载图标: {svg_path}")
            self.__class__._global_icon_loaded = True
        else:
            # 备用方案：使用原始设置图标
            fallback_path = os.path.join(icon_dir, 'gear.svg')
            if os.path.exists(fallback_path):
                self.setWindowIcon(QIcon(fallback_path))
                print(f"已加载备用图标: {fallback_path}")
                self.__class__._global_icon_loaded = True
            else:
                print(f"无法加载图标，路径不存在: {svg_path} 或 {fallback_path}")
                # 尝试使用终端图标作为最后的备用方案
                terminal_icon = os.path.join(icon_dir, 'cyber_terminal.ico')
                if os.path.exists(terminal_icon):
                    self.setWindowIcon(QIcon(terminal_icon))
                    print(f"已加载终端图标: {terminal_icon}")
                    self.__class__._global_icon_loaded = True
                else:
                    print("所有图标路径均不存在")
    
    def update_command_list(self):
        # 更新命令列表
        self.command_list.clear()
        for cmd in self.commands:
            item = QListWidgetItem(f"{cmd['name']} ({cmd['command']})")
            item.setData(Qt.UserRole, cmd)
            self.command_list.addItem(item)
    
    def add_command(self):
        # 切换到添加命令选项卡
        parent = self.parent()
        tabs = self.findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(1)
    
    def expand_command_input(self):
        """扩展命令输入框"""
        self._expand_input_field(self.command_input)
    
    def _expand_input_field(self, input_field, parent_dialog=None):
        """通用的输入框扩展方法"""
        # 创建扩展输入对话框
        dialog = QDialog(parent_dialog or self)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.setWindowTitle("命令内容编辑器")
        dialog.setMinimumSize(600, 400)
        
        # 应用主题样式
        try:
            # 尝试获取主题配置
            theme = None
            if hasattr(self, 'parent_window') and self.parent_window:
                theme = self.parent_window.themes[self.parent_window.current_theme]
            elif hasattr(self, 'themes') and hasattr(self, 'current_theme'):
                theme = self.themes[self.current_theme]
            
            if theme:
                dialog.setStyleSheet(f"""
                    QDialog {{
                         background: {theme['window_bg']};
                         color: {theme['terminal_text']};
                    }}
                    QTextEdit {{
                        background: {theme['terminal_bg']};
                        color: {theme['terminal_text']};
                        border: 2px solid {theme['accent_color']};
                        border-radius: 8px;
                        padding: 8px;
                        font-family: 'Consolas', 'Monaco', monospace;
                        font-size: 12px;
                    }}
                    QPushButton {{
                        background: {theme['button_bg']};
                        color: {theme['button_text']};
                        border: 2px solid {theme['button_border']};
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background: {theme['button_hover']};
                    }}
                """)
        except Exception as e:
            # 如果主题应用失败，使用默认样式
            print(f"主题应用失败: {e}")
        
        # 布局
        layout = QVBoxLayout(dialog)
        
        # 提示标签
        tip_label = QLabel("💡 提示: 在这里可以更方便地编辑长命令，支持多行输入")
        tip_label.setStyleSheet("color: #888; margin-bottom: 10px;")
        layout.addWidget(tip_label)
        
        # 文本编辑器
        text_edit = QTextEdit()
        text_edit.setPlainText(input_field.text())
        text_edit.setTabStopWidth(40)  # 设置Tab宽度
        layout.addWidget(text_edit)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        buttons_layout.addWidget(ok_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        # 快捷键
        QShortcut(QKeySequence("Ctrl+Return"), dialog, activated=dialog.accept)
        QShortcut(QKeySequence("Escape"), dialog, activated=dialog.reject)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            # 获取编辑后的文本并更新到原输入框
            new_text = text_edit.toPlainText().strip()
            input_field.setText(new_text)
    
    def add_command_from_form(self):
        # 从表单添加命令
        name = self.name_input.text().strip()
        cmd_type = self.type_combo.currentText()
        
        # 根据命令类型自动设置图标
        icon = cmd_type
        
        if not name:
            QMessageBox.warning(self, "输入错误", "命令名称不能为空")
            return
        
        # 处理录屏命令的特殊逻辑
        if cmd_type == "screen_record":
            start_command = self.start_command_input.text().strip()
            stop_command = self.stop_command_input.text().strip()
            export_command = self.export_command_input.text().strip()
            
            if not start_command or not stop_command or not export_command:
                QMessageBox.warning(self, "输入错误", "录屏命令的开始、停止和导出命令都不能为空")
                return
            
            # 将三个命令组合成一个JSON格式的命令
            command = json.dumps({
                "start": start_command,
                "stop": stop_command,
                "export": export_command
            }, ensure_ascii=False)
        else:
            command = self.command_input.text().strip()
            if not command:
                QMessageBox.warning(self, "输入错误", "命令内容不能为空")
                return
        
        # 添加新命令
        self.commands.append({
            "name": name,
            "command": command,
            "type": cmd_type,
            "icon": icon
        })
        
        # 更新列表并清空表单
        self.update_command_list()
        self.name_input.clear()
        if cmd_type == "screen_record":
            self.start_command_input.clear()
            self.stop_command_input.clear()
            self.export_command_input.clear()
        else:
            self.command_input.clear()
        
        # 实时更新主窗口
        if self.parent_window:
            self.parent_window.commands = self.commands.copy()
            self.parent_window.save_config()
            # 延迟更新按钮，避免重复创建
            QTimer.singleShot(100, self.parent_window.update_command_buttons)
        
        # 切换回命令列表选项卡
        tabs = self.findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(0)
    
    def edit_command(self):
        # 编辑选中的命令
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "选择错误", "请先选择要编辑的命令")
            return
        
        # 获取选中的命令
        item = selected_items[0]
        cmd = item.data(Qt.UserRole)
        index = self.command_list.row(item)
        
        # 创建编辑对话框
        dialog = QDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.setWindowTitle("编辑命令")
        dialog.setMinimumWidth(400)
        
        # 表单布局
        layout = QFormLayout(dialog)
        
        # 命令名称
        name_input = QLineEdit(cmd['name'])
        layout.addRow("命令名称:", name_input)
        
        # 命令内容 - 根据命令类型显示不同的输入界面
        cmd_type = cmd.get('type', 'normal')
        
        # 普通命令输入框
        command_row = QWidget()
        command_row_layout = QHBoxLayout(command_row)
        command_row_layout.setContentsMargins(0, 0, 0, 0)
        
        command_input = QLineEdit()
        
        # 录屏命令专用输入框
        screen_record_widget = QWidget()
        screen_record_layout = QVBoxLayout(screen_record_widget)
        screen_record_layout.setContentsMargins(0, 0, 0, 0)
        
        start_command_input = QLineEdit()
        start_command_input.setPlaceholderText("开始录屏命令，例如: hdc shell screenrecord /data/local/tmp/screen.mp4")
        
        stop_command_input = QLineEdit()
        stop_command_input.setPlaceholderText("停止录屏命令，例如: hdc shell pkill -SIGINT screenrecord")
        
        export_command_input = QLineEdit()
        export_command_input.setPlaceholderText("导出命令，例如: hdc file recv /data/local/tmp/screen.mp4 ./screen.mp4")
        
        # 开始录屏命令行
        start_row = QWidget()
        start_row_layout = QHBoxLayout(start_row)
        start_row_layout.setContentsMargins(0, 0, 0, 0)
        start_row_layout.addWidget(start_command_input)
        
        start_expand_btn = QPushButton("📝")
        start_expand_btn.setToolTip("扩大输入框")
        start_expand_btn.setFixedSize(30, 30)
        start_expand_btn.clicked.connect(lambda: self._expand_input_field(start_command_input, dialog))
        start_row_layout.addWidget(start_expand_btn)
        
        # 停止录屏命令行
        stop_row = QWidget()
        stop_row_layout = QHBoxLayout(stop_row)
        stop_row_layout.setContentsMargins(0, 0, 0, 0)
        stop_row_layout.addWidget(stop_command_input)
        
        stop_expand_btn = QPushButton("📝")
        stop_expand_btn.setToolTip("扩大输入框")
        stop_expand_btn.setFixedSize(30, 30)
        stop_expand_btn.clicked.connect(lambda: self._expand_input_field(stop_command_input, dialog))
        stop_row_layout.addWidget(stop_expand_btn)
        
        # 导出命令行
        export_row = QWidget()
        export_row_layout = QHBoxLayout(export_row)
        export_row_layout.setContentsMargins(0, 0, 0, 0)
        export_row_layout.addWidget(export_command_input)
        
        export_expand_btn = QPushButton("📝")
        export_expand_btn.setToolTip("扩大输入框")
        export_expand_btn.setFixedSize(30, 30)
        export_expand_btn.clicked.connect(lambda: self._expand_input_field(export_command_input, dialog))
        export_row_layout.addWidget(export_expand_btn)
        
        screen_record_layout.addWidget(QLabel("开始录屏命令:"))
        screen_record_layout.addWidget(start_row)
        screen_record_layout.addWidget(QLabel("停止录屏命令:"))
        screen_record_layout.addWidget(stop_row)
        screen_record_layout.addWidget(QLabel("导出命令:"))
        screen_record_layout.addWidget(export_row)
        
        # 根据命令类型填充数据
        if cmd_type == 'screen_record':
            try:
                # 尝试解析JSON格式的录屏命令
                screen_commands = json.loads(cmd['command'])
                start_command_input.setText(screen_commands.get('start', ''))
                stop_command_input.setText(screen_commands.get('stop', ''))
                export_command_input.setText(screen_commands.get('export', ''))
                screen_record_widget.setVisible(True)
                command_row.setVisible(False)
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON格式，显示在普通输入框中
                command_input.setText(cmd['command'])
                screen_record_widget.setVisible(False)
                command_row.setVisible(True)
        else:
            command_input.setText(cmd['command'])
            screen_record_widget.setVisible(False)
            command_row.setVisible(True)
        
        command_row_layout.addWidget(command_input)
        
        # 添加扩展按钮
        expand_btn = QPushButton("📝")
        expand_btn.setToolTip("扩大输入框")
        expand_btn.setFixedSize(30, 30)
        
        # 为编辑对话框创建扩展功能
        expand_btn.clicked.connect(lambda: self._expand_input_field(command_input, dialog))
        command_row_layout.addWidget(expand_btn)
        
        layout.addRow("命令内容:", command_row)
        layout.addRow("", screen_record_widget)  # 录屏专用输入框
        
        # 命令类型
        type_combo = QComboBox()
        type_combo.addItems([
            "normal", "upload", "download", "screenshot", "terminal", "device", "file", "app",
            "system", "network", "memory", "cpu", "process", "service", "user", "group",
            "log", "config", "install", "uninstall", "update", "backup", "restore",
            "compress", "extract", "encrypt", "decrypt", "database", "web", "api", "screen_record"
        ])
        type_combo.setCurrentText(cmd.get('type', 'normal'))
        
        # 添加类型切换逻辑
        def toggle_command_fields(cmd_type):
            is_screen_record = cmd_type == "screen_record"
            screen_record_widget.setVisible(is_screen_record)
            command_row.setVisible(not is_screen_record)
        
        type_combo.currentTextChanged.connect(toggle_command_fields)
        
        layout.addRow("命令类型:", type_combo)
        
        # 添加图标预览
        icon_preview = QLabel()
        icon_preview.setStyleSheet("font-size: 24px;")
        
        # 初始显示当前图标
        if self.parent_window:
            icon_symbol = self.parent_window.get_command_icon_symbol(type_combo.currentText())
            icon_preview.setText(icon_symbol)
        
        # 连接类型选择变化信号
        def update_preview(cmd_type):
            if self.parent_window:
                icon_symbol = self.parent_window.get_command_icon_symbol(cmd_type)
                icon_preview.setText(icon_symbol)
        
        type_combo.currentTextChanged.connect(update_preview)
        
        # 添加图标预览
        layout.addRow("图标预览:", icon_preview)
        
        # 按钮
        buttons = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)
        
        # 连接按钮事件
        save_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            # 获取命令类型并自动设置图标
            cmd_type = type_combo.currentText()
            
            # 根据命令类型处理命令内容
            if cmd_type == "screen_record":
                start_cmd = start_command_input.text().strip()
                stop_cmd = stop_command_input.text().strip()
                export_cmd = export_command_input.text().strip()
                
                if not start_cmd or not stop_cmd or not export_cmd:
                    QMessageBox.warning(dialog, "输入错误", "录屏命令的开始、停止和导出命令都不能为空")
                    return
                
                # 将三个命令组合成JSON格式
                command_content = json.dumps({
                    "start": start_cmd,
                    "stop": stop_cmd,
                    "export": export_cmd
                }, ensure_ascii=False)
            else:
                command_content = command_input.text().strip()
                if not command_content:
                    QMessageBox.warning(dialog, "输入错误", "命令内容不能为空")
                    return
            
            # 更新命令
            self.commands[index] = {
                "name": name_input.text().strip(),
                "command": command_content,
                "type": cmd_type,
                "icon": cmd_type  # 图标与命令类型保持一致
            }
            
            # 更新列表
            self.update_command_list()
            
            # 实时更新主窗口
            if self.parent_window:
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                # 延迟更新按钮，避免重复创建
                QTimer.singleShot(100, self.parent_window.update_command_buttons)
    
    def delete_command(self):
        # 删除选中的命令
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "选择错误", "请先选择要删除的命令")
            return
        
        # 确认删除
        item = selected_items[0]
        cmd = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "确认删除", f"确定要删除命令 '{cmd['name']}' 吗？\n\n命令将被移至回收站，可以稍后恢复。",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 删除命令
            index = self.command_list.row(item)
            deleted_cmd = self.commands[index]
            del self.commands[index]
            
            # 将命令移动到回收站
            if self.parent_window:
                self.parent_window.move_to_recycle_bin(deleted_cmd)
            
            # 更新列表
            self.update_command_list()
            
            # 实时更新主窗口
            if self.parent_window:
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                # 延迟更新按钮，避免重复创建
                QTimer.singleShot(100, self.parent_window.update_command_buttons)
                
            QMessageBox.information(self, "删除成功", f"命令 '{deleted_cmd['name']}' 已移至回收站")
    
    def move_command_up(self):
        # 上移选中的命令
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            return
        
        # 获取选中的命令索引
        index = self.command_list.row(selected_items[0])
        if index > 0:
            # 交换位置
            self.commands[index], self.commands[index-1] = self.commands[index-1], self.commands[index]
            
            # 更新列表并选中移动后的项
            self.update_command_list()
            self.command_list.setCurrentRow(index-1)
            
            # 实时更新主窗口
            if self.parent_window:
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                # 延迟更新按钮，避免重复创建
                QTimer.singleShot(100, self.parent_window.update_command_buttons)
    
    def move_command_down(self):
        # 下移选中的命令
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            return
        
        # 获取选中的命令索引
        index = self.command_list.row(selected_items[0])
        if index < len(self.commands) - 1:
            # 交换位置
            self.commands[index], self.commands[index+1] = self.commands[index+1], self.commands[index]
            
            # 更新列表并选中移动后的项
            self.update_command_list()
            self.command_list.setCurrentRow(index+1)
            
            # 实时更新主窗口
            if self.parent_window:
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                # 延迟更新按钮，避免重复创建
                QTimer.singleShot(100, self.parent_window.update_command_buttons)
    
    def load_templates(self):
        """加载模板库数据"""
        try:
            # 获取模板文件路径
            if getattr(sys, 'frozen', False):
                # 如果是打包的应用，使用应用程序目录
                templates_file = os.path.join(os.path.dirname(sys.executable), 'templates.json')
            else:
                # 如果是开发环境，使用脚本目录
                templates_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates.json')
            
            # 检查文件是否存在
            if not os.path.exists(templates_file):
                self.category_list.addItem("未找到模板文件")
                return
            
            # 加载模板数据
            with open(templates_file, 'r', encoding='utf-8') as f:
                self.templates_data = json.load(f)
            
            # 清空分类列表
            self.category_list.clear()
            
            # 添加分类
            for category in self.templates_data:
                self.category_list.addItem(category['category'])
            
            # 默认选中第一个分类并触发事件
            if self.category_list.count() > 0:
                self.category_list.setCurrentRow(0)
                # 手动触发分类选择事件，确保右侧内容正确显示
                self.on_category_selected(0)
        except Exception as e:
            self.category_list.addItem(f"加载模板失败: {str(e)}")
    
    def on_category_selected(self, index):
        """当分类被选中时更新模板列表"""
        # 清空模板列表和详情
        self.templates_list.clear()
        self.template_detail.clear()
        
        # 检查索引是否有效
        if index < 0 or not hasattr(self, 'templates_data') or index >= len(self.templates_data):
            return
        
        # 获取选中分类的模板
        templates = self.templates_data[index]['templates']
        
        # 添加模板到列表
        for template in templates:
            item = QListWidgetItem(template['name'])
            item.setData(Qt.UserRole, template)
            self.templates_list.addItem(item)
        
        # 默认选中第一个模板并触发事件
        if self.templates_list.count() > 0:
            self.templates_list.setCurrentRow(0)
            # 手动触发模板选择事件，确保详情区域正确显示
            self.on_template_selected(0)
    
    def on_template_selected(self, index):
        """当模板被选中时更新详情"""
        # 清空详情
        self.template_detail.clear()
        
        # 检查索引是否有效
        if index < 0 or self.templates_list.count() == 0:
            return
        
        # 获取选中的模板
        item = self.templates_list.item(index)
        template = item.data(Qt.UserRole)
        
        # 显示模板详情
        detail_html = f"""<b>命令:</b> {template['command']}<br>
<b>类型:</b> {template['type']}<br>
<b>描述:</b> {template['description']}"""
        self.template_detail.setHtml(detail_html)
    
    def add_template_to_commands(self):
        """将选中的模板添加到命令列表"""
        # 检查是否有选中的模板
        selected_items = self.templates_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "选择错误", "请先选择一个模板")
            return
        
        # 获取选中的模板
        item = selected_items[0]
        template = item.data(Qt.UserRole)
        
        # 添加到命令列表，图标根据类型自动设置
        cmd_type = template['type']
        self.commands.append({
            "name": template['name'],
            "command": template['command'],
            "type": cmd_type,
            "icon": cmd_type  # 图标与命令类型保持一致
        })
        
        # 更新命令列表
        self.update_command_list()
        
        # 实时更新主窗口
        if self.parent_window:
            self.parent_window.commands = self.commands.copy()
            self.parent_window.save_config()
            self.parent_window.update_command_buttons()
        
        # 提示添加成功
        QMessageBox.information(self, "添加成功", f"已将模板 '{template['name']}' 添加到命令列表")
    
    def save_changes(self):
        """保存更改并关闭对话框"""
        try:
            # 更新主窗口的命令列表
            if self.parent_window and hasattr(self, 'commands'):
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                # 延迟更新按钮，避免在对话框关闭前重复创建
                QTimer.singleShot(100, self.parent_window.update_command_buttons)
            
            # 关闭对话框
            self.accept()
        except Exception as e:
            print(f"保存更改时出错: {e}")
            import traceback
            traceback.print_exc()
            # 即使出错也要关闭对话框
            self.accept()

# 回收站对话框
class RecycleBinDialog(QDialog):
    def __init__(self, deleted_commands, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.deleted_commands = deleted_commands.copy()
        self.parent_window = parent
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("回收站")
        self.setMinimumSize(700, 500)
        
        # 设置对话框图标
        self.set_dialog_icon()
        
        # 应用主题样式
        self.apply_theme()
        
        # 主布局
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("🗑️ 回收站 - 已删除的命令")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 提示信息
        if not self.deleted_commands:
            info_label = QLabel("回收站为空")
            info_label.setStyleSheet("color: #888; font-size: 14px; text-align: center; margin: 20px;")
            info_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(info_label)
        else:
            info_label = QLabel(f"共有 {len(self.deleted_commands)} 个已删除的命令")
            info_label.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 10px;")
            layout.addWidget(info_label)
        
        # 命令列表
        self.command_list = QListWidget()
        self.command_list.setSelectionMode(QListWidget.SingleSelection)
        self.update_command_list()
        layout.addWidget(self.command_list)
        
        # 按钮布局
        buttons_layout = QHBoxLayout()
        
        # 恢复按钮
        restore_btn = QPushButton("🔄 恢复命令")
        restore_btn.clicked.connect(self.restore_command)
        buttons_layout.addWidget(restore_btn)
        
        # 永久删除按钮
        permanent_delete_btn = QPushButton("❌ 永久删除")
        permanent_delete_btn.clicked.connect(self.permanent_delete_command)
        buttons_layout.addWidget(permanent_delete_btn)
        
        # 清空回收站按钮
        clear_all_btn = QPushButton("🗑️ 清空回收站")
        clear_all_btn.clicked.connect(self.clear_recycle_bin)
        buttons_layout.addWidget(clear_all_btn)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
        
        # 快捷键
        QShortcut(QKeySequence("Escape"), self, activated=self.accept)
    
    def set_dialog_icon(self):
        """设置对话框图标"""
        # 使用类级别的标志来防止重复加载
        if not hasattr(self.__class__, '_global_icon_loaded'):
            self.__class__._global_icon_loaded = False
            
        if self.__class__._global_icon_loaded:
            return
            
        if self.parent_window:
            self.setWindowIcon(self.parent_window.windowIcon())
            self.__class__._global_icon_loaded = True
    
    def apply_theme(self):
        """应用主题样式"""
        if hasattr(self, 'parent_window') and self.parent_window:
            theme = self.parent_window.themes[self.parent_window.current_theme]
            self.setStyleSheet(f"""
                QDialog {{
                    background: {theme['window_bg']};
                    color: {theme['terminal_text']};
                }}
                QListWidget {{
                    background: {theme['terminal_bg']};
                    color: {theme['terminal_text']};
                    border: 2px solid {theme['accent_color']};
                    border-radius: 8px;
                    padding: 5px;
                }}
                QListWidget::item {{
                    padding: 8px;
                    border-bottom: 1px solid {theme['accent_color']};
                }}
                QListWidget::item:selected {{
                    background: {theme['accent_color']};
                    color: {theme['window_bg']};
                }}
                QPushButton {{
                    background: {theme['button_bg']};
                    color: {theme['button_text']};
                    border: 2px solid {theme['button_border']};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {theme['button_hover']};
                }}
                QLabel {{
                    color: {theme['terminal_text']};
                }}
            """)
    
    def update_command_list(self):
        """更新命令列表"""
        self.command_list.clear()
        for cmd in self.deleted_commands:
            # 创建列表项
            item_text = f"{cmd['name']} - {cmd.get('deleted_at', '未知时间')}"
            if len(cmd.get('command', '')) > 50:
                command_preview = cmd['command'][:50] + "..."
            else:
                command_preview = cmd.get('command', '')
            
            full_text = f"{item_text}\n命令: {command_preview}"
            
            item = QListWidgetItem(full_text)
            item.setData(Qt.UserRole, cmd)
            
            # 设置图标
            if self.parent_window:
                icon_symbol = self.parent_window.get_command_icon_symbol(cmd.get('icon', 'terminal'))
                item.setText(f"{icon_symbol} {full_text}")
            
            self.command_list.addItem(item)
    
    def restore_command(self):
        """恢复选中的命令"""
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "选择错误", "请先选择要恢复的命令")
            return
        
        item = selected_items[0]
        cmd = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "确认恢复", f"确定要恢复命令 '{cmd['name']}' 吗？",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 恢复命令
            if self.parent_window:
                self.parent_window.restore_from_recycle_bin(cmd)
            
            # 从本地列表移除
            self.deleted_commands.remove(cmd)
            
            # 更新列表
            self.update_command_list()
            
            QMessageBox.information(self, "恢复成功", f"命令 '{cmd['name']}' 已恢复")
    
    def permanent_delete_command(self):
        """永久删除选中的命令"""
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "选择错误", "请先选择要永久删除的命令")
            return
        
        item = selected_items[0]
        cmd = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "确认永久删除", 
                                    f"确定要永久删除命令 '{cmd['name']}' 吗？\n\n⚠️ 此操作不可撤销！",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 从回收站永久删除
            if self.parent_window:
                self.parent_window.deleted_commands.remove(cmd)
                self.parent_window.save_deleted_commands()
            
            # 从本地列表移除
            self.deleted_commands.remove(cmd)
            
            # 更新列表
            self.update_command_list()
            
            QMessageBox.information(self, "删除成功", f"命令 '{cmd['name']}' 已永久删除")
    
    def clear_recycle_bin(self):
        """清空回收站"""
        if not self.deleted_commands:
            QMessageBox.information(self, "提示", "回收站已经是空的")
            return
        
        reply = QMessageBox.question(self, "确认清空", 
                                    f"确定要清空回收站吗？\n\n将永久删除 {len(self.deleted_commands)} 个命令\n\n⚠️ 此操作不可撤销！",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 清空回收站
            if self.parent_window:
                self.parent_window.deleted_commands.clear()
                self.parent_window.save_deleted_commands()
            
            # 清空本地列表
            self.deleted_commands.clear()
            
            # 更新列表
            self.update_command_list()
            
            QMessageBox.information(self, "清空成功", "回收站已清空")
    
    def refresh_log_content(self, log_text):
        """刷新日志内容"""
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                    if log_content.strip():
                        log_text.setPlainText(log_content)
                        # 滚动到底部显示最新日志
                        log_text.moveCursor(QTextCursor.End)
                    else:
                        log_text.setPlainText("日志文件为空，暂无崩溃记录。")
            else:
                log_text.setPlainText("日志文件不存在。")
            logging.info("日志内容已刷新")
        except Exception as e:
            error_msg = f"刷新日志内容失败: {e}"
            logging.error(error_msg, exc_info=True)
            log_text.setPlainText(error_msg)
    
    def clear_log_file(self, log_text):
        """清空日志文件"""
        try:
            reply = QMessageBox.question(self, "确认清空", 
                                       "确定要清空所有日志记录吗？此操作不可撤销。",
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                # 清空日志文件
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write('')
                log_text.setPlainText("日志已清空。")
                logging.info("用户手动清空了日志文件")
                QMessageBox.information(self, "成功", "日志文件已清空。")
        except Exception as e:
            error_msg = f"清空日志文件失败: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)
    
    def open_log_folder(self):
        """打开日志文件夹"""
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                subprocess.run(['explorer', LOG_DIR], check=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(['open', LOG_DIR], check=True)
            else:  # Linux
                subprocess.run(['xdg-open', LOG_DIR], check=True)
            
            logging.info(f"打开日志文件夹: {LOG_DIR}")
        except Exception as e:
            error_msg = f"打开日志文件夹失败: {e}"
            logging.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "错误", error_msg)

# 程序入口
if __name__ == "__main__":
    import os
    import sys
    
    # 首先初始化日志系统
    try:
        setup_crash_logging()
        logging.info("=== 应用程序启动 ===")
        logging.info(f"Python版本: {sys.version}")
        logging.info(f"工作目录: {os.getcwd()}")
        logging.info(f"应用基础目录: {APP_BASE_DIR}")
        
        # 检查上次是否异常退出
        check_previous_crash()
        
        # 创建崩溃标记文件
        create_crash_marker("Application Starting")
        
        # 启动心跳检测
        start_heartbeat()
        
    except Exception as e:
        print(f"日志系统初始化失败: {e}")
        # 即使日志系统失败也继续运行
    
    # 设置环境变量以提高Qt稳定性
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_SCALE_FACTOR'] = '1'
    
    app = None
    window = None
    
    try:
        logging.info("初始化QApplication...")
        
        # 创建QApplication时使用更保守的参数
        app = QApplication(sys.argv)
        app.setAttribute(Qt.AA_DisableWindowContextHelpButton, True)
        app.setQuitOnLastWindowClosed(True)
        
        logging.info("创建CommandManager主窗口...")
        try:
            window = CommandManager()
            logging.info("CommandManager创建成功")
        except Exception as e:
            logging.error(f"CommandManager创建失败: {e}", exc_info=True)
            raise
        
        logging.info("显示主窗口...")
        try:
            window.show()
            logging.info("主窗口显示成功")
        except Exception as e:
            logging.error(f"主窗口显示失败: {e}", exc_info=True)
            raise
        
        logging.info("启动应用程序事件循环...")
        exit_code = app.exec_()
        logging.info(f"应用程序正常退出，退出码: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logging.info("用户中断程序")
        create_crash_marker("User Interrupt (Ctrl+C)")
        print("\n用户中断程序")
        sys.exit(0)
    except Exception as e:
        error_msg = f"程序异常: {e}"
        logging.error(error_msg, exc_info=True)
        create_crash_marker(f"Exception: {e}")
        print(error_msg)
        print(f"详细错误信息已保存到: {LOG_FILE}")
        sys.exit(1)
    finally:
        # 停止心跳检测
        try:
            stop_heartbeat()
        except Exception as e:
            logging.error(f"停止心跳检测失败: {e}")
        
        if app:
            try:
                logging.info("清理QApplication资源...")
                app.quit()
            except Exception as e:
                logging.error(f"清理应用程序资源时出错: {e}", exc_info=True)
        
        # 清理心跳文件
        try:
            if os.path.exists(HEARTBEAT_FILE):
                os.remove(HEARTBEAT_FILE)
        except Exception as e:
            logging.error(f"清理心跳文件失败: {e}")
        
        logging.info("=== 应用程序结束 ===")


# 音乐播放器对话框