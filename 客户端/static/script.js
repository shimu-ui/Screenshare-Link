// 初始化Socket.IO连接
let socket = null;

function initializeClient(config) {
    // 创建Socket.IO连接
    const serverUrl = `http://${config.serverIp}:${config.port}`;
    console.log(`[连接] 尝试连接到服务器: ${serverUrl}`);

    socket = io(serverUrl, {
        transports: ['polling', 'websocket'],  // 优先使用polling，与主端保持一致
        upgrade: true,
        rememberUpgrade: true,
        timeout: 30000,  // 增加超时时间
        forceNew: true,
        reconnection: true,
        reconnectionAttempts: 10,  // 增加重连次数
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        maxReconnectionAttempts: 10,
        autoConnect: false,  // 手动控制连接
        path: '/socket.io/'  // 明确指定路径
    });

    // 如果跳过认证，直接发送认证信息
    if (config.skipAuth && config.deviceId) {
        socket.on('connect', () => {
            console.log('[连接] 已认证客户端重新连接');
            showSuccess('连接已恢复');
            updateStatus('已连接');
            
            // 发送认证信息给服务器
            socket.emit('reconnect_approved', {
                device_id: config.deviceId,
                server_ip: config.serverIp,
                server_port: config.port
            });
        });
    }

    // 连接状态处理
    socket.on('connect', () => {
        console.log('[连接] Socket连接成功，等待审核');
        showStatus('等待主端审核...');
        updateStatus('等待审核');
    });

    // 处理认证状态
    socket.on('auth_status', (data) => {
        console.log('[认证] 状态:', data);
        switch(data.status) {
            case 'pending':
                showStatus(`等待主端审核 (设备ID: ${data.device_id})`);
                updateStatus('等待审核');
                // 更新设备ID显示
                document.getElementById('device-id').textContent = data.device_id;
                break;
            case 'approved':
                showSuccess('连接已通过');
                updateStatus('已连接');
                // 保存连接信息和认证状态
                localStorage.setItem('server_ip', config.serverIp);
                localStorage.setItem('server_port', config.port);
                localStorage.setItem('auth_status', 'approved');
                localStorage.setItem('device_id', data.device_id);
                break;
            case 'rejected':
                showError(`连接被拒绝: ${data.reason || '未知原因'}`);
                updateStatus('已断开');
                socket.disconnect();
                break;
        }
    });

    // 接收屏幕数据
    socket.on('screen_data', (data) => {
        const canvas = document.getElementById('screen');
        const ctx = canvas.getContext('2d');
        const img = new Image();
        
        img.onload = () => {
            // 调整canvas大小以适应图像
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
        };
        
        img.src = 'data:image/jpeg;base64,' + data.image;
    });

    // 接收文件广播
    socket.on('file_broadcast', (data) => {
        console.log('收到文件广播:', data);
        showFileNotification(data.filename, data.url);
    });

    socket.on('disconnect', (reason) => {
        console.log(`[连接] 断开: ${reason}`);
        showError(`连接断开: ${reason}`);
        updateStatus('已断开');
    });

    socket.on('connect_error', (error) => {
        console.error('[连接] 错误:', error);
        showError(`连接错误: ${error.message}`);
        updateStatus('连接错误');
    });

    // 尝试连接
    socket.connect();
}

