import os
import sys
import platform
from cx_Freeze import setup, Executable

# 增加递归限制
sys.setrecursionlimit(5000)

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 基础配置
base = None
if platform.system() == "Windows":
    base = "Win32GUI"

# 创建主端可执行文件
main_server = Executable(
    script=os.path.join(current_dir, "主端", "app.py"),
    base=base,
    target_name="SS-Link主端.exe",
    icon=os.path.join(current_dir, "主端", "static", "favicon.ico")
)

# 创建客户端可执行文件
client = Executable(
    script=os.path.join(current_dir, "客户端", "app.py"),
    base=base,
    target_name="SS-Link客户端.exe",
    icon=os.path.join(current_dir, "客户端", "static", "favicon.ico")
)

# 需要包含的包
required_packages = [
    "flask",
    "flask_socketio",
    "flask_cors",
    "engineio.async_drivers.threading",  # 只包含threading异步驱动
    "socketio",
    "mss",
    "PIL",
    "cv2",
    "numpy"
]

# 需要排除的包
excluded_packages = [
    "tkinter",
    "unittest",
    "email",
    "html",
    "http",
    "xml",
    "pydoc",
    "doctest",
    "argparse",
    "datetime",
    "zipfile",
    "py",
    "pytest",
    "_pytest",
    "pkg_resources",
    "distutils",
    "setuptools",
    "asyncio",
    "concurrent",
    "multiprocessing",
    "lib2to3",
    "pygame",
    "tcl",
    "tk",
    "wx"
]

# 构建选项
build_options = {
    "packages": required_packages,
    "excludes": excluded_packages,
    "include_files": [
        (os.path.join(current_dir, "主端", "static"), "static"),
        (os.path.join(current_dir, "主端", "templates"), "templates"),
        (os.path.join(current_dir, "主端", "config.ini"), "config.ini"),
        (os.path.join(current_dir, "config.ini"), "config.ini")
    ],
    "optimize": 2,  # 使用最高级别的优化
    "include_msvcr": True,  # 包含MSVC运行时
    "zip_include_packages": "*",  # 将所有包压缩到zip文件中
    "zip_exclude_packages": "",  # 不排除任何包的压缩
}

setup(
    name="SS-Link",
    version="1.0.0",
    description="一个强大的多客户端屏幕共享解决方案",
    options={"build_exe": build_options},
    executables=[main_server, client]
)