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

    // 初始化文件传输
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const selectedFiles = document.getElementById('selectedFiles');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');

    fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files);
        selectedFiles.innerHTML = files.map(file => `
            <div class="selected-file">
                <span>${file.name}</span> (${formatFileSize(file.size)})
            </div>
        `).join('');
    });

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function updateProgress(file, loaded, total) {
        const percent = (loaded / total * 100).toFixed(2);
        progressBar.style.width = percent + '%';
        progressText.textContent = `${file.name}: ${percent}%`;
        
        // 添加渐变色效果
        const hue = (percent * 1.2); // 120是绿色的色相值
        progressBar.style.backgroundColor = `hsl(${hue}, 70%, 50%)`;
    }

    function broadcastFiles() {
        const files = fileInput.files;
        if (files.length === 0) {
            alert('请选择要广播的文件');
            return;
        }

        Array.from(files).forEach((file, index) => {
            const formData = new FormData();
            formData.append('file', file);

            // 创建进度条项
            const progressItem = document.createElement('div');
            progressItem.className = 'progress-item';
            progressItem.innerHTML = `
                <div class="file-info">
                    <span class="filename">${file.name}</span>
                    <span class="filesize">(${formatFileSize(file.size)})</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar"></div>
                    <span class="progress-text">0%</span>
                </div>
            `;
            fileList.appendChild(progressItem);

            const progressBar = progressItem.querySelector('.progress-bar');
            const progressText = progressItem.querySelector('.progress-text');

            // 使用 XMLHttpRequest 获取上传进度
            const xhr = new XMLHttpRequest();
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total * 100).toFixed(1);
                    progressBar.style.width = percent + '%';
                    progressText.textContent = percent + '%';
                    
                    // 广播进度到客户端
                    socket.emit('upload_progress', {
                        filename: file.name,
                        loaded: e.loaded,
                        total: e.total,
                        percent: percent
                    });
                }
            };

            xhr.onload = () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    progressText.textContent = '完成';
                    progressBar.style.backgroundColor = '#2ecc71';
                }
            };

            xhr.onerror = () => {
                progressText.textContent = '失败';
                progressBar.style.backgroundColor = '#e74c3c';
            };

            xhr.open('POST', '/upload', true);
            xhr.send(formData);
        });
    }

    // 绑定广播按钮事件
    document.querySelector('.file-upload button').addEventListener('click', broadcastFiles);

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