// 连接相关函数
function connectToServer() {
    const ip = document.getElementById('server-ip').value;
    const port = document.getElementById('server-port').value;
    
    if (!ip || !port) {
        showError('请输入IP地址和端口');
        return;
    }

    // 检查是否已经通过认证
    const savedAuthStatus = localStorage.getItem('auth_status');
    const savedServerIp = localStorage.getItem('server_ip');
    const savedServerPort = localStorage.getItem('server_port');
    const savedDeviceId = localStorage.getItem('device_id');
    
    // 如果之前已经通过认证，且连接的是同一个服务器
    if (savedAuthStatus === 'approved' && savedServerIp === ip && savedServerPort === port) {
        console.log('[连接] 检测到已认证的连接，尝试直接连接...');
        showStatus('正在重新连接...');
        
        // 直接初始化连接，不等待审核
        if (socket) {
            console.log('[连接] 断开旧连接');
            socket.disconnect();
        }

        initializeClient({
            serverIp: ip,
            port: port,
            reconnectionAttempts: 5,
            timeout: 5000,
            skipAuth: true,  // 跳过认证
            deviceId: savedDeviceId
        });
        
        return;
    }

    showStatus('正在连接...');
    console.log(`[连接] 尝试连接到: ${ip}:${port}`);

    // 先测试HTTP连接
    fetch(`http://${ip}:${port}/ping`)
        .then(response => response.text())
        .then(data => {
            if (data === 'pong') {
                console.log('[连接] HTTP连接测试成功');
                
                // 初始化Socket.IO连接
                if (socket) {
                    console.log('[连接] 断开旧连接');
                    socket.disconnect();
                }

                initializeClient({
                    serverIp: ip,
                    port: port,
                    reconnectionAttempts: 5,
                    timeout: 5000
                });

                showStatus('正在等待审核...');
            } else {
                throw new Error('无效响应');
            }
        })
        .catch(error => {
            console.error('[连接] 失败:', error);
            showError('连接失败: ' + error.message);
        });
}

// 自动发现主端
function autoDiscover() {
    showStatus('正在搜索主端...');
    
    fetch('/discover')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('server-ip').value = data.ip;
                document.getElementById('server-port').value = data.port;
                showSuccess('找到主端!');
                connectToServer(); // 自动连接
            } else {
                throw new Error(data.message || '未找到主端');
            }
        })
        .catch(error => {
            showError('自动发现失败: ' + error.message);
        });
}

// 重新连接函数
function reconnect() {
    if (socket) {
        socket.disconnect();
    }
    connectToServer();
}

// 全屏切换函数
function toggleFullscreen() {
    const screenContainer = document.getElementById('screen-container');
    if (screenContainer) {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            screenContainer.requestFullscreen();
        }
    }
}

// 打开下载文件夹
function openDownloadsFolder() {
    // 这里可以添加打开下载文件夹的逻辑
    console.log('打开下载文件夹');
}

// 显示文件通知
function showFileNotification(filename, url) {
    const notificationsList = document.getElementById('file-notifications');
    const badge = document.getElementById('notification-badge');
    
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = 'file-notification';
    notification.innerHTML = `
        <div class="notification-content">
            <span class="filename">${filename}</span>
            <div class="notification-actions">
                <button onclick="downloadFile('${url}', '${filename}')" class="download-btn">
                    <i class="fas fa-download"></i> 下载
                </button>
                <button onclick="this.parentElement.parentElement.parentElement.remove()" class="dismiss-btn">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `;
    
    notificationsList.appendChild(notification);
    
    // 更新通知数量
    const count = notificationsList.children.length;
    badge.textContent = count;
    badge.style.display = count > 0 ? 'inline' : 'none';
}

// 下载文件
function downloadFile(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 状态更新函数
function updateStatus(message) {
    const status = document.getElementById('status');
    if (status) {
        status.textContent = message;
    }
}

function showStatus(message) {
    const status = document.getElementById('connection-status');
    status.textContent = message;
    status.className = 'status-text';
}

function showSuccess(message) {
    const status = document.getElementById('connection-status');
    status.textContent = message;
    status.className = 'status-text success';
}

function showError(message) {
    const status = document.getElementById('connection-status');
    status.textContent = message;
    status.className = 'status-text error';
}

// 加载保存的连接信息
document.addEventListener('DOMContentLoaded', () => {
    const savedIp = localStorage.getItem('server_ip');
    const savedPort = localStorage.getItem('server_port');
    
    if (savedIp) {
        document.getElementById('server-ip').value = savedIp;
    } else {
        // 如果没有保存的IP，使用本机IP
        const localIp = document.getElementById('server-ip').placeholder.replace('例如: ', '');
        document.getElementById('server-ip').value = localIp;
    }
    
    if (savedPort) {
        document.getElementById('server-port').value = savedPort;
    }
    
    // 不自动连接，等待用户手动点击连接按钮
});