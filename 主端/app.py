from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import os
import socket
import logging
import base64
from io import BytesIO
from mss import mss
import time
from PIL import Image
import numpy as np
from PIL import ImageGrab
import win32gui
import win32con
import win32ui
from threading import Thread, Event, Timer
import atexit
import cv2
from numba import jit
from concurrent.futures import ThreadPoolExecutor
import psutil
import threading
import sys
from config_manager import Config
import json

# 设置日志级别
logging.basicConfig(
    level=logging.WARNING,  # 改为WARNING级别
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 设置werkzeug和engineio的日志级别
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)
logging.getLogger('socketio').setLevel(logging.WARNING)

# 修改资源路径处理
def get_resource_path(relative_path):
    """获取资源文件的绝对路径"""
    try:
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            base_path = os.path.join(os.path.dirname(sys.executable), '主端')
        else:
            # 如果是开发环境
            base_path = os.path.dirname(__file__)
        return os.path.join(base_path, relative_path)
    except Exception as e:
        print(f"获取资源路径失败: {e}")
        return os.path.join(os.path.dirname(__file__), relative_path)

# 修改客户端的资源路径处理
def get_client_resource_path(relative_path):
    """获取客户端资源文件的绝对路径"""
    try:
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            base_path = os.path.join(os.path.dirname(sys.executable), '客户端')
        else:
            # 如果是开发环境
            base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '客户端')
        return os.path.join(base_path, relative_path)
    except Exception as e:
        print(f"获取客户端资源路径失败: {e}")
        return os.path.join(os.path.dirname(__file__), relative_path)

# 修改模板和静态文件路径
app = Flask(__name__,
           template_folder=get_resource_path('templates'),
           static_folder=get_resource_path('static'),
           static_url_path='/static')
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "allow_headers": "*",
        "expose_headers": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "supports_credentials": True
    }
})

