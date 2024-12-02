import sys
import os
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
base_packages = [
    "flask",
    "flask_socketio",
    "flask_cors",
    "engineio.async_drivers.threading",
    "PIL",
    "cv2",
    "numpy",
    "werkzeug",
    "jinja2",
    "http",
    "http.server",
    "socketio",
    "engineio",
    "email",
    "email.utils",
    "html",
    "html.parser",
    "json",
    "logging",
    "urllib",
    "urllib.parse",
    "urllib.request"
]

# 主端额外包
server_packages = base_packages + [
    "mss",
    "win32gui",
    "win32con",
    "win32ui"
]

# 获取打包类型
build_type = os.environ.get("BUILD_TYPE", "").lower()

if not build_type:
    print("请指定要打包的程序：")
    print("set BUILD_TYPE=server && python setup.py build - 打包主端")
    print("set BUILD_TYPE=client && python setup.py build - 打包客户端")
    print("set BUILD_TYPE=all && python setup.py build - 打包主端和客户端")
    sys.exit(1)

print(f"开始打包... (类型: {build_type})")

executables = []
build_options = {}

# 主端打包配置
if build_type in ["server", "all"]:
    print("正在打包主端...")
    executables.append(
        Executable(
            script=os.path.join(current_dir, "主端", "app.py"),
            base=None,  # 显示控制台窗口
            target_name="主端.exe",
            icon=os.path.join(current_dir, "主端", "static", "favicon.ico")
        )
    )
    build_options["build_exe"] = {
        "packages": server_packages,
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
            (os.path.join(current_dir, "主端", "templates"), "templates"),
            (os.path.join(current_dir, "主端", "static"), "static"),
            (os.path.join(current_dir, "config.ini"), "config.ini")
        ],
        "include_msvcr": True,
        "optimize": 2,
        "build_exe": "dist/主端"
    }

# 客户端打包配置
if build_type in ["client", "all"]:
    print("正在打包客户端...")
    executables.append(
        Executable(
            script=os.path.join(current_dir, "客户端", "app.py"),
            base=None,  # 显示控制台窗口
            target_name="客户端.exe",
            icon=os.path.join(current_dir, "客户端", "static", "favicon.ico")
        )
    )
    build_options["build_exe_2"] = {
        "packages": base_packages,
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
            (os.path.join(current_dir, "客户端", "templates"), "templates"),
            (os.path.join(current_dir, "客户端", "static"), "static"),
            (os.path.join(current_dir, "config.ini"), "config.ini")
        ],
        "include_msvcr": True,
        "optimize": 2,
        "build_exe": "dist/客户端"
    }

if not executables:
    print(f"错误：无效的打包类型 '{build_type}'")
    print("有效的类型：server, client, all")
    sys.exit(1)

# 执行打包
setup(
    name="SS-Link",
    version="1.0.0",
    description="局域网投屏工具",
    options=build_options,
    executables=executables
)

print("打包过程结束")