// Socket.IO连接
const socket = io({
    transports: ['polling', 'websocket'],  // 与主端保持一致，优先使用polling
    upgrade: true,
    rememberUpgrade: true,
    timeout: 30000,  // 增加超时时间
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    maxReconnectionAttempts: 10,
    forceNew: true,
    path: '/socket.io/'  // 明确指定路径
});

let isTestRunning = false;

// 添加自动刷新功能
let autoRefreshInterval = null;
const REFRESH_INTERVAL = 5000; // 5秒刷新一次

// 添加日志条目
function addLogEntry(message, type = 'info') {
    const container = document.getElementById('log-container');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="log-time">[${time}]</span> ${message}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

// 刷新窗口列表
async function refreshWindows() {
    try {
        const response = await fetch('/get_windows');
        const windows = await response.json();
        const select = document.getElementById('window-list');
        select.innerHTML = '<option value="">全屏模式</option>';
        
        windows.forEach(window => {
            const option = document.createElement('option');
            option.value = window.id;
            option.textContent = window.title;
            select.appendChild(option);
        });
        addLogEntry('窗口列表已更新');
    } catch (error) {
        addLogEntry('获取窗口列表失败: ' + error, 'error');
    }
}

// 开始测试
function startTest() {
    if (!isTestRunning) {
        const windowId = document.getElementById('window-list').value;
        socket.emit('start_screen_share', { window_id: windowId });
        isTestRunning = true;
        addLogEntry('开始测试投屏' + (windowId ? ' (窗口模式)' : ' (全屏模式)'));
        document.getElementById('window-list').disabled = true;
    }
}

// 停止测试
function stopTest() {
    if (isTestRunning) {
        socket.emit('stop_screen_share');
        isTestRunning = false;
        addLogEntry('停止测试投屏');
        document.getElementById('window-list').disabled = false;
    }
}

// 更新客户端列表
function updateClientList(clients) {
    const list = document.getElementById('client-list');
    list.innerHTML = '';
    Object.entries(clients).forEach(([id, info]) => {
        const item = document.createElement('div');
        item.className = 'client-item';
        item.innerHTML = `
            <div class="client-info">
                <span class="client-ip">${info.ip}</span>
                <span class="client-id">${id}</span>
            </div>
            <span class="client-status">已连接</span>
        `;
        list.appendChild(item);
    });
}

// Socket.IO事件处理
socket.on('connect', () => {
    addLogEntry('已连接到服务器');
    console.log('调试页面Socket.IO连接成功');
});

socket.on('disconnect', (reason) => {
    addLogEntry('与服务器断开连接: ' + reason, 'error');
    console.log('调试页面Socket.IO断开连接:', reason);
    isTestRunning = false;
});

socket.on('connect_error', (error) => {
    addLogEntry('连接错误: ' + error.message, 'error');
    console.error('调试页面Socket.IO连接错误:', error);
});

socket.on('reconnect', (attemptNumber) => {
    addLogEntry('重新连接成功 (第' + attemptNumber + '次尝试)');
    console.log('调试页面Socket.IO重新连接成功:', attemptNumber);
});

socket.on('reconnect_error', (error) => {
    addLogEntry('重新连接失败: ' + error.message, 'error');
    console.error('调试页面Socket.IO重新连接失败:', error);
});

socket.on('screen_data', (data) => {
    try {
        const preview = document.getElementById('preview');
        if (preview) {
            preview.src = 'data:image/jpeg;base64,' + data.image;
        }
    } catch (error) {
        addLogEntry('预览更新失败: ' + error, 'error');
    }
});

socket.on('performance_update', (data) => {
    try {
        // 更新FPS
        const fpsElement = document.getElementById('current-fps');
        if (fpsElement) {
            fpsElement.textContent = parseFloat(data.fps).toFixed(1);
        }

        // 更新CPU使用率
        const cpuElement = document.getElementById('cpu-usage');
        if (cpuElement) {
            cpuElement.textContent = `${parseFloat(data.cpu).toFixed(1)}%`;
        }

        // 更新内存使用
        const memoryElement = document.getElementById('memory-usage');
        if (memoryElement) {
            memoryElement.textContent = `${(data.memory / 1024 / 1024).toFixed(1)} MB`;
        }

        // 更新客户端数量（两个位置）
        const headerClientCount = document.getElementById('header-client-count');
        const metricsClientCount = document.getElementById('metrics-client-count');
        
        if (headerClientCount) {
            headerClientCount.textContent = `连接设备: ${data.clients}`;
        }
        if (metricsClientCount) {
            metricsClientCount.textContent = data.clients;
        }

        // 更新投屏状态
        const statusElement = document.getElementById('sharing-status');
        if (statusElement) {
            if (data.status === 'running') {
                statusElement.textContent = '正在投屏';
                statusElement.style.color = '#2ecc71';
            } else {
                statusElement.textContent = '已停止';
                statusElement.style.color = '#e74c3c';
            }
        }
    } catch (error) {
        addLogEntry('性能数据更新失败: ' + error, 'error');
    }
});

socket.on('screen_stopped', () => {
    const preview = document.getElementById('preview');
    if (preview) {
        preview.src = '';
    }
    document.getElementById('sharing-status').textContent = '已停止';
    isTestRunning = false;
    document.getElementById('window-list').disabled = false;
    addLogEntry('投屏已停止');
});

// 更新待审核客户端UI
socket.on('new_pending_client', (data) => {
    console.log('收到新的待审核客户端:', data);
    
    const pendingList = document.getElementById('pending-list');
    if (!pendingList) {
        console.error('找不到待审核列表容器');
        return;
    }
    
    // 检查是否已经存在相同的客户端
    const existingItem = pendingList.querySelector(`[data-client-id="${data.id}"]`);
    if (existingItem) {
        console.log('客户端已存在，跳过重复添加:', data.id);
        return;
    }
    
    const item = document.createElement('div');
    item.className = 'client-item pending';
    item.dataset.clientId = data.id;  // 存储客户端ID
    item.innerHTML = `
        <div class="client-info">
            <span class="device-id">${data.device_id}</span>
            <span class="client-ip">${data.ip}</span>
        </div>
        <div class="client-controls">
            <button onclick="approveClient('${data.id}')" class="button approve">同意</button>
            <button onclick="rejectClient('${data.id}')" class="button reject">拒绝</button>
        </div>
    `;
    pendingList.appendChild(item);
    addLogEntry(`新的待审核客户端: ${data.device_id} (${data.ip})`);
});

// 批准客户端
function approveClient(clientId) {
    socket.emit('approve_client', { client_id: clientId });
    const item = document.querySelector(`[data-client-id="${clientId}"]`);
    if (item) {
        // 获取客户端信息
        const deviceId = item.querySelector('.device-id').textContent;
        const clientIp = item.querySelector('.client-ip').textContent;
        
        // 添加到已连接列表
        addToConnectedList(clientId, deviceId, clientIp);
        
        // 从待审核列表移除
        item.remove();
    }
    addLogEntry(`已批准客户端: ${clientId}`);
}

// 添加到已连接列表
function addToConnectedList(clientId, deviceId, clientIp) {
    const connectedList = document.getElementById('connected-list');
    if (!connectedList) return;
    
    // 检查是否已经存在相同的客户端（基于IP和设备ID）
    const existingItem = connectedList.querySelector(`[data-client-ip="${clientIp}"][data-device-id="${deviceId}"]`);
    if (existingItem) {
        console.log('客户端已存在，跳过重复添加:', clientId, deviceId, clientIp);
        return;
    }
    
    const item = document.createElement('div');
    item.className = 'client-item connected';
    item.dataset.clientId = clientId;
    item.dataset.clientIp = clientIp;
    item.dataset.deviceId = deviceId;
    item.innerHTML = `
        <div class="client-info">
            <span class="device-id">${deviceId}</span>
            <span class="client-ip">${clientIp}</span>
        </div>
        <div class="client-status">
            <span class="status-connected">已连接</span>
        </div>
    `;
    connectedList.appendChild(item);
}

// 拒绝客户端
function rejectClient(clientId) {
    socket.emit('reject_client', { client_id: clientId });
    const item = document.querySelector(`[data-client-id="${clientId}"]`);
    if (item) {
        // 禁用按钮，防止重复点击
        const buttons = item.querySelectorAll('button');
        buttons.forEach(button => {
            button.disabled = true;
            button.style.opacity = '0.5';
        });

        // 显示审核状态
        const controls = item.querySelector('.client-controls');
        if (controls) {
            // 创建状态元素
            const status = document.createElement('span');
            status.className = 'status-rejected';
            status.textContent = '已拒绝';
            
            // 使用淡入淡出效果替换按钮
            controls.style.opacity = '0';
            setTimeout(() => {
                controls.innerHTML = '';
                controls.appendChild(status);
                controls.style.opacity = '1';
            }, 300);
        }

        // 添加淡出动画并移除
        setTimeout(() => {
            item.style.animation = 'fadeOut 0.5s ease forwards';
            setTimeout(() => {
                item.remove();
            }, 500);
        }, 1000);  // 等待1秒后开始淡出
    }
    addLogEntry(`已拒绝客户端: ${clientId}`);
}

// 从待审核列表移除
function removeFromPendingList(clientId) {
    const pendingList = document.getElementById('pending-list');
    if (!pendingList) return;

    const item = pendingList.querySelector(`[data-client-id="${clientId}"]`);
    if (item) {
        item.remove();
    }
}

// 处理客户端状态更新
socket.on('client_count', (data) => {
    console.log('收到客户端数量更新:', data);
    
    // 更新客户端数量显示
    const headerClientCount = document.getElementById('header-client-count');
    const metricsClientCount = document.getElementById('metrics-client-count');
    
    if (headerClientCount) {
        headerClientCount.textContent = `连接设备: ${data.count}`;
    }
    if (metricsClientCount) {
        metricsClientCount.textContent = data.count;
    }
    
    // 更新已连接客户端列表
    updateConnectedClientList(data.clients);
});

// 更新已连接客户端列表
function updateConnectedClientList(clients) {
    const connectedList = document.getElementById('connected-list');
    if (!connectedList) return;
    
    // 清空现有列表
    connectedList.innerHTML = '';
    
    // 添加新的客户端（去重）
    const addedClients = new Set();
    clients.forEach(client => {
        const clientKey = `${client.ip}-${client.device_id}`;
        if (!addedClients.has(clientKey)) {
            addToConnectedList(client.id, client.device_id, client.ip);
            addedClients.add(clientKey);
        }
    });
}

// 处理移除待审核客户端
socket.on('remove_pending_client', (data) => {
    console.log('移除待审核客户端:', data);
    removeFromPendingList(data.id);
});

// 添加到黑名单
function addToBlacklist() {
    const ip = document.getElementById('blacklist-ip').value.trim();
    if (ip) {
        socket.emit('add_to_blacklist', { ip });
        document.getElementById('blacklist-ip').value = '';
        addLogEntry(`已添加IP到黑名单: ${ip}`);
    }
}

// 加载黑名单列表
async function loadBlacklist() {
    try {
        const response = await fetch('/get_blacklist');
        const blacklistIPs = await response.json();
        updateBlacklistUI(blacklistIPs);
    } catch (error) {
        addLogEntry('加载黑名单失败: ' + error, 'error');
    }
}

// 更新黑名单UI
function updateBlacklistUI(ips) {
    const blacklistContainer = document.getElementById('blacklist');
    blacklistContainer.innerHTML = '';
    
    ips.forEach(ip => {
        const item = document.createElement('div');
        item.className = 'client-item blacklist';
        item.innerHTML = `
            <div class="client-info">
                <span class="client-ip">${ip}</span>
            </div>
            <div class="client-controls">
                <button onclick="removeFromBlacklist('${ip}')" class="button">移除</button>
            </div>
        `;
        blacklistContainer.appendChild(item);
    });
}

// 从黑名单移除
function removeFromBlacklist(ip) {
    socket.emit('remove_from_blacklist', { ip });
    addLogEntry(`已从黑名单移除IP: ${ip}`);
}

// 监听黑名单更新
socket.on('blacklist_updated', (data) => {
    loadBlacklist();
    addLogEntry(`黑名单${data.action === 'add' ? '添加' : '移除'}IP: ${data.ip}`);
});

// 自动刷新函数
function startAutoRefresh() {
    if (autoRefreshInterval) return;
    
    autoRefreshInterval = setInterval(() => {
        // 更新客户端列表
        socket.emit('get_clients');
        
        // 更新待审核列表
        socket.emit('get_pending_clients');
        
        // 更新黑名单
        loadBlacklist();
        
        // 刷新窗口列表
        refreshWindows();
    }, REFRESH_INTERVAL);
    
    console.log('自动刷新已启动');
}

// 停止自动刷新
function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        console.log('自动刷新已停止');
    }
}

