// 初始化Socket.IO连接
let socket = null;

function initializeClient(config) {
    // 创建Socket.IO连接
    const serverUrl = `http://${config.serverIp}:${config.port}`;
    console.log(`[连接] 尝试连接到服务器: ${serverUrl}`);

    socket = io(serverUrl, {
        transports: ['websocket', 'polling'],  // 允许降级到polling
        reconnection: true,
        reconnectionAttempts: config.reconnectionAttempts,
        reconnectionDelay: 1000,
        timeout: config.timeout,
        autoConnect: false  // 手动控制连接
    });

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
                break;
            case 'approved':
                showSuccess('连接已通过');
                updateStatus('已连接');
                // 保存连接信息
                localStorage.setItem('server_ip', config.serverIp);
                localStorage.setItem('server_port', config.port);
                break;
            case 'rejected':
                showError(`连接被拒绝: ${data.reason || '未知原因'}`);
                updateStatus('已断开');
                socket.disconnect();
                break;
        }
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
    
    // 如果设置了自动连接，则自动尝试连接
    if (config.autoConnect) {
        connectToServer();
    }
});