# 创建主端可执行文件
main_server = Executable(
    script=os.path.join(current_dir, "SS-Link", "主端", "app.py"),
    base="Win32GUI" if sys.platform == "win32" else None,
    target_name="SS-Link主端.exe",
    icon=os.path.join(current_dir, "SS-Link", "主端", "static", "favicon.ico"),
    shortcut_name="SS-Link主端",
    shortcut_dir="DesktopFolder",
    copyright="Copyright © 2024 shimu-ui"
)

# 创建客户端可执行文件
client = Executable(
    script=os.path.join(current_dir, "SS-Link", "客户端", "app.py"),
    base="Win32GUI" if sys.platform == "win32" else None,
    target_name="SS-Link客户端.exe",
    icon=os.path.join(current_dir, "SS-Link", "主端", "static", "favicon.ico"),
    shortcut_name="SS-Link客户端",
    shortcut_dir="DesktopFolder",
    copyright="Copyright © 2024 shimu-ui"
) 