from flask import Flask, render_template, jsonify, request, send_from_directory, send_file
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
from werkzeug.utils import secure_filename
import zipfile
from functools import wraps
import jwt
import datetime
import shutil
import gc
from functools import lru_cache
import hashlib
import logging.handlers
import pyaudio
import wave
import audioop
import win32api

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

# 修改socketio配置 - 增强连接兼容性
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
    max_http_buffer_size=1024 * 1024 * 10,
    allow_upgrades=True,  # 允许协议升级
    transports=['polling', 'websocket'],  # 优先使用polling，然后升级到websocket
    cookie=None,  # 禁用cookie以避免跨域问题
    path='/socket.io/'  # 明确指定路径
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

# JWT密钥配置
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key')  
JWT_ALGORITHM = 'HS256'
JWT_EXPIRES = 24 * 60 * 60  # 24小时

def generate_token(device_id):
    """生成JWT token"""
    payload = {
        'device_id': device_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXPIRES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token):
    """验证JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload['device_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get('token')
        if not token:
            return {'error': '未授权'}, 401
        
        device_id = verify_token(token)
        if not device_id:
            return {'error': '无效token'}, 401
            
        return f(*args, **kwargs)
    return decorated

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

# 添加图像处理优化
@jit(nopython=True)
def optimize_image_quality(image_array):
    """使用Numba加速的图质量优化"""
    # 亮度和对比度优化
    alpha = 1.1  # 对比度
    beta = 10    # 亮度
    return np.clip(alpha * image_array + beta, 0, 255).astype(np.uint8)

# 添加画质设置类
class QualitySettings:
    def __init__(self):
        self.quality = 80  # 图像质(0-100)
        self.resolution_scale = 1.0  # 分辨率缩放(0.1-1.0)
        self.fps_limit = 60  # 帧率限制
        self.compression = 'webp'  # 压缩格式(webp/jpeg)
        self.optimize_mode = 'balanced'  # 优化模式(quality/balanced/performance)
        
    def update(self, settings):
        """更新画质设置"""
        if 'quality' in settings:
            self.quality = max(1, min(100, settings['quality']))
            
        if 'resolution_scale' in settings:
            self.resolution_scale = max(0.1, min(1.0, settings['resolution_scale']))
            
        if 'fps_limit' in settings:
            self.fps_limit = max(1, min(144, settings['fps_limit']))
            
        if 'compression' in settings:
            if settings['compression'] in ['webp', 'jpeg']:
                self.compression = settings['compression']
                
        if 'optimize_mode' in settings:
            if settings['optimize_mode'] in ['quality', 'balanced', 'performance']:
                self.optimize_mode = settings['optimize_mode']
                
    def get_encode_params(self):
        """获取编码参数"""
        if self.compression == 'webp':
            return [
                int(cv2.IMWRITE_WEBP_QUALITY), self.quality
            ]
        else:
            return [
                int(cv2.IMWRITE_JPEG_QUALITY), self.quality,
                int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
            ]
            
    def get_target_resolution(self, width, height):
        """获取目标分辨率"""
        return (
            int(width * self.resolution_scale),
            int(height * self.resolution_scale)
        )
        
    def get_frame_interval(self):
        """获取帧间隔"""
        return 1.0 / self.fps_limit

# 创建画质设置实例
quality_settings = QualitySettings()

# 启动性能监控线程
def start_performance_monitor():
    """启动性能监控线程"""
    def performance_monitor_thread():
        while True:
            try:
                # 获取系统资源使用情况
                cpu_percent = psutil.cpu_percent()
                memory_info = psutil.virtual_memory().used
                
                # 计算FPS - 如果没有投屏，显示系统默认帧率
                current_time = time.time()
                elapsed = current_time - performance_data['last_time']
                if elapsed >= 1.0:
                    if is_sharing:
                        # 投屏时使用实际帧率
                        current_fps = performance_data['frame_count'] / elapsed
                        performance_data['frame_count'] = 0
                    else:
                        # 没有投屏时显示系统默认帧率（60FPS）
                        current_fps = 60.0
                    
                    performance_data['last_time'] = current_time
                    
                    # 计算网络流量（基于已发送的数据）
                    network_traffic = 0
                    if hasattr(performance_data, 'total_bytes_sent'):
                        network_traffic = performance_data.get('total_bytes_sent', 0) / 1024  # KB/s
                    
                    # 发送性能数据
                    print(f"发送性能数据: FPS={current_fps:.1f}, CPU={cpu_percent:.1f}%, Memory={memory_info/1024/1024:.1f}MB, Network={network_traffic:.1f}KB/s, Clients={len(connected_clients)}")
                    socketio.emit('performance_update', {
                        'fps': current_fps,
                        'cpu': cpu_percent,
                        'memory': memory_info,
                        'network': network_traffic,
                        'status': 'running' if is_sharing else 'stopped',
                        'clients': len(connected_clients)
                    }, broadcast=True)
                    
                    # 重置网络流量计数器
                    if hasattr(performance_data, 'total_bytes_sent'):
                        performance_data['total_bytes_sent'] = 0

                time.sleep(1.0)
            except Exception as e:
                print(f"性能监控错误: {e}")
                time.sleep(1.0)
    
    # 启动性能监控线程
    performance_thread = Thread(target=performance_monitor_thread, daemon=True)
    performance_thread.start()
    print("性能监控线程已启动")
    print(f"线程ID: {performance_thread.ident}, 是否活跃: {performance_thread.is_alive()}")

# 添加画质设置接口
@socketio.on('update_quality')
def update_quality(data):
    """更新画质设置"""
    try:
        quality_settings.update(data)
        return {'status': 'success'}
    except Exception as e:
        logging.error(f"更新画质设置失败: {e}")
        return {'status': 'error', 'message': str(e)}

# 修改图像处理函数使用新的画质设置
def process_image(image, target_width, target_height):
    """优化的图像处理函数"""
    try:
        # 转换为OpenCV格式
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # 获取目标分辨率
        new_width, new_height = quality_settings.get_target_resolution(
            target_width, target_height
        )
        
        # 根据优化模式选择算法
        if quality_settings.optimize_mode == 'quality':
            interpolation = cv2.INTER_CUBIC
        elif quality_settings.optimize_mode == 'performance':
            interpolation = cv2.INTER_NEAREST
        else:
            interpolation = cv2.INTER_LINEAR
            
        # 缩放图像
        resized = cv2.resize(cv_image, (new_width, new_height), 
                           interpolation=interpolation)
        
        # 图像优化
        if quality_settings.optimize_mode != 'performance':
            resized = optimize_image_quality(resized)
            
        # 编码
        result, enc_img = cv2.imencode(
            '.webp' if quality_settings.compression == 'webp' else '.jpg',
            resized,
            quality_settings.get_encode_params()
        )
        
        return enc_img.tobytes()
        
    except Exception as e:
        logging.error(f"图像处理错误: {e}")
        return None

# 添加资源限制
class ResourceMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.max_memory = 1024 * 1024 * 1024  # 1GB
        self.max_cpu = 80  # 80%
        
    def check_resources(self):
        """检查资源使用情况"""
        try:
            # 检查内存使用
            memory_used = self.process.memory_info().rss
            if memory_used > self.max_memory:
                print(f"内存使用超限: {memory_used / 1024 / 1024:.1f}MB")
                self.cleanup_memory()
                
            # 检查CPU使用
            cpu_percent = self.process.cpu_percent()
            if cpu_percent > self.max_cpu:
                print(f"CPU使用超限: {cpu_percent}%")
                self.reduce_load()
                
        except Exception as e:
            print(f"资源监控错误: {e}")
            
    def cleanup_memory(self):
        """清理内存"""
        # 清理图像缓存
        gc.collect()
        # 清理临时文件
        self.cleanup_temp_files()
        
    def reduce_load(self):
        """降低负载"""
        global target_fps
        if target_fps > 15:
            target_fps -= 5
            print(f"降低目标帧率至: {target_fps}")
            
    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                try:
                    file_path = os.path.join(temp_dir, file)
                    if os.path.getctime(file_path) < time.time() - 3600:
                        os.remove(file_path)
                except Exception as e:
                    print(f"清理临时文件失败: {e}")

# 创建资源监控实例
resource_monitor = ResourceMonitor()

# 添加全局错误处理装饰器
def handle_errors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            # 记录错误
            logging.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            # 通知客户端
            socketio.emit('error', {
                'message': '操作失败',
                'details': str(e)
            })
            return None
    return decorated

# 修改screen_share_thread函数
@handle_errors
def screen_share_thread(window_id=None):
    """优化的投屏线程"""
    global is_sharing, target_fps
    
    try:
        # 初始化目标帧率
        target_fps = 60
        frame_interval = 1.0 / target_fps
        
        while is_sharing and not stop_event.is_set():
            try:
                start_time = time.time()
                
                # 检查资源使用
                resource_monitor.check_resources()
                
                # 处理图像和发送
                process_and_send_frame(window_id)
                
                # 动态调整帧率
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                elif elapsed > frame_interval * 1.5:
                    target_fps = max(15, target_fps - 1)
                    frame_interval = 1.0 / target_fps
                    
            except Exception as e:
                logging.error(f"Frame processing error: {e}", exc_info=True)
                # 尝试恢复
                time.sleep(1)
                continue
                
    except Exception as e:
        logging.error(f"Screen share thread error: {e}", exc_info=True)
        raise
    finally:
        is_sharing = False
        try:
            socketio.emit('screen_stopped', {'data': '投屏已停止'})
        except:
            pass

def process_and_send_frame(window_id=None):
    """处理屏幕截图并发送给客户端"""
    try:
        # 获取屏幕截图
        if window_id:
            # 窗口模式
            img = capture_window(int(window_id))
        else:
            # 全屏模式
            img = capture_screen()
        
        if img is None:
            print("截图失败，无法获取图像")
            return
            
        # 调整图像大小和质量
        img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
        
        # 转换为JPEG格式并压缩
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        img_data = buffer.getvalue()
        
        # 转换为base64
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        # 发送给所有已连接的客户端
        print(f"发送投屏数据，图像大小: {len(img_data)} 字节，base64长度: {len(img_base64)}")
        socketio.emit('screen_data', {
            'image': img_base64,
            'timestamp': time.time(),
            'fps': target_fps
        }, broadcast=True)
        
        # 更新性能数据
        performance_data['frame_count'] += 1
        
        # 统计网络流量
        if not hasattr(performance_data, 'total_bytes_sent'):
            performance_data['total_bytes_sent'] = 0
        performance_data['total_bytes_sent'] += len(img_data)
        
        current_time = time.time()
        if current_time - performance_data['last_time'] >= 1.0:
            performance_data['fps'] = performance_data['frame_count']
            performance_data['frame_count'] = 0
            performance_data['last_time'] = current_time
            
    except Exception as e:
        logging.error(f"Frame processing error: {e}")
        print(f"Frame processing error: {e}")
        import traceback
        traceback.print_exc()

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
    """处理客户端连接"""
    client_id = request.sid
    client_ip = request.remote_addr
    
    # 生成设备ID
    device_id = get_or_create_device_id(client_ip)
    
    # 检查是否已经存在相同IP的已连接客户端，如果有则断开旧连接
    existing_connected = None
    for cid, cinfo in connected_clients.items():
        if cinfo['ip'] == client_ip and cinfo['device_id'] == device_id:
            existing_connected = cid
            break
    
    if existing_connected:
        print(f"[Socket.IO] 发现相同IP的已连接客户端，断开旧连接: {existing_connected}")
        # 从已连接列表中移除
        connected_clients.pop(existing_connected, None)
        # 断开旧连接
        socketio.disconnect(existing_connected)
        # 立即广播更新客户端列表
        socketio.emit('client_count', {
            'count': len(connected_clients),
            'clients': [{
                'id': cid,
                'ip': info['ip'],
                'device_id': info['device_id']
            } for cid, info in connected_clients.items()]
        }, broadcast=True)
    
    # 检查是否已经存在相同IP的待审核客户端
    existing_pending = None
    for pid, pinfo in pending_clients.items():
        if pinfo['ip'] == client_ip and pinfo['device_id'] == device_id:
            existing_pending = pid
            break
    
    # 如果存在相同IP的待审核客户端，移除旧的
    if existing_pending:
        print(f"[Socket.IO] 移除重复的待审核客户端: {existing_pending}")
        pending_clients.pop(existing_pending, None)
        # 通知前端移除旧的待审核条目
        emit('remove_pending_client', {
            'id': existing_pending
        }, broadcast=True)
    
    # 检查当前客户端是否已经连接
    if client_id in connected_clients:
        print(f"[Socket.IO] 客户端已连接，跳过待审核: {client_id}")
        return True
    
    # 添加到待审核列表
    pending_clients[client_id] = {
        'ip': client_ip,
        'device_id': device_id,
        'time': time.time()
    }
    
    # 广播新的连接请求
    emit('new_pending_client', {
        'id': client_id,
        'ip': client_ip,
        'device_id': device_id
    }, broadcast=True)
    
    # 通知客户端等待审核
    emit('auth_status', {
        'status': 'pending',
        'device_id': device_id,
        'message': '等待主端审核'
    }, room=client_id)
    
    print(f"[Socket.IO] 新客户端等待审核: {client_id} ({client_ip})")
    return True

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
        
        # 待审核列表移除
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
def handle_reject_client(data):
    """处理拒绝客户端请求"""
    client_id = data.get('client_id')
    if client_id in pending_clients:
        client_info = pending_clients[client_id]
        
        # 从待审核列表移除
        pending_clients.pop(client_id)
        
        # 通知客户端被拒绝
        emit('auth_status', {
            'status': 'rejected',
            'reason': '连接被拒绝'
        }, room=client_id)
        
        print(f"[Socket.IO] 拒绝客户端连接: {client_id}")

@socketio.on('approve_client')
def handle_approve_client(data):
    """处理批准客户端请求"""
    client_id = data.get('client_id')
    if client_id in pending_clients:
        client_info = pending_clients[client_id]
        
        # 添加到已连接列表
        connected_clients[client_id] = {
            'ip': client_info['ip'],
            'device_id': client_info['device_id'],
            'connected_time': time.time()
        }
        
        # 从待审核列表移除
        pending_clients.pop(client_id)
        
        # 通知客户端审核通过
        emit('auth_status', {
            'status': 'approved',
            'device_id': client_info['device_id']
        }, room=client_id)
        
        # 广播更新客户端列表
        emit('client_count', {
            'count': len(connected_clients),
            'clients': [{
                'id': cid,
                'ip': info['ip'],
                'device_id': info['device_id']
            } for cid, info in connected_clients.items()]
        }, broadcast=True)
        
        print(f"[Socket.IO] 客户端审核通过: {client_id}")

@socketio.on('reconnect_approved')
def handle_reconnect_approved(data):
    """处理已认证客户端的重新连接"""
    client_id = request.sid
    device_id = data.get('device_id')
    client_ip = request.remote_addr
    
    print(f"[Socket.IO] 已认证客户端重新连接: {client_id} (设备ID: {device_id})")
    
    # 直接从待审核列表移除（如果存在）
    if client_id in pending_clients:
        pending_clients.pop(client_id)
        # 通知前端移除待审核条目
        emit('remove_pending_client', {
            'id': client_id
        }, broadcast=True)
    
    # 添加到已连接列表
    connected_clients[client_id] = {
        'ip': client_ip,
        'device_id': device_id,
        'connected_time': time.time()
    }
    
    # 通知客户端连接成功
    emit('auth_status', {
        'status': 'approved',
        'device_id': device_id
    }, room=client_id)
    
    # 广播更新客户端列表
    socketio.emit('client_count', {
        'count': len(connected_clients),
        'clients': [{
            'id': cid,
            'ip': info['ip'],
            'device_id': info['device_id']
        } for cid, info in connected_clients.items()]
    }, broadcast=True)
    
    print(f"[Socket.IO] 已认证客户端重新连接成功: {client_id} (设备ID: {device_id})")

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

# 添加重试装饰器
def retry(max_attempts=3, delay=1):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        logging.error(f"Max retry attempts reached for {f.__name__}: {e}")
                        raise
                    logging.warning(f"Retry attempt {attempts} for {f.__name__}: {e}")
                    time.sleep(delay)
            return None
        return decorated
    return decorator

# 使用重试机制
@retry(max_attempts=3)
def capture_screen():
    """捕获整个屏幕"""
    try:
        with mss() as sct:
            # 捕获主显示器
            monitor = sct.monitors[1]  # 主显示器
            print(f"捕获屏幕，显示器信息: {monitor}")
            screenshot = sct.grab(monitor)
            print(f"截图成功，尺寸: {screenshot.width}x{screenshot.height}")
            
            # 转换为PIL Image
            img = Image.frombytes(
                'RGB',
                (screenshot.width, screenshot.height),
                screenshot.rgb
            )
            print(f"图像转换成功，模式: {img.mode}, 尺寸: {img.size}")
            return img
    except Exception as e:
        logging.error(f"Screen capture error: {e}")
        print(f"Screen capture error: {e}")
        import traceback
        traceback.print_exc()
        return None

@retry(max_attempts=3)
def capture_window(hwnd):
    """带重试的窗口捕获"""
    try:
        # 获取口位置和大小
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            print(f"无效的窗口小: {width}x{height}")
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
        logging.error(f"Window capture error: {e}")
        raise

# 添加获取窗口列表的路由
@app.route('/get_windows')
def get_windows():
    windows = get_window_list()
    return jsonify([{
        'id': str(w['hwnd']),
        'title': w['title']
    } for w in windows])

# 添加音频捕获和传输支持
class AudioCapture:
    def __init__(self):
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 2
        self.rate = 44100
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        
    def start_capture(self):
        """开始音频捕获"""
        if self.stream:
            return
            
        try:
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            self.is_recording = True
            
            # 启动音频传输线程
            Thread(target=self.audio_stream_thread, daemon=True).start()
            
        except Exception as e:
            logging.error(f"音频捕获启动失败: {e}")
            
    def stop_capture(self):
        """停止音频捕获"""
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
    def audio_stream_thread(self):
        """音频流传输线程"""
        while self.is_recording:
            try:
                # 读取音频数据
                data = self.stream.read(self.chunk)
                
                # 压缩音频数据
                compressed = audioop.lin2adpcm(data, 2, None)[0]
                
                # 发送给客户端
                socketio.emit('audio_data', {
                    'data': base64.b64encode(compressed).decode(),
                    'timestamp': time.time()
                }, room='screen_viewers')
                
            except Exception as e:
                logging.error(f"音频传输错误: {e}")
                time.sleep(0.1)

# 创建音频捕获实例
audio_capture = AudioCapture()

# 修改开始投屏函数
@socketio.on('start_screen_share')
def start_screen_share(data=None):
    global is_sharing, sharing_thread
    if is_sharing:
        return
        
    is_sharing = True
    stop_event.clear()
    
    # 启动音频捕获
    audio_capture.start_capture()
    
    # 发送状态更新
    socketio.emit('sharing_status', {'status': '正在投屏'})
    
    # 启动投屏线程
    sharing_thread = Thread(target=screen_share_thread, 
                          args=(data.get('window_id'),),
                          daemon=True)
    sharing_thread.start()

# 修改停止投屏函数
@socketio.on('stop_screen_share')
def stop_screen_share():
    global is_sharing, sharing_thread
    if not is_sharing:
        return
        
    is_sharing = False
    stop_event.set()
    
    # 停止音频捕获
    audio_capture.stop_capture()
    
    if sharing_thread and sharing_thread.is_alive():
        sharing_thread.join(timeout=1.0)

def find_free_port(start_port):
    """查找可用端口"""
    port = start_port
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            port += 1
    raise RuntimeError('没有可用的端口')

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
    
    # 清理过期的已连接客户端
    for sid, info in list(connected_clients.items()):
        if current_time - info['connected_time'] > 60:  # 60秒超时
            connected_clients.pop(sid, None)
            print(f'Cleaned up stale connection: {sid}')
    
    # 清理过期的待审核客户端
    for sid, info in list(pending_clients.items()):
        if current_time - info['time'] > 30:  # 30秒超时
            pending_clients.pop(sid, None)
            print(f'Cleaned up stale pending client: {sid}')
            # 通知前端移除过期的待审核条目
            socketio.emit('remove_pending_client', {
                'id': sid
            }, broadcast=True)
    
    # 更新连接数量
    socketio.emit('client_count', {
        'count': len(connected_clients),
        'clients': [{
            'id': cid,
            'ip': info['ip'],
            'device_id': info['device_id']
        } for cid, info in connected_clients.items()]
    }, broadcast=True)

# 每分钟执行一次清理
@socketio.on('cleanup')
def handle_cleanup():
    cleanup_stale_connections()

# 在文件开头添加
import os

# 获取当前文件所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def save_device_ids():
    """保存设备ID映射"""
    try:
        device_ids_file = os.path.join(CURRENT_DIR, 'device_ids.json')
        with open(device_ids_file, 'w') as f:
            json.dump({
                'counter': device_counter,
                'mappings': ip_to_device_id
            }, f)
    except Exception as e:
        print(f"保存设备ID映射失败: {e}")

def load_device_ids():
    """加载设备ID映射"""
    global device_counter
    try:
        device_ids_file = os.path.join(CURRENT_DIR, 'device_ids.json')
        if os.path.exists(device_ids_file):
            with open(device_ids_file, 'r') as f:
                data = json.load(f)
                device_counter = data.get('counter', 0)
                ip_to_device_id.update(data.get('mappings', {}))
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
        
        # 断开该IP所有连接
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
    """处理客户端断开"""
    client_id = request.sid
    print(f"\n[Socket.IO] 客户端断开: {client_id}")
    
    # 从已连接列表中移除
    if client_id in connected_clients:
        client_info = connected_clients.pop(client_id)
        print(f"[Socket.IO] 已连接客户端断开: {client_id} ({client_info['ip']})")
        
        # 广播更新连接数量
        socketio.emit('client_count', {
            'count': len(connected_clients),
            'clients': [{
                'id': cid,
                'ip': info['ip'],
                'device_id': info['device_id']
            } for cid, info in connected_clients.items()]
        }, broadcast=True)
    
    # 从待审核列表中移除
    if client_id in pending_clients:
        client_info = pending_clients.pop(client_id)
        print(f"[Socket.IO] 待审核客户端断开: {client_id} ({client_info['ip']})")
        
        # 通知前端移除待审核条目
        emit('remove_pending_client', {
            'id': client_id
        }, broadcast=True)

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

UPLOAD_FOLDER = 'uploads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 文件上传配置
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'pdf', 'txt', 'zip', 'rar', '7z', 'tar', 'gz'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
# 移除认证要求，因为这是主端自己的文件上传
# @require_auth
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400
        
    file = request.files['file']
    if not file:
        return jsonify({'error': '无效文件'}), 400
        
    # 检查文件名
    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({'error': '无效文件名'}), 400
        
    # 检查文件扩展名
    if not allowed_file(filename):
        return jsonify({'error': '不允许的文件类型'}), 400
        
    # 检查文件大小
    if request.content_length > MAX_CONTENT_LENGTH:
        return jsonify({'error': '文件太大'}), 413
        
    try:
        # 保存文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 文件上传成功后，自动广播到所有连接的客户端
        if connected_clients:
            socketio.emit('file_broadcast', {
                'filename': filename,
                'url': f'/download/{filename}',
                'size': os.path.getsize(file_path)
            }, broadcast=True)
            print(f"文件 {filename} 已广播到 {len(connected_clients)} 个客户端")
        
        return jsonify({
            'message': '文件上传成功',
            'filename': filename,
            'size': os.path.getsize(file_path)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 这个函数已经在上面定义了，移除重复定义
# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(
        os.path.join(app.config['UPLOAD_FOLDER'], filename),
        as_attachment=True,
        download_name=filename
    )

@socketio.on('broadcast_file')
def broadcast_file(data):
    """广播文件到有客户端"""
    room = data.get('room')
    filename = data.get('filename')
    if room and filename:
        socketio.emit('file_broadcast', {
            'filename': filename,
            'url': f'/download/{filename}'
        }, room=room)

# 添加缓存支持
class FrameCache:
    def __init__(self, maxsize=128):
        self.cache = {}
        self.maxsize = maxsize
        
    def get_frame(self, frame_hash):
        """获取缓存的帧"""
        return self.cache.get(frame_hash)
        
    def cache_frame(self, frame_data, frame_hash):
        """缓存帧"""
        if len(self.cache) >= self.maxsize:
            # 移除最旧的缓存
            self.cache.pop(next(iter(self.cache)))
        self.cache[frame_hash] = frame_data
        
    def clear(self):
        """清空缓存"""
        self.cache.clear()

# 创建帧缓存实例
frame_cache = FrameCache()

@lru_cache(maxsize=32)
def get_window_info(hwnd):
    """缓存窗口信息"""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        title = win32gui.GetWindowText(hwnd)
        return {
            'rect': rect,
            'title': title,
            'time': time.time()
        }
    except Exception:
        return None

class ErrorRecovery:
    def __init__(self):
        self.error_count = 0
        self.last_error_time = 0
        self.recovery_threshold = 5
        self.recovery_interval = 60  # 60秒
        
    def record_error(self, error):
        """记录错误"""
        current_time = time.time()
        # 重置计数器(如果距离上次错误超过恢复间隔)
        if current_time - self.last_error_time > self.recovery_interval:
            self.error_count = 0
            
        self.error_count += 1
        self.last_error_time = current_time
        
        # 检查是否需要采取恢复措施
        if self.error_count >= self.recovery_threshold:
            self.trigger_recovery()
            
    def trigger_recovery(self):
        """触发恢复措施"""
        try:
            # 停止当前投屏
            global is_sharing
            if is_sharing:
                stop_screen_share()
                
            # 清理资源
            resource_monitor.cleanup_memory()
            frame_cache.clear()
            
            # 重置错误计数
            self.error_count = 0
            
            # 通知客户端
            socketio.emit('recovery', {
                'message': '系统已自动恢复'
            })
            
        except Exception as e:
            logging.error(f"Recovery failed: {e}")

# 创建错误恢复实例
error_recovery = ErrorRecovery()

# 配置日志记录
def setup_logging():
    """配置日志系统"""
    log_dir = os.path.join(CURRENT_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'ss-link.log')
    
    # 创建文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=1024*1024,  # 1MB
        backupCount=5
    )
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 设置Flask和SocketIO的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)

# 添加录制支持
class ScreenRecorder:
    def __init__(self):
        self.is_recording = False
        self.video_writer = None
        self.audio_file = None
        self.start_time = 0
        self.frames = []
        self.audio_data = []
        
    def start_recording(self, filename):
        """开始录制"""
        try:
            # 创建输出目录
            os.makedirs('recordings', exist_ok=True)
            
            # 初始化视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                f'recordings/{filename}.mp4',
                fourcc, 30.0, (1920, 1080)
            )
            
            # 初始化音频文件
            self.audio_file = wave.open(f'recordings/{filename}.wav', 'wb')
            self.audio_file.setnchannels(2)
            self.audio_file.setsampwidth(2)
            self.audio_file.setframerate(44100)
            
            self.is_recording = True
            self.start_time = time.time()
            
        except Exception as e:
            logging.error(f"录制启动失败: {e}")
            
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return
            
        self.is_recording = False
        
        try:
            # 关闭视频写入器
            if self.video_writer:
                self.video_writer.release()
                
            # 关闭音频文件
            if self.audio_file:
                self.audio_file.close()
                
            # 合并音视频
            self.merge_audio_video()
            
        except Exception as e:
            logging.error(f"录制停止失败: {e}")
            
    def add_frame(self, frame):
        """添加视频帧"""
        if self.is_recording and self.video_writer:
            self.video_writer.write(frame)
            
    def add_audio(self, audio_data):
        """添加音频数据"""
        if self.is_recording and self.audio_file:
            self.audio_file.writeframes(audio_data)
            
    def merge_audio_video(self):
        """合并音视频"""
        try:
            # 使用ffmpeg合并
            input_video = f'recordings/temp_video.mp4'
            input_audio = f'recordings/temp_audio.wav'
            output = f'recordings/output_{int(time.time())}.mp4'
            
            os.system(f'ffmpeg -i {input_video} -i {input_audio} -c:v copy -c:a aac {output}')
            
            # 清理临时件
            os.remove(input_video)
            os.remove(input_audio)
            
        except Exception as e:
            logging.error(f"音视频合并失败: {e}")

# 创建录制实例
screen_recorder = ScreenRecorder()

# 添加录制控制接口
@socketio.on('start_recording')
def start_recording():
    """开始录制"""
    if not is_sharing:
        return {'error': '请先开始投屏'}
        
    filename = f'recording_{int(time.time())}'
    screen_recorder.start_recording(filename)
    return {'message': '开始录制'}
    
@socketio.on('stop_recording')
def stop_recording():
    """停止录制"""
    screen_recorder.stop_recording()
    return {'message': '录制已停止'}

# 添加远程控制支持
import win32api
import win32con
import win32gui
import win32ui
from ctypes import windll

class RemoteControl:
    def __init__(self):
        self.enabled = False
        self.controlling_client = None
        
    def enable(self, client_id):
        """启用远程控制"""
        self.enabled = True
        self.controlling_client = client_id
        
    def disable(self):
        """禁用远程控制"""
        self.enabled = False
        self.controlling_client = None
        
    def handle_mouse(self, x, y, button, action):
        """处理鼠标事件"""
        if not self.enabled:
            return
            
        try:
            # 转换坐标
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            real_x = int(x * screen_width)
            real_y = int(y * screen_height)
            
            # 移动鼠标
            win32api.SetCursorPos((real_x, real_y))
            
            # 处理点击
            if action == 'down':
                if button == 'left':
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, real_x, real_y, 0, 0)
                elif button == 'right':
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, real_x, real_y, 0, 0)
            elif action == 'up':
                if button == 'left':
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, real_x, real_y, 0, 0)
                elif button == 'right':
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, real_x, real_y, 0, 0)
                    
        except Exception as e:
            logging.error(f"鼠标事件处理失败: {e}")
            
    def handle_keyboard(self, key, action):
        """处理键盘事件"""
        if not self.enabled:
            return
            
        try:
            # 转换按键码
            vk_code = win32api.VkKeyScan(key)
            
            # 处理按键
            if action == 'down':
                win32api.keybd_event(vk_code, 0, 0, 0)
            elif action == 'up':
                win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
                
        except Exception as e:
            logging.error(f"键盘事件处理失败: {e}")

# 创建远程控制实例
remote_control = RemoteControl()

# 添加远程控制接口
@socketio.on('request_control')
def request_control():
    """请求远程控制"""
    client_id = request.sid
    if client_id not in connected_clients:
        return {'status': 'error', 'message': '未连接'}
        
    if remote_control.enabled:
        return {'status': 'error', 'message': '已有其他用户在控制'}
        
    remote_control.enable(client_id)
    return {'status': 'success'}
    
@socketio.on('release_control')
def release_control():
    """释放远程控制"""
    client_id = request.sid
    if remote_control.controlling_client == client_id:
        remote_control.disable()
        return {'status': 'success'}
    return {'status': 'error', 'message': '无控制权限'}
    
@socketio.on('mouse_event')
def handle_mouse_event(data):
    """处理鼠标事件"""
    client_id = request.sid
    if remote_control.controlling_client != client_id:
        return {'status': 'error', 'message': '无控制权限'}
        
    remote_control.handle_mouse(
        data.get('x', 0),
        data.get('y', 0),
        data.get('button', 'left'),
        data.get('action', 'move')
    )
    return {'status': 'success'}
    
@socketio.on('keyboard_event')
def handle_keyboard_event(data):
    """处理键盘事件"""
    client_id = request.sid
    if remote_control.controlling_client != client_id:
        return {'status': 'error', 'message': '无控制权限'}
        
    remote_control.handle_keyboard(
        data.get('key', ''),
        data.get('action', 'up')
    )
    return {'status': 'success'}

@app.route('/ping')
def ping():
    """用于客户端发现主端"""
    print(f"\n[Ping] 收到来自 {request.remote_addr} 的ping请求")
    return 'pong'

@app.route('/test_connection')
def test_connection():
    """测试连接状态"""
    return {
        'status': 'success',
        'message': '连接正常',
        'server_time': time.time(),
        'connected_clients': len(connected_clients),
        'server_ip': get_local_ip(),
        'server_port': config.get_int('主端', '默认端口', 5000)
    }

@app.route('/test')
def test_page():
    """连接测试页面"""
    return render_template('test.html')

if __name__ == '__main__':
    setup_logging()
    try:
        # 尝试默认端口
        port = config.get_int('主端', '默认端口', 5000)
        if port < 1024:  # 避免使用特权端口
            port = 5000
            
        # 如果默认端口不可用,查找其他端口
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
        except OSError:
            port = find_free_port(5000)
            
        ip = get_local_ip()
        print(f"主端运行在: http://{ip}:{port}")
        
        # 启动定期清理任务
        cleanup_timer = Timer(60.0, cleanup_stale_connections)
        cleanup_timer.daemon = True
        cleanup_timer.start()
        
        # 启动性能监控线程
        start_performance_monitor()
        
        socketio.run(app, 
                    host='0.0.0.0',
                    port=port,
                    debug=False,
                    use_reloader=False)
    except Exception as e:
        print(f"启动失败: {e}")
    finally:
        cleanup()