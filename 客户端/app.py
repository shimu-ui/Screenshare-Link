from flask import Flask, render_template, request
import socket
from config_manager import Config
import os
import sys

# 修改资源路径处理
def get_resource_path(relative_path):
    """获取资源文件的绝对路径"""
    try:
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            base_path = os.path.join(os.path.dirname(sys.executable), '客户端')
        else:
            # 如果是开发环境
            base_path = os.path.dirname(__file__)
        return os.path.join(base_path, relative_path)
    except Exception as e:
        print(f"获取资源路径失败: {e}")
        return os.path.join(os.path.dirname(__file__), relative_path)

# 修改Flask应用初始化
app = Flask(__name__,
           template_folder=get_resource_path('templates'),
           static_folder=get_resource_path('static'),
           static_url_path='/static')

def get_config_path():
    """获取配置文件路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        return os.path.join(os.path.dirname(sys.executable), 'config.ini')
    else:
        # 如果是开发环境
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')

# 加载配置
config = Config(get_config_path())

def get_main_server_ip():
    """获取主端IP地址"""
    try:
        # 从配置文件获取
        main_server_ip = config.get('主端', 'IP地址', fallback='auto')
        
        # 如果配置为auto,则自动获取
        if main_server_ip == 'auto':
            # 创建UDP socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # 连接任意可用地址
                s.connect(('8.8.8.8', 80))
                # 获取本机IP
                local_ip = s.getsockname()[0]
                # 获取网段
                network = '.'.join(local_ip.split('.')[:-1])
                # 遍历该网段寻找主端
                for i in range(1, 255):
                    try:
                        test_ip = f"{network}.{i}"
                        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        test_socket.settimeout(0.1)
                        if test_socket.connect_ex((test_ip, 5000)) == 0:
                            return test_ip
                        test_socket.close()
                    except:
                        continue
            finally:
                s.close()
                
            # 如果找不到主端,使用默认IP
            return '127.0.0.1'
            
        return main_server_ip
            
    except Exception as e:
        print(f"获取主端IP失败: {e}")
        return '127.0.0.1'  # 出错时返回本地回环地址

@app.route('/')
def index():
    try:
        main_server_ip = get_main_server_ip()
        print(f"加载主端IP: {main_server_ip}")
        
        # 获取设备名称
        device_name = config.get('客户端', '设备名称', 'auto')
        if device_name == 'auto':
            try:
                device_name = socket.gethostname()
            except:
                device_name = 'auto'
        
        return render_template('index.html',
                             main_server_ip=main_server_ip,
                             auto_connect=config.get_bool('客户端', '自动连接', True),
                             fullscreen=config.get_bool('客户端', '全屏模式', False),
                             timeout=config.get_int('网络', '超时时间', 10000),
                             reconnection_attempts=config.get_int('网络', '重连次数', 5),
                             device_name=device_name)  # 传递设备名称
    except Exception as e:
        print(f"渲染页面失败: {e}")
        return f"错误: {str(e)}", 500

if __name__ == '__main__':
    port = config.get_int('客户端', '默认端口', 5001)
    print(f"客户端运行在: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)