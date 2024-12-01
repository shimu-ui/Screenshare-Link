document.addEventListener('DOMContentLoaded', () => {
    initializeMedia();
    console.log('DOM loaded, initializing socket connection...');
    
    const socket = io('http://127.0.0.1:5000', {
        transports: ['websocket', 'polling'],
        upgrade: true,
        rememberUpgrade: true,
        timeout: 10000,
    });

    let isSharing = false;

    // 监听连接数量更新
    socket.on('client_count', (data) => {
        console.log('Client count updated:', data.count);
        document.getElementById('client-count').textContent = `连接设备: ${data.count}`;
        
        // 如果没有设备连接，禁用开始按钮
        const startButton = document.getElementById('start');
        startButton.disabled = data.count === 0;
    });

    socket.on('connect', () => {
        console.log('Connected to server');
        updateStatus('已连接到服务器');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        updateStatus('已断开连接');
    });

    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        updateStatus('连接错误');
    });

    // 窗口选择功能
    window.refreshWindows = async () => {
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
            console.log('窗口列表已更新');
        } catch (error) {
            console.error('获取窗口列表失败:', error);
            updateStatus('获取窗口列表失败');
        }
    };

    // 开始投屏按钮处理
    document.getElementById('start').onclick = () => {
        if (!isSharing) {
            const windowId = document.getElementById('window-list').value;
            console.log('选择的窗口ID:', windowId);
            socket.emit('start_screen_share', { window_id: windowId });
            isSharing = true;
            updateStatus('正在投屏' + (windowId ? ' (窗口模式)' : ' (全屏模式)'));
            document.getElementById('start').disabled = true;
            document.getElementById('stop').disabled = false;
            document.getElementById('window-list').disabled = true;
        }
    };

    // 停止投屏按钮处理
    document.getElementById('stop').onclick = () => {
        if (isSharing) {
            socket.emit('stop_screen_share');
            isSharing = false;
            updateStatus('已停止投屏');
            document.getElementById('start').disabled = false;
            document.getElementById('stop').disabled = true;
            document.getElementById('window-list').disabled = false;
        }
    };

    function updateStatus(message) {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = `当前状态: ${message}`;
        }
    }

    // 初始状态
    document.getElementById('stop').disabled = true;
    updateStatus('未开始');
    document.getElementById('client-count').textContent = '连接设备: 0';

    // 初始加载窗口列表
    refreshWindows();

    // 定期刷新窗口列表
    setInterval(refreshWindows, 10000); // 每10秒刷新一次
});

async function initializeMedia() {
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.log('浏览器不支持getUserMedia');
            return;
        }
        
        // 请求屏幕共享权限
        const stream = await navigator.mediaDevices.getUserMedia({
            video: true
        });
        
        // 停止所有轨道
        stream.getTracks().forEach(track => track.stop());
    } catch (err) {
        console.log('获取媒体设备权限失败:', err);
    }
}