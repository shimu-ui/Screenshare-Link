import sys
import os

# 增加递归限制
sys.setrecursionlimit(5000)

from cx_Freeze import setup, Executable

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"当前目录: {current_dir}")

# 检查目录和文件是否存在
print(f"主端目录存在: {os.path.exists(os.path.join(current_dir, '主端'))}")
print(f"客户端目录存在: {os.path.exists(os.path.join(current_dir, '客户端'))}")
print(f"主端app.py存在: {os.path.exists(os.path.join(current_dir, '主端', 'app.py'))}")
print(f"客户端app.py存在: {os.path.exists(os.path.join(current_dir, '客户端', 'app.py'))}")
print(f"主端favicon.ico存在: {os.path.exists(os.path.join(current_dir, '主端', 'static', 'favicon.ico'))}")
print(f"config.ini存在: {os.path.exists(os.path.join(current_dir, 'config.ini'))}")

# 基础包列表
packages = [
    "flask",
    "flask_socketio",
    "flask_cors",
    "engineio.async_drivers.threading",
    "PIL",
    "cv2",
    "numpy",
    "werkzeug",
    "jinja2",
    "http.server",
    "socketio",
    "engineio",
    "email.utils",
    "html.parser",
    "json",
    "logging",
    "urllib.parse",
    "urllib.request",
    "pickle",
    "mss",
    "win32gui",
    "win32con",
    "win32ui"
]

print("开始打包...")

# 创建可执行文件配置
executables = [
    # 主端
    Executable(
        script=os.path.join(current_dir, "主端", "app.py"),
        base=None,  # 显示控制台窗口
        target_name="主端.exe",
        icon=os.path.join(current_dir, "主端", "static", "favicon.ico")
    ),
    # 客户端
    Executable(
        script=os.path.join(current_dir, "客户端", "app.py"),
        base=None,  # 显示控制台窗口
        target_name="客户端.exe",
        icon=os.path.join(current_dir, "客户端", "static", "favicon.ico")
    )
]

# 构建选项
build_options = {
    "build_exe": {
        "packages": packages,
        "excludes": [
            "tkinter",
            "unittest",
            "xml",
            "asyncio",
            "test",
            "distutils",
            "lib2to3",
            "pygame",
            "tcl",
            "tk"
        ],
        "include_files": [
            (os.path.join(current_dir, "主端", "templates"), "主端/templates"),
            (os.path.join(current_dir, "主端", "static"), "主端/static"),
            (os.path.join(current_dir, "客户端", "templates"), "客户端/templates"),
            (os.path.join(current_dir, "客户端", "static"), "客户端/static"),
            (os.path.join(current_dir, "config.ini"), "config.ini")
        ],
        "include_msvcr": True,
        "optimize": 2,
        "build_exe": "dist/SS-Link",
        "zip_include_packages": "*",
        "zip_exclude_packages": ""
    }
}

# 执行打包
setup(
    name="SS-Link",
    version="1.0.0",
    description="局域网投屏工具",
    options=build_options,
    executables=executables
)

print("打包过程结束")