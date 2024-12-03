import os
import shutil
import subprocess
import sys

def clean_build():
    """清理构建文件"""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
    
    # 清理 .spec 文件
    for file in os.listdir('.'):
        if file.endswith('.spec'):
            os.remove(file)

def copy_resources(target_dir, is_server=True):
    """复制资源文件"""
    # 复制配置文件
    shutil.copy('config.ini', target_dir)
    
    # 复制图标
    if os.path.exists(os.path.join(target_dir, 'static', 'favicon.ico')):
        icon_path = os.path.join(target_dir, 'static', 'favicon.ico')
    else:
        # 确保static目录存在
        os.makedirs(os.path.join(target_dir, 'static'), exist_ok=True)
        # 生成图标
        from icon import create_favicon
        icon_path = create_favicon(target_dir, "SS" if is_server else "SC")

    return icon_path

def build_app(app_type):
    """构建应用"""
    is_server = app_type == "主端"
    app_dir = "主端" if is_server else "客户端"
    
    # 清理旧的构建文件
    clean_build()
    
    # 准备资源文件
    icon_path = copy_resources(app_dir, is_server)
    
    # PyInstaller命令
    app_name = "SS-Link主端" if is_server else "SS-Link客户端"
    main_script = os.path.join(app_dir, 'app.py')
    
    cmd = [
        'pyinstaller',
        '--noconfirm',
        '--clean',
        '--name', app_name,
        '--icon', icon_path,
        '--add-data', f'{app_dir}/templates;templates',
        '--add-data', f'{app_dir}/static;static',
        '--add-data', 'config.ini;.',
        '--hidden-import', 'engineio.async_drivers.threading',
        '--hidden-import', 'flask_socketio',
        '--hidden-import', 'dns.resolver',
        main_script
    ]
    
    # 添加额外的依赖
    if is_server:
        cmd.extend([
            '--hidden-import', 'mss',
            '--hidden-import', 'cv2',
            '--hidden-import', 'numpy',
        ])
    
    # 执行打包命令
    subprocess.run(cmd)
    
    print(f"\n{app_type}打包完成！")

def main():
    """主函数"""
    if len(sys.argv) != 2 or sys.argv[1] not in ['主端', '客户端', 'all']:
        print("用法: python build.py [主端|客户端|all]")
        sys.exit(1)
    
    if sys.argv[1] == 'all':
        build_app('主端')
        build_app('客户端')
    else:
        build_app(sys.argv[1])

if __name__ == '__main__':
    main() 