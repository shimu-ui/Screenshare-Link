// 全局变量
let socket = null;
let pendingFrame = null;
let animationFrameId = null;
let isFullscreen = false;
let isConnected = false;

// 初始化Socket.IO
function initSocket(config) {
    console.log('正在初始化连接...', config);
    
    // 获取设备名称
    let deviceName = config.deviceName;
    if(deviceName === 'auto') {
        // 尝试获取主机名
        try {
            deviceName = window.location.hostname;
        } catch(e) {
            deviceName = null;
        }
    }
    
    // 创建Socket连接
    const socketUrl = `http://${config.serverIp}:5000`;
    console.log('尝试连接到:', socketUrl);
    
    socket = io(socketUrl, {
        transports: ['websocket', 'polling'],
        upgrade: true,
        rememberUpgrade: true,
        timeout: config.timeout || 10000,
        reconnection: true,
        reconnectionAttempts: config.reconnectionAttempts || 5,
        query: { 
            type: 'client',
            deviceName: deviceName  // 传递设备名称
        }
    });

    // 连接事件处理
    socket.on('connect', () => {
        console.log('Socket连接成功，等待服务器审核...');
        console.log('Socket ID:', socket.id);
        isConnected = true;
        updateStatus('等待管理员审核...');
        updateConnectionStatus('等待审核', 'waiting');
    });

    // 断开连接事件
    socket.on('disconnect', () => {
        isConnected = false;
        updateStatus('连接断开');
        updateConnectionStatus('已断开', 'disconnected');
    });

    socket.on('connect_error', (error) => {
        console.error('连接错误:', error);
        console.error('错误详情:', {
            message: error.message,
            description: error.description,
            type: error.type
        });
        updateStatus('连接失败: ' + error.message);
        updateConnectionStatus('连接错误', 'disconnected');
    });

    // 认证状态处理
    socket.on('auth_status', (data) => {
        console.log('收到认证状态:', data);
        if (data.status === 'pending') {
            updateStatus('等待管理员审核...');
            updateConnectionStatus('等待审核', 'waiting');
        } else if (data.status === 'approved') {
            updateStatus('已通过审核');
            updateConnectionStatus('已连接', 'connected');
            // 更新设备ID显示
            const deviceIdElement = document.getElementById('device-id');
            if (deviceIdElement && data.device_id) {
                deviceIdElement.textContent = data.device_id;
            }
        } else if (data.status === 'rejected') {
            updateStatus('连接被拒绝');
            updateConnectionStatus('已拒绝', 'disconnected');
            socket.disconnect();
        }
    });

    // 接收画面帧
    socket.on('screen_frame', (data) => {
        updateImage(data);
    });

    // 投屏停止事件
    socket.on('screen_stopped', () => {
        const img = document.getElementById('screen');
        if (img) {
            img.src = '';
            img.style.display = 'none';
        }
        updateStatus('投屏已停止');
    });

    // 添加文件接收事件处理
    socket.on('file_broadcast', (data) => {
        console.log('收到文件广播:', data);
        const { filename, url, size } = data;
        
        // 创建文件接收通知
        const notification = document.createElement('div');
        notification.className = 'file-notification';
        notification.innerHTML = `
            <div class="file-info">
                <i class="fas fa-file"></i>
                <span class="file-name">${filename}</span>
                <span class="file-size">(${formatFileSize(size)})</span>
                <div class="file-actions">
                    <button onclick="downloadFile('${url}', '${filename}')" class="download-btn">
                        <i class="fas fa-download"></i> 下载
                    </button>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" class="close-btn">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
        
        // 添加到通知区域
        const notificationArea = document.getElementById('file-notifications');
        if (notificationArea) {
            notificationArea.insertBefore(notification, notificationArea.firstChild);
            
            // 更新通知计数
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                const count = notificationArea.children.length;
                badge.textContent = count;
                badge.style.display = count > 0 ? 'inline-block' : 'none';
            }
        } else {
            console.error('找不到通知区域元素');
        }
    });
}

// 图像处理
function updateImage(data) {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }
    pendingFrame = data;
    animationFrameId = requestAnimationFrame(renderFrame);
}

function renderFrame() {
    if (!pendingFrame) return;
    
    const img = document.getElementById('screen');
    if (!img) return;

    try {
        // 创建图像URL
        const url = 'data:image/jpeg;base64,' + pendingFrame.image;
        
        // 直接设置图像源
        img.src = url;
        img.style.display = 'block';  // 确保图像显示

        // 更新尺寸
        if (pendingFrame.width && pendingFrame.height) {
            // 获取容器尺寸
            const container = document.getElementById('screen-container');
            const containerWidth = container.clientWidth;
            const containerHeight = container.clientHeight;
            
            // 计算缩放比例
            const scaleX = containerWidth / pendingFrame.width;
            const scaleY = containerHeight / pendingFrame.height;
            const scale = Math.min(scaleX, scaleY);
            
            // 应用缩放
            const width = pendingFrame.width * scale;
            const height = pendingFrame.height * scale;
            
            img.style.width = width + 'px';
            img.style.height = height + 'px';
            img.style.maxWidth = '100%';
            img.style.maxHeight = '100%';
            img.style.objectFit = 'contain';
        }

    } catch (error) {
        console.error('渲染错误:', error);
        img.style.display = 'none';
    }
    
    pendingFrame = null;
}

// 状态更新
function updateStatus(message) {
    const status = document.getElementById('status');
    if (status) {
        status.textContent = message;
        console.log('状态更新:', message);
    }
}

function updateConnectionStatus(message, type) {
    const statusText = document.getElementById('status-text');
    if (statusText) {
        statusText.textContent = message;
        statusText.className = `status-text status-${type}`;
        console.log('连接状态更新:', message, type);
    }
}

// 全屏控制
function toggleFullscreen() {
    const container = document.getElementById('screen-container');
    if (!container) return;

    if (!isFullscreen) {
        if (container.requestFullscreen) {
            container.requestFullscreen().catch(error => {
                console.error('全屏错误:', error);
            });
        }
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen().catch(error => {
                console.error('退出全屏错误:', error);
            });
        }
    }
}

// 监听全屏变化
document.addEventListener('fullscreenchange', () => {
    isFullscreen = !!document.fullscreenElement;
    const container = document.getElementById('screen-container');
    if (container) {
        container.classList.toggle('fullscreen', isFullscreen);
    }
});

// 重连功能
function reconnect() {
    if (socket && !isConnected) {
        socket.connect();
        updateStatus('正在重新连接...');
    }
}

// 初始化客户端
function initializeClient(config) {
    console.log('初始化客户端配置:', config);
    initSocket(config);

    // 自动全屏
    if (config.autoConnect && config.fullscreen) {
        setTimeout(() => {
            toggleFullscreen();
        }, 1000);
    }
}

// 添加文件大小格式化函数
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 添加文件下载函数
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 导出全局函数
window.toggleFullscreen = toggleFullscreen;
window.reconnect = reconnect;
window.initializeClient = initializeClient;
window.downloadFile = downloadFile;  // 导出下载函数