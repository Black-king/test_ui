
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import subprocess
import datetime
import tempfile
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QTextEdit, QGridLayout, QFileDialog, QDialog,
                             QLineEdit, QComboBox, QFormLayout, QMessageBox, QProgressBar,
                             QScrollArea, QFrame, QSplitter, QTabWidget, QToolButton, QMenu,
                             QAction, QListWidget, QListWidgetItem, QInputDialog, QGraphicsOpacityEffect,
                             QDesktopWidget, QShortcut, QSizePolicy)
from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QSize, QTimer, QProcess, QPropertyAnimation, 
                          QEasingCurve, QPoint, QRect, QEvent, QObject, QRectF)
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

# 全局动画开关（为稳定优先，默认关闭）
ANIMATIONS_ENABLED = False

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
        self.timer.start(50)  # 50ms更新一次
        
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
            # 不主动输出额外换行，由 UI 端在提示命令后决定是否换行
            
            # 创建进程
            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.handle_output)
            
            # 启动进程 - 使用cmd执行hdc命令
            self.process.start("cmd", ["/c", self.command])
            
            # 等待进程完成
            if self.process.waitForFinished(-1):
                exit_code = self.process.exitCode()
                if exit_code == 0:
                    self.finished_signal.emit(True, "命令执行成功")
                else:
                    self.finished_signal.emit(False, f"命令执行失败，退出代码: {exit_code}")
            else:
                self.finished_signal.emit(False, "命令执行超时或失败")
                
        except Exception as e:
            self.output_signal.emit(f"错误: {str(e)}\n")
            self.finished_signal.emit(False, f"执行出错: {str(e)}")
    
    def handle_output(self):
        try:
            # 尝试使用GBK解码，适用于中文Windows系统
            data = self.process.readAllStandardOutput().data().decode('gbk', errors='replace')
        except UnicodeDecodeError:
            # 如果GBK解码失败，回退到UTF-8
            data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
            
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
        self.commands = []
        self.command_thread = None
        self.current_theme = 'light'  # 默认主题
        self.init_themes()
        # 读取UI偏好（如主题）
        self.load_ui_settings()
        self.init_ui()
        self.load_config()
        
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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1a2e, stop:1 #16213e);
                border: 1px solid #00ffff;
                border-radius: 6px;
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
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2c3e50, stop:1 #34495e);
            padding: 10px 20px;
            border-radius: 8px;
            border: 2px solid #00ffff;
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
        
        # 诗句轮播：每5分钟更换一次
        self.poems = [
            "西风寒露深林下，任是无人也自香",
            "疏影横斜水清浅，暗香浮动月黄昏",
            "人闲桂花落，夜静春山空",
            "竹外桃花三两枝，春江水暖鸭先知",
            "明月松间照，清泉石上流"
        ]
        self._poem_index = 0
        self.update_poem()
        self.poem_timer = QTimer(self)
        self.poem_timer.timeout.connect(self.update_poem)
        self.poem_timer.start(5 * 60 * 1000)  # 5分钟
        
        title_layout.addWidget(self.time_label)
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
        hint = QLabel("右键命令可 快速运行/编辑/删除/复制")
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
        
        terminal_header_layout.addWidget(terminal_label)
        terminal_header_layout.addWidget(self.terminal_status, alignment=Qt.AlignCenter)
        
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
        terminal_header_layout.addWidget(clear_btn, alignment=Qt.AlignRight)
        
        right_layout.addWidget(terminal_header_widget)
        
        # 终端输出区域
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
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
        
        # 连接面板大小变化事件
        left_panel.resizeEvent = self.on_left_panel_resize
        right_panel.resizeEvent = self.on_right_panel_resize
        
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
    
    def on_left_panel_resize(self, event):
        """左侧面板大小变化时更新粒子效果"""
        if hasattr(self, 'left_particle_effect'):
            self.left_particle_effect.setGeometry(0, 0, event.size().width(), event.size().height())
    
    def on_right_panel_resize(self, event):
        """右侧面板大小变化时更新粒子效果"""
        if hasattr(self, 'right_particle_effect'):
            self.right_particle_effect.setGeometry(0, 0, event.size().width(), event.size().height())
    
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
        tooltip = f"<b>{cmd['name']}</b>"
        
        # 添加命令内容
        tooltip += f"<br><br>命令: {cmd['command']}"
        
        # 添加命令类型
        if 'type' in cmd:
            tooltip += f"<br>类型: {cmd['type']}"
        
        # 添加命令描述（如果有）
        if 'description' in cmd:
            tooltip += f"<br><br>{cmd['description']}"
        
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
            background: {theme['button_bg']};
            padding: 10px 20px;
            border-radius: 8px;
            border: 2px solid {theme['accent_color']};
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
        
        # 更新清除按钮样式
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
                break
            
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
                self.left_particle_effect.timer.start(50)
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
                self.right_particle_effect.timer.start(50)
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
        self.terminal.append(f"<span style='color:{theme['terminal_text']}; font-size:14px;'>提示：Ctrl+F 搜索命令，右键命令可进行更多操作。</span>")
    
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
            btn.setText(f"{icon_symbol} {cmd['name']}")
            
            # 添加工具提示
            tooltip = self.create_command_tooltip(cmd)
            btn.setToolTip(tooltip)
            
            # 设置样式
            theme = self.themes[self.current_theme]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {theme['button_bg']};
                    color: {theme['button_text']};
                    border: 3px solid {theme['button_border']};
                    border-radius: 12px;
                    padding: 15px 18px;
                    font-weight: 700;
                    font-size: 18px;
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
            """)
            
            # 设置鼠标悬停为手型
            btn.setCursor(Qt.PointingHandCursor)
            
            # 连接点击事件
            btn.clicked.connect(lambda checked, cmd=cmd: self.execute_command(cmd))

            # 右键菜单：运行/编辑/删除/复制
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            def show_ctx_menu(pos, button=btn, command=cmd):
                menu = QMenu(button)
                # 设置菜单样式以保证可读性
                theme = self.themes[self.current_theme]
                menu.setStyleSheet(self.get_menu_stylesheet(theme))
                run_act = QAction("运行", menu)
                edit_act = QAction("编辑", menu)
                del_act = QAction("删除", menu)
                copy_act = QAction("复制命令", menu)
                run_act.triggered.connect(lambda: self.execute_command(command))
                edit_act.triggered.connect(lambda: self.open_edit_dialog(command))
                del_act.triggered.connect(lambda: self.delete_command_from_ui(command))
                copy_act.triggered.connect(lambda: self.copy_command_text(command))
                for a in (run_act, edit_act, del_act, copy_act):
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
        # 获取命令类型和内容
        cmd_type = cmd.get('type', 'normal')
        cmd_content = cmd['command']
        cmd_name = cmd.get('name', '未命名命令')
        
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
        
        # 执行命令
        QTimer.singleShot(300, lambda: self.run_command(cmd_content))
    
    def run_command(self, command):
        # 如果有正在运行的命令，先停止它
        if self.command_thread and self.command_thread.isRunning():
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

    def copy_command_text(self, cmd):
        clipboard = QApplication.clipboard()
        clipboard.setText(cmd.get('command', ''))
        self.log_message("命令已复制到剪贴板", info=True)

    def open_edit_dialog(self, cmd):
        # 打开对话框并自动定位到指定命令进行编辑
        dialog = CommandManagerDialog(self.commands, self)
        def do_focus():
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
        QTimer.singleShot(0, do_focus)
        dialog.exec_()

    def delete_command_from_ui(self, cmd):
        # 根据名称和内容匹配删除
        before = len(self.commands)
        self.commands = [c for c in self.commands if not (c.get('name') == cmd.get('name') and c.get('command') == cmd.get('command'))]
        if len(self.commands) != before:
            self.save_config()
            self.update_command_buttons()
            self.log_message("命令已删除", info=True)
    
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
        # 显示命令管理对话框
        dialog = CommandManagerDialog(self.commands, self)
        # 设置默认显示模板库选项卡
        tabs = dialog.findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(2)  # 索引2对应模板库选项卡
        dialog.exec_()
        # 关闭返回后刷新（防止子对话框变更未刷）
        self.update_command_buttons()

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
        self.command_input = QLineEdit()
        add_layout.addRow("命令内容:", self.command_input)
        
        # 命令类型
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "normal", "upload", "download", "screenshot", "terminal", "device", "file", "app",
            "system", "network", "memory", "cpu", "process", "service", "user", "group",
            "log", "config", "install", "uninstall", "update", "backup", "restore",
            "compress", "extract", "encrypt", "decrypt", "database", "web", "api"
        ])
        add_layout.addRow("命令类型:", self.type_combo)
        
        # 添加类型变化监听，显示当前选择的图标
        self.icon_preview = QLabel()
        self.icon_preview.setStyleSheet("font-size: 24px;")
        
        # 初始显示默认图标
        self.update_icon_preview(self.type_combo.currentText())
        
        # 连接类型选择变化信号
        self.type_combo.currentTextChanged.connect(self.update_icon_preview)
        
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
                    background-color: {theme['accent_color']};
                    color: #000000;
                    border-color: #66ffff;
                }}
                QListWidget::item:hover {{
                    background-color: #1a4a5a;
                    border-color: {theme['accent_color']};
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
        else:
            # 备用方案：使用原始设置图标
            fallback_path = os.path.join(icon_dir, 'gear.svg')
            if os.path.exists(fallback_path):
                self.setWindowIcon(QIcon(fallback_path))
                print(f"已加载备用图标: {fallback_path}")
            else:
                print(f"无法加载图标，路径不存在: {svg_path} 或 {fallback_path}")
                # 尝试使用终端图标作为最后的备用方案
                terminal_icon = os.path.join(icon_dir, 'cyber_terminal.ico')
                if os.path.exists(terminal_icon):
                    self.setWindowIcon(QIcon(terminal_icon))
                    print(f"已加载终端图标: {terminal_icon}")
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
    
    def add_command_from_form(self):
        # 从表单添加命令
        name = self.name_input.text().strip()
        command = self.command_input.text().strip()
        cmd_type = self.type_combo.currentText()
        
        # 根据命令类型自动设置图标
        icon = cmd_type
        
        if not name or not command:
            QMessageBox.warning(self, "输入错误", "命令名称和内容不能为空")
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
        self.command_input.clear()
        
        # 实时更新主窗口
        if self.parent_window:
            self.parent_window.commands = self.commands.copy()
            self.parent_window.save_config()
            self.parent_window.update_command_buttons()
        
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
        
        # 命令内容
        command_input = QLineEdit(cmd['command'])
        layout.addRow("命令内容:", command_input)
        
        # 命令类型
        type_combo = QComboBox()
        type_combo.addItems([
            "normal", "upload", "download", "screenshot", "terminal", "device", "file", "app",
            "system", "network", "memory", "cpu", "process", "service", "user", "group",
            "log", "config", "install", "uninstall", "update", "backup", "restore",
            "compress", "extract", "encrypt", "decrypt", "database", "web", "api"
        ])
        type_combo.setCurrentText(cmd.get('type', 'normal'))
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
            
            # 更新命令
            self.commands[index] = {
                "name": name_input.text().strip(),
                "command": command_input.text().strip(),
                "type": cmd_type,
                "icon": cmd_type  # 图标与命令类型保持一致
            }
            
            # 更新列表
            self.update_command_list()
            
            # 实时更新主窗口
            if self.parent_window:
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                self.parent_window.update_command_buttons()
    
    def delete_command(self):
        # 删除选中的命令
        selected_items = self.command_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "选择错误", "请先选择要删除的命令")
            return
        
        # 确认删除
        item = selected_items[0]
        cmd = item.data(Qt.UserRole)
        reply = QMessageBox.question(self, "确认删除", f"确定要删除命令 '{cmd['name']}' 吗？",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 删除命令
            index = self.command_list.row(item)
            del self.commands[index]
            
            # 更新列表
            self.update_command_list()
            
            # 实时更新主窗口
            if self.parent_window:
                self.parent_window.commands = self.commands.copy()
                self.parent_window.save_config()
                self.parent_window.update_command_buttons()
    
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
                self.parent_window.update_command_buttons()
    
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
                self.parent_window.update_command_buttons()
    
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
        # 更新主窗口的命令列表
        if self.parent_window:
            self.parent_window.commands = self.commands.copy()
            self.parent_window.save_config()
            self.parent_window.update_command_buttons()
        
        # 关闭对话框
        self.accept()

# 程序入口
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CommandManager()
    sys.exit(app.exec_())