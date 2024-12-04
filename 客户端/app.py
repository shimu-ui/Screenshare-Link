from flask import Flask, render_template, request, jsonify
import socket
from config_manager import Config
import os
import sys
import requests

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
        print("\n=== 开始连接主端 ===")
        main_server_ip = config.get('主端', 'IP地址', fallback='auto')
        base_port = config.get_int('主端', '默认端口', 5000)
        print(f"配置信息: IP={main_server_ip}, 端口={base_port}")
        
        # 检查是否有手动输入的IP和端口
        saved_ip = request.args.get('ip') or request.cookies.get('server_ip')
        saved_port = request.args.get('port') or request.cookies.get('server_port')
        
        # 如果是自动发现请求，则扫描网络
        if request.endpoint == 'discover':
            print("\n[自动发现] 开始...")
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
                print(f"[自动发现] 本机IP: {local_ip}")
                
                # 扫描端口范围(5000-5010)
                for port in range(5000, 5011):
                    try:
                        print(f"[自动发现] 尝试连接到 {local_ip}:{port}")
                        response = requests.get(
                            f"http://{local_ip}:{port}/ping",
                            timeout=0.5
                        )
                        if response.status_code == 200 and response.text == 'pong':
                            print(f"[自动发现] 找到主端: {local_ip}:{port}")
                            return local_ip, port
                    except:
                        continue
                    
            finally:
                s.close()
                
            print("[自动发现] 未找到主端")
            return None, None
            
        # 如果有保存的连接信息，使用保存的信息
        elif saved_ip and saved_port:
            print(f"\n[手动连接] 尝试连接到 {saved_ip}:{saved_port}")
            try:
                response = requests.get(
                    f"http://{saved_ip}:{saved_port}/ping",
                    timeout=0.5
                )
                if response.status_code == 200 and response.text == 'pong':
                    print("[手动连接] 连接成功!")
                    return saved_ip, int(saved_port)
            except Exception as e:
                print(f"[手动连接] 失败: {e}")
        
        # 使用配置文件中的IP
        if main_server_ip != 'auto':
            print(f"\n[配置连接] 使用配置的主端IP: {main_server_ip}")
            return main_server_ip, base_port
            
        # 如果都失败了，返回本机IP
        print("\n[默认] 使用本机IP")
        return get_local_ip(), base_port
            
    except Exception as e:
        print(f"\n[错误] 获取主端IP失败: {e}")
        return '127.0.0.1', base_port

def get_local_ip():
    """获取本机局域网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

@app.route('/')
def index():
    try:
        # 获取本机局域网IP
        local_ip = get_local_ip()
        print(f"本机IP: {local_ip}")
        
        # 获取其他配置
        device_name = config.get('客户端', '设备名称', 'auto')
        if device_name == 'auto':
            try:
                device_name = socket.gethostname()
            except:
                device_name = 'Unknown'
        
        return render_template('index.html',
                             local_ip=local_ip,  # 传递本机IP
                             main_server_ip=local_ip,  # 默认使用本机IP
                             main_server_port=config.get_int('主端', '默认端口', 5000),
                             auto_connect=config.get_bool('客户端', '自动连接', True),
                             fullscreen=config.get_bool('客户端', '全屏模式', False),
                             timeout=config.get_int('网络', '超时时间', 10000),
                             reconnection_attempts=config.get_int('网络', '重连次数', 5),
                             device_name=device_name)
    except Exception as e:
        print(f"渲染页面失败: {e}")
        return f"错误: {str(e)}", 500

def find_free_port(start_port):
    """查找可用端口"""
    port = start_port
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # 使用 0.0.0.0 允许所有网络接口访问
                s.bind(('0.0.0.0', port))
                s.close()
                return port
        except OSError:
            port += 1
    raise RuntimeError('没有可用的端口')

@app.route('/discover')
def discover():
    """自动发现主端"""
    try:
        ip, port = get_main_server_ip()
        if ip and port:
            return jsonify({
                'success': True,
                'ip': ip,
                'port': port
            })
        return jsonify({
            'success': False,
            'message': '未找到主端'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/connect', methods=['POST'])
def connect():
    """手动连接主端"""
    try:
        ip = request.form.get('ip')
        port = request.form.get('port')
        
        print(f"\n[手动连接] 收到连接请求: {ip}:{port}")
        
        if not ip or not port:
            print("[手动连接] 错误: IP或端口为空")
            return jsonify({
                'success': False,
                'message': '请输入IP和端口'
            })
            
        # 测试连接
        try:
            print(f"[手动连接] 测试连接到 {ip}:{port}")
            response = requests.get(
                f"http://{ip}:{port}/ping",
                timeout=0.5
            )
            if response.status_code == 200 and response.text == 'pong':
                print("[手动连接] 连接成功!")
                resp = jsonify({
                    'success': True,
                    'message': '连接成功'
                })
                resp.set_cookie('server_ip', ip)
                resp.set_cookie('server_port', port)
                return resp
        except Exception as e:
            print(f"[手动连接] 连接失败: {e}")
            
        return jsonify({
            'success': False,
            'message': '连接失败'
        })
        
    except Exception as e:
        print(f"[手动连接] 发生错误: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

if __name__ == '__main__':
    try:
        # 尝试默认端口
        port = config.get_int('客户端', '默认端口', 5001)
        if port < 1024:  # 避免使用特权端口
            port = 5001
            
        # 如果默认端口不可用,查找其他端口
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                s.close()
        except OSError:
            port = find_free_port(5001)
            
        # 获取本机局域网IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
            
        print(f"客户端运行在: http://{ip}:{port}")
        
        app.run(
            host='0.0.0.0',  # 允许所有网络接口访问
            port=port,
            debug=True
        )
    except Exception as e:
        print(f"启动失败: {e}")
        # 如果是权限问题,提示用户
        if isinstance(e, OSError) and e.errno == 13:
            print("提示: 请尝试使用管理员权限运行,或者使用更高的端口号(如8000以上)")