# 在文件开头添加
def get_config_path():
    """获取配置文件路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        return os.path.join(os.path.dirname(sys.executable), 'config.ini')
    else:
        # 如果是开发环境
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')

# 修改配置加载
config = Config(get_config_path())

# 修改socketio配置
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=config.get_int('网络', '超时时间', 60000) // 1000,
    ping_interval=config.get_int('网络', '心跳间隔', 25),
    always_connect=True,
    reconnection=True,
    reconnection_attempts=config.get_int('网络', '重连次数', 5),
    max_http_buffer_size=1024 * 1024 * 10
)

# 全局变量
is_sharing = False
sharing_thread = None
stop_event = Event()

# 使用字典来存储客户端信息
connected_clients = {}

cleanup_timer = None  # 添加全局变量

# 创建线程池
executor = ThreadPoolExecutor(max_workers=2)

# 添加性能监控相关的变量
performance_data = {
    'fps': 0,
    'frame_count': 0,
    'last_time': time.time()
}

# 添加新的全局变量
pending_clients = {}  # 等待审核的客户端
blacklist = set()    # 黑名单IP
device_counter = 0  # 设备编号计数器
ip_to_device_id = {}  # IP地址到设备ID的映射

def load_blacklist():
    """加载黑名单"""
    try:
        blacklist_file = os.path.join(os.path.dirname(__file__), 'blacklist.txt')
        if os.path.exists(blacklist_file):
            with open(blacklist_file, 'r') as f:
                blacklist.update(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"加载黑名单失败: {e}")

def save_blacklist():
    """保存黑名单"""
    try:
        blacklist_file = os.path.join(os.path.dirname(__file__), 'blacklist.txt')
        with open(blacklist_file, 'w') as f:
            for ip in blacklist:
                f.write(f"{ip}\n")
    except Exception as e:
        print(f"保存黑名单失败: {e}")

def update_performance_metrics():
    """更新性能指标"""
    while True:
        try:
            process = psutil.Process()
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info().rss

            # 计算FPS
            current_time = time.time()
            elapsed = current_time - performance_data['last_time']
            if elapsed >= 1.0:
                current_fps = performance_data['frame_count'] / elapsed
                performance_data['frame_count'] = 0
                performance_data['last_time'] = current_time

                # 发送性能数据
                socketio.emit('performance_update', {
                    'fps': current_fps,
                    'cpu': cpu_percent,
                    'memory': memory_info,
                    'status': 'running' if is_sharing else 'stopped',
                    'clients': len(connected_clients)
                }, broadcast=True)

            time.sleep(1.0)
        except Exception as e:
            print(f"性能监控错误: {e}")
            time.sleep(1.0)

# 使用Numba加速图像处理
@jit(nopython=True)
def optimize_image(image_array):
    """使用Numba加速的图像处理"""
    return np.clip(image_array * 1.1, 0, 255).astype(np.uint8)

def process_image(image, target_width, target_height):
    """优化的图像处理"""
    try:
        # 转换为OpenCV格式
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # 使用OpenCV进行缩放
        resized = cv2.resize(cv_image, (target_width, target_height), 
                           interpolation=cv2.INTER_LINEAR)
        
        # 使用WebP格式替代JPEG，因为它提供更好的压缩率和更快的编码速度
        encode_param = [
            int(cv2.IMWRITE_WEBP_QUALITY), 75  # WebP质量
        ]
        result, enc_img = cv2.imencode('.webp', resized, encode_param)
        
        return enc_img.tobytes()
    except Exception as e:
        print(f"图像处理错误: {e}")
        # 回退到JPEG编码
        encode_param = [
            int(cv2.IMWRITE_JPEG_QUALITY), 75,
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
            int(cv2.IMWRITE_JPEG_PROGRESSIVE), 0  # 禁用渐进式JPEG以提高速度
        ]
        result, enc_img = cv2.imencode('.jpg', resized, encode_param)
        return enc_img.tobytes()

def screen_share_thread(window_id=None):
    """优化的投屏线程"""
    global is_sharing
    
    try:
        if window_id:
            hwnd = int(window_id)
            print(f"开始窗口投屏，窗口ID: {hwnd}")
            if not win32gui.IsWindow(hwnd):
                print("无效的口ID")
                is_sharing = False
                return
        else:
            hwnd = None
            print("开始全屏投屏")
            
        with mss() as sct:
            main_monitor = sct.monitors[0]
            
            # 预先计算目标尺寸
            source_width = main_monitor["width"]
            target_width = 1920
            scale_factor = target_width / source_width
            target_height = int(main_monitor["height"] * scale_factor)
            
            print(f"投屏分辨率: {target_width}x{target_height}")
            
            while is_sharing and not stop_event.is_set():
                try:
                    if not connected_clients:
                        time.sleep(0.1)
                        continue
                        
                    start_time = time.time()
                    
                    if hwnd:
                        screenshot = capture_window(hwnd)
                        if screenshot is None:
                            continue
                    else:
                        screen = sct.grab(main_monitor)
                        screenshot = Image.frombytes(
                            'RGB',
                            (screen.width, screen.height),
                            screen.rgb,
                        )

                    # 处理图像
                    compressed_data = process_image(screenshot, target_width, target_height)
                    img_str = base64.b64encode(compressed_data).decode()
                    
                    # 发送画面帧
                    if not stop_event.is_set():
                        try:
                            socketio.emit('screen_frame', {
                                'image': img_str,
                                'width': target_width,
                                'height': target_height,
                                'timestamp': time.time()
                            }, room='screen_viewers', namespace='/')
                            
                            performance_data['frame_count'] += 1
                        except Exception as e:
                            print(f"发送画面帧失败: {e}")
                    
                    elapsed = time.time() - start_time
                    if elapsed < 0.016:  # 目标60FPS
                        time.sleep(0.016 - elapsed)
                    
                except Exception as e:
                    print(f"截图错误: {e}")
                    time.sleep(0.016)
                    
    except Exception as e:
        print(f"投屏错误: {e}")
        print(f"错误详情:", exc_info=True)
    finally:
        is_sharing = False
        try:
            socketio.emit('screen_stopped', {'data': '投屏已停止'}, broadcast=True)
        except Exception as e:
            print(f"发送停止消息失败: {e}")

@app.route('/')
def index():
    return render_template('index.html')

def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接一个公网IP（不会真正建立连接）
        s.connect(('8.8.8.8', 80))
        # 获取本机IP
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return '127.0.0.1'

@app.route('/get_ip')
def get_ip():
    """获取主端的局域网IP地址"""
    ip = get_local_ip()
    print(f"本机IP地: {ip}")
    return jsonify({'ip': ip})

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    client_ip = request.remote_addr
    client_type = request.args.get('type', '')
    
    print(f'收到新连接请求: {client_id} from {client_ip}, type: {client_type}')
    
    if client_type == 'client':
        try:
            auth_settings = config.get_auth_settings()
            print(f'客户端连接: {client_ip}, 需要审核: {not auth_settings["auto_approve"]}')
            
            # 获取或生成设备ID
            device_id = get_or_create_device_id(client_ip)
            print(f'分配设备ID: {device_id}')
            
            # 先加入投屏房间
            join_room('screen_viewers')
            print(f'客户端加入投屏房间: {client_id}')
            
            # 自动审核或等待手动审核
            if auth_settings['auto_approve']:
                print(f'自动审核通过: {client_ip}')
                approve_client(client_id, client_ip, device_id)
            else:
                print(f'等待手动审核: {client_ip}')
                # 添加到待审核列表
                pending_clients[client_id] = {
                    'ip': client_ip,
                    'time': time.time(),
                    'device_id': device_id
                }
                
                # 发送等待审核状态
                emit('auth_status', {
                    'status': 'pending',
                    'device_id': device_id
                }, room=client_id)
                
                # 通知所有管理页面
                socketio.emit('new_pending_client', {
                    'id': client_id,
                    'ip': client_ip,
                    'device_id': device_id
                }, to='admin')
                
                print(f'客户端已加入待审核列表: {client_ip} (设备ID: {device_id})')
                
        except Exception as e:
            print(f'客户端连接处理失败: {e}')
            return False
    else:
        # 调试页面连接
        join_room('screen_viewers')  # 调试页面也加入投屏房间
        join_room('admin')  # 加入管理员房间
        print(f'调试页面连接: {client_id} from {client_ip}')

def approve_client(client_id, client_ip, device_id):
    """批准客户端连接"""
    try:
        client_info = pending_clients.get(client_id)
        if not client_info:
            return
            
        # 客户端已经在投屏房间中，不需要重复加入
        print(f'客户端已在投屏房间: {client_id} (设备ID: {device_id})')
        
        # 添加新连接
        connected_clients[client_id] = {
            'ip': client_ip,
            'connected_time': time.time(),
            'device_id': device_id
        }
        
        # 从待审核列表移除
        pending_clients.pop(client_id, None)
        
        print(f'客户端连接成功: {client_id} (设备ID: {device_id}) from {client_ip}')
        
        # 发送批准消息和设备ID
        emit('auth_status', {
            'status': 'approved',
            'device_id': device_id
        }, room=client_id)
        
        # 广播更新连接数量和设备列表
        socketio.emit('client_count', {
            'count': len(connected_clients),
            'clients': [{
                'id': cid,
                'ip': info['ip'],
                'device_id': info['device_id']
            } for cid, info in connected_clients.items()]
        }, broadcast=True)
        
    except Exception as e:
        print(f'批准客户端失败: {e}')

@socketio.on('reject_client')
def reject_client(data):
    """拒绝客户端连接"""
    client_id = data.get('client_id')
    if client_id in pending_clients:
        client_ip = pending_clients[client_id]['ip']
        
        # 可选择加入黑名单
        if data.get('add_to_blacklist', False):
            blacklist.add(client_ip)
            save_blacklist()
        
        # 从待审核列表移除
        pending_clients.pop(client_id)
        
        # 发送拒绝消息
        emit('auth_status', {'status': 'rejected'}, room=client_id)
        print(f'拒绝客户端连接: {client_id} from {client_ip}')

@socketio.on('approve_client')
def handle_approve_client(data):
    """处理批准客户端请求"""
    client_id = data.get('client_id')
    if client_id in pending_clients:
        approve_client(client_id, pending_clients[client_id]['ip'], pending_clients[client_id]['device_id'])

# 在程序启动时加载黑名单
load_blacklist()

# 添加窗口列表获取函数
def get_window_list():
    """获取所有可见窗口的列表"""
    windows = []
    
    def enum_windows_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title != 'Program Manager':  # 排除桌面
                windows.append({
                    'hwnd': hwnd,
                    'title': title
                })
    
    win32gui.EnumWindows(enum_windows_callback, None)
    return windows

# 修改窗口捕获函数
def capture_window(hwnd):
    """捕获指定窗口的截图"""
    try:
        # 获取窗口位置和大小
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            print(f"无效的窗口大小: {width}x{height}")
            return None

        # 将窗口置于前台
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.1)  # 等待窗口激活
        except:
            print("无法将窗口置于前台")

        # 用mss捕获指定区域
        with mss() as sct:
            monitor = {
                "top": top,
                "left": left,
                "width": width,
                "height": height,
                "mon": -1,  # 使用整个虚拟屏幕
            }
            
            try:
                screenshot = sct.grab(monitor)
                # 转换为PIL Image
                img = Image.frombytes(
                    'RGB',
                    (screenshot.width, screenshot.height),  # 使用width和height属性
                    screenshot.rgb,  # 使用rgb而不是bgra
                )
                return img
            except Exception as e:
                print(f"截图失败: {e}")
                return None

    except Exception as e:
        print(f"窗口捕获错误: {e}")
        return None

# 添加获取窗口列表的路由
@app.route('/get_windows')
def get_windows():
    windows = get_window_list()
    return jsonify([{
        'id': str(w['hwnd']),
        'title': w['title']
    } for w in windows])

@socketio.on('start_screen_share')
def start_screen_share(data=None):
    global is_sharing, sharing_thread
    if is_sharing:
        return
        
    is_sharing = True
    stop_event.clear()
    
    # 发送状态更新
    socketio.emit('sharing_status', {'status': '正在投屏'})
    
    # 启动投屏线程
    sharing_thread = Thread(target=screen_share_thread, 
                          args=(data.get('window_id'),),
                          daemon=True)
    sharing_thread.start()

@socketio.on('stop_screen_share')
def stop_screen_share():
    global is_sharing, sharing_thread
    if not is_sharing:
        return
        
    is_sharing = False
    stop_event.set()
    
    if sharing_thread and sharing_thread.is_alive():
        sharing_thread.join(timeout=1.0)
    
    print("停止投屏...")
    socketio.emit('sharing_status', {'status': '已停止'})
    emit('screen_stopped', {'data': '投屏已停止'}, broadcast=True)

def find_free_port(start_port):
    """查找可用端口"""
    max_attempts = 100
    port = start_port
    attempts = 0
    
    while attempts < max_attempts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
                port += 1
                attempts += 1
        except Exception as e:
            print(f"查找端口时出错: {e}")
            port += 1
            attempts += 1
    
    raise RuntimeError(f"无法找到可用端口，已尝试 {max_attempts} 次")

@socketio.on_error()
def error_handler(e):
    print(f'SocketIO error: {str(e)}')

@socketio.on_error_default
def default_error_handler(e):
    print(f'SocketIO default error: {str(e)}')

# 添加调试页面路由
@app.route('/debug')
def debug():
    return render_template('debug.html')

# 添加定清理函数
def cleanup_stale_connections():
    current_time = time.time()
    for sid, info in list(connected_clients.items()):
        if current_time - info['connected_time'] > 60:  # 60秒超时
            connected_clients.pop(sid, None)
            print(f'Cleaned up stale connection: {sid}')
    
    # 更新连接数量
    emit('client_count', {
        'count': len(connected_clients)
    }, broadcast=True)

# 每分钟执行一次清理
@socketio.on('cleanup')
def handle_cleanup():
    cleanup_stale_connections()

def save_device_ids():
    """保存设备ID映射"""
    try:
        device_ids_file = os.path.join(os.path.dirname(__file__), 'device_ids.json')
        with open(device_ids_file, 'w') as f:
            json.dump({
                'counter': device_counter,
                'mappings': ip_to_device_id
            }, f, indent=2)
    except Exception as e:
        print(f"保存设备ID映射失败: {e}")

def load_device_ids():
    """加载设备ID映射"""
    global device_counter, ip_to_device_id
    try:
        device_ids_file = os.path.join(os.path.dirname(__file__), 'device_ids.json')
        if os.path.exists(device_ids_file):
            with open(device_ids_file, 'r') as f:
                data = json.load(f)
                device_counter = data.get('counter', 0)
                ip_to_device_id = data.get('mappings', {})
    except Exception as e:
        print(f"加载设备ID映射失败: {e}")

# 在程序启动时加载设备ID映射
load_device_ids()

# 在程序出时保存设备ID映射
def cleanup():
    """程序退出时的清理工作"""
    global is_sharing, cleanup_timer
    if is_sharing:
        stop_screen_share()
    
    # 停止时器
    if cleanup_timer and cleanup_timer.is_alive():
        cleanup_timer.cancel()
    
    # 保存设备ID映射
    save_device_ids()

# 注册退出处理
atexit.register(cleanup)

# 添加favicon路由
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico', 
        mimetype='image/vnd.microsoft.icon'
    )

# 添加黑名单管理相关的路由
@socketio.on('add_to_blacklist')
def add_to_blacklist(data):
    """添加IP到黑名单"""
    ip = data.get('ip')
    if ip:
        blacklist.add(ip)
        save_blacklist()
        
        # 断开该IP的所有连接
        for sid, info in list(connected_clients.items()):
            if info['ip'] == ip:
                socketio.disconnect(sid)
        
        emit('blacklist_updated', {'action': 'add', 'ip': ip}, broadcast=True)
        print(f'已添加IP到黑名单: {ip}')

@socketio.on('remove_from_blacklist')
def remove_from_blacklist(data):
    """从黑名单移除IP"""
    ip = data.get('ip')
    if ip in blacklist:
        blacklist.remove(ip)
        save_blacklist()
        emit('blacklist_updated', {'action': 'remove', 'ip': ip}, broadcast=True)
        print(f'已从黑名单移除IP: {ip}')

@app.route('/get_blacklist')
def get_blacklist():
    """获取黑名单列表"""
    return jsonify(list(blacklist))

# 修改断开连接处理
@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    if client_id in connected_clients:
        try:
            # 从房间中移除
            leave_room('screen_viewers')
            print(f'客户端离开房间: {client_id}')
            
            # 移除连接信息
            client_info = connected_clients.pop(client_id)
            print(f'客户端断开: {client_id} from {client_info["ip"]}')
            print(f'当前客户端数量: {len(connected_clients)}')
            
            # 广播更新连接数量
            emit('client_count', {
                'count': len(connected_clients)
            }, broadcast=True)
        except Exception as e:
            print(f'离开房间失败: {e}')
    elif client_id in pending_clients:
        # 清理待审核列表
        pending_clients.pop(client_id)
        print(f'待审核客户端断开: {client_id}')

def get_or_create_device_id(ip):
    """获取或创建设备ID"""
    global device_counter
    if ip not in ip_to_device_id:
        device_counter += 1
        # 获取主机名
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            # 如果能获取到主机名,使用主机名
            device_name = hostname.split('.')[0]  # 只取第一部分
        except:
            # 获取失败则使用编号
            device_name = f"设备{device_counter:03d}"
            
        ip_to_device_id[ip] = device_name
    return ip_to_device_id[ip]

@socketio.on('get_clients')
def handle_get_clients():
    """获取当前连接的客户端列表"""
    try:
        emit('client_count', {
            'count': len(connected_clients),
            'clients': [{
                'id': cid,
                'ip': info['ip'],
                'device_id': info['device_id']
            } for cid, info in connected_clients.items()]
        })
    except Exception as e:
        print(f'获取客户端列表失败: {e}')

@socketio.on('get_pending_clients')
def handle_get_pending_clients():
    """获取待审核的客户端列表"""
    try:
        for pid, pinfo in pending_clients.items():
            emit('new_pending_client', {
                'id': pid,
                'ip': pinfo['ip'],
                'device_id': pinfo['device_id']
            })
    except Exception as e:
        print(f'获取待审核列表失败: {e}')

if __name__ == '__main__':
    port = find_free_port(config.get_int('主端', '默认端口', 5000))
    ip = get_local_ip()
    print(f"主端运行在: http://{ip}:{port}")
    
    # 启动定期清理任务
    cleanup_timer = Timer(60.0, cleanup_stale_connections)
    cleanup_timer.daemon = True
    cleanup_timer.start()
    
    # 启动性能监控线程
    performance_thread = threading.Thread(
        target=update_performance_metrics, 
        daemon=True
    )
    performance_thread.start()
    
    try:
        socketio.run(app, 
                    host='0.0.0.0',
                    port=port,
                    debug=True,
                    use_reloader=False)
    finally:
        cleanup()