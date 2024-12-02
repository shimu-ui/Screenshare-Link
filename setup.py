import sys
import os
from cx_Freeze import setup, Executable

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"当前目录: {current_dir}")

# 检查目录是否存在
print(f"主端目录存在: {os.path.exists(os.path.join(current_dir, '主端'))}")
print(f"客户端目录存在: {os.path.exists(os.path.join(current_dir, '客户端'))}")

# 检查文件是否存在
print(f"主端app.py存在: {os.path.exists(os.path.join(current_dir, '主端', 'app.py'))}")
print(f"客户端app.py存在: {os.path.exists(os.path.join(current_dir, '客户端', 'app.py'))}")
print(f"主端favicon.ico存在: {os.path.exists(os.path.join(current_dir, '主端', 'static', 'favicon.ico'))}")
print(f"config.ini存在: {os.path.exists(os.path.join(current_dir, 'config.ini'))}")

# 构建选项
build_exe_options = {
    "packages": [
        "flask",
        "flask_socketio",
        "flask_cors",
        "engineio.async_drivers.threading",
        "mss",
        "PIL",
        "cv2",
        "numpy",
        "win32gui",
        "win32con",
        "win32ui",
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
    ],
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
    "build_exe": os.path.join("build", "exe.win-amd64-3.10", "主端")
}

# 客户端构建选项
client_build_options = {
    "packages": [
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
    ],
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
    "build_exe": os.path.join("build", "exe.win-amd64-3.10", "客户端")
}

print("开始打包...")

try:
    # 打包主端
    print("正在打包主端...")
    if len(sys.argv) == 1 or sys.argv[1] == "build_server":
        setup(
            name="SS-Link-主端",
            version="1.0.0",
            description="局域网投屏工具-主端",
            options={"build_exe": build_exe_options},
            executables=[
                Executable(
                    script=os.path.join(current_dir, "主端", "app.py"),
                    base=None,  # 改为 None 以显示控制台窗口，方便调试
                    target_name="主端.exe",
                    icon=os.path.join(current_dir, "主端", "static", "favicon.ico")
                )
            ]
        )
        print("主端打包完成")

    # 打包客户端
    print("正在打包客户端...")
    if len(sys.argv) == 1 or sys.argv[1] == "build_client":
        setup(
            name="SS-Link-客户端",
            version="1.0.0",
            description="局域网投屏工具-客户端",
            options={"build_exe": client_build_options},
            executables=[
                Executable(
                    script=os.path.join(current_dir, "客户端", "app.py"),
                    base=None,  # 改为 None 以显示控制台窗口，方便调试
                    target_name="客户端.exe",
                    icon=os.path.join(current_dir, "客户端", "static", "favicon.ico")
                )
            ]
        )
        print("客户端打包完成")

except Exception as e:
    print(f"打包过程出错: {str(e)}")

print("打包过程结束")