// 页面获得/失去焦点时的处理
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // 页面不可见时停止自动刷新
        stopAutoRefresh();
    } else {
        // 页面可见时启动自动刷新
        startAutoRefresh();
        // 立即刷新一次
        socket.emit('get_clients');
        socket.emit('get_pending_clients');
        loadBlacklist();
        refreshWindows();
    }
});

// 在页面加载时启动自动刷新
document.addEventListener('DOMContentLoaded', () => {
    startAutoRefresh();
    loadBlacklist();
});

// 在页面关闭或离开时清理
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});

// 初始化
refreshWindows();
addLogEntry('调试页面已加载');

// 导出全局函数
window.startTest = startTest;
window.stopTest = stopTest;
window.refreshWindows = refreshWindows;
window.addToBlacklist = addToBlacklist;
window.removeFromBlacklist = removeFromBlacklist;

// 更新已连接客户端列表
socket.on('client_count', (data) => {
    const connectedList = document.getElementById('connected-list');
    if (connectedList && data.clients) {
        connectedList.innerHTML = '';
        data.clients.forEach(client => {
            const item = document.createElement('div');
            item.className = 'client-item connected';
            item.innerHTML = `
                <div class="client-info">
                    <span class="device-id">${client.device_id}</span>
                    <span class="client-ip">${client.ip}</span>
                </div>
                <div class="client-status">已连接</div>
            `;
            connectedList.appendChild(item);
        });
    }
}); 