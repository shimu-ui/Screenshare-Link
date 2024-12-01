import os
import sys
from cx_Freeze import setup, Executable

current_dir = os.path.dirname(os.path.abspath(__file__))

# 创建主端可执行文件
main_server = Executable(
    script=os.path.join(current_dir, "主端", "app.py"),
    base="Win32GUI" if sys.platform == "win32" else None,
    target_name="SS-Link主端.exe",
    icon=os.path.join(current_dir, "主端", "static", "favicon.ico"),
    shortcut_name="SS-Link主端",
    shortcut_dir="DesktopFolder",
    copyright="Copyright © 2024 shimu-ui"
)

# 创建客户端可执行文件
client = Executable(
    script=os.path.join(current_dir, "客户端", "app.py"),
    base="Win32GUI" if sys.platform == "win32" else None,
    target_name="SS-Link客户端.exe",
    icon=os.path.join(current_dir, "客户端", "static", "favicon.ico"),
    shortcut_name="SS-Link客户端",
    shortcut_dir="DesktopFolder",
    copyright="Copyright © 2024 shimu-ui"
)

# 构建选项
build_options = {
    "packages": [
        "flask",
        "flask_socketio",
        "flask_cors",
        "engineio",
        "socketio",
        "mss",
        "PIL",
        "cv2",
        "numpy",
        "win32api",
        "win32con"
    ],
    "include_files": [
        (os.path.join(current_dir, "主端", "static"), "static"),
        (os.path.join(current_dir, "主端", "templates"), "templates"),
        (os.path.join(current_dir, "主端", "config.ini"), "config.ini"),
        (os.path.join(current_dir, "config.ini"), "config.ini"),
    ],
    "excludes": ["tkinter", "test", "distutils"],
    "optimize": 2
}

setup(
    name="SS-Link",
    version="1.0.0",
    description="一个强大的多客户端屏幕共享解决方案",
    author="shimu-ui",
    options={"build_exe": build_options},
    executables=[main_server, client]
)