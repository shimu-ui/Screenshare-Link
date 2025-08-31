document.addEventListener('DOMContentLoaded', () => {
    initializeMedia();
    console.log('DOM loaded, using existing socket connection...');
    
    // 使用HTML中已创建的socket实例
    const socket = window.socket;
    if (!socket) {
        console.error('Socket.IO连接未找到！');
        return;
    }

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

    // 将broadcastFiles函数暴露到全局作用域，这样HTML中的onclick就能找到它
    window.broadcastFiles = function() {
        const files = fileInput.files;
        if (files.length === 0) {
            alert('请选择要广播的文件');
            return;
        }

        // 不清空已选择的文件显示，只清空进度条
        selectedFiles.innerHTML = Array.from(files).map(file => `
            <div class="selected-file">
                <span>${file.name}</span> (${formatFileSize(file.size)})
            </div>
        `).join('');
        
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
                    
                    // 显示广播成功消息
                    console.log(`文件 ${file.name} 上传并广播成功`);
                    
                    // 保持进度条显示，不自动移除
                    // 用户可以手动刷新页面来清理
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

    // 绑定广播按钮事件 - 移除重复绑定，因为HTML中已经有onclick
    // document.querySelector('.file-upload button').addEventListener('click', broadcastFiles);

    // 监听连接数量更新 - 由HTML中的处理程序处理
    socket.on('client_count', (data) => {
        console.log('Client count updated:', data.count);
        
        // 如果没有设备连接，禁用开始按钮
        const startButton = document.getElementById('start');
        if (startButton) {
            startButton.disabled = data.count === 0;
        }
        
        // 更新客户端数量显示
        const clientCountElement = document.getElementById('header-client-count');
        if (clientCountElement) {
            clientCountElement.textContent = `连接设备: ${data.count}`;
        }
        
        // 更新连接统计
        const currentConnectionsElement = document.getElementById('current-connections');
        if (currentConnectionsElement) {
            currentConnectionsElement.textContent = data.count;
        }
    });
    
    // 监听性能数据更新
    socket.on('performance_update', (data) => {
        console.log('Performance data received:', data);
        
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
        
        // 更新帧率
        const fpsElement = document.getElementById('fps-counter');
        if (fpsElement) {
            fpsElement.textContent = `${parseFloat(data.fps).toFixed(1)} FPS`;
        }
        
        // 更新连接统计
        const currentConnectionsElement = document.getElementById('current-connections');
        if (currentConnectionsElement) {
            currentConnectionsElement.textContent = data.clients;
        }
        
        // 更新总连接数
        const totalConnectionsElement = document.getElementById('total-connections');
        if (totalConnectionsElement) {
            totalConnectionsElement.textContent = data.clients;
        }
        
        // 更新网络流量
        const networkElement = document.getElementById('network-usage');
        if (networkElement && data.network !== undefined) {
            networkElement.textContent = `${parseFloat(data.network).toFixed(1)} KB/s`;
        }
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
    
    // 初始化客户端计数显示
    const clientCountElement = document.getElementById('header-client-count');
    if (clientCountElement) {
        clientCountElement.textContent = '连接设备: 0';
    }

    // 初始加载窗口列表
    refreshWindows();

    // 定期刷新窗口列表
    setInterval(refreshWindows, 10000); // 每10秒刷新一次

    // 画质设置处理
    function initQualityControls() {
        const qualityInput = document.getElementById('quality');
        const resolutionInput = document.getElementById('resolution');
        const fpsInput = document.getElementById('fps');
        const compressionSelect = document.getElementById('compression');
        const optimizeModeSelect = document.getElementById('optimize-mode');
        
        // 更新显示值
        function updateValue(input) {
            const value = input.nextElementSibling;
            if (input.id === 'resolution') {
                value.textContent = input.value + '%';
            } else {
                value.textContent = input.value;
            }
        }
        
        // 发送设置更新
        function updateQualitySettings() {
            socket.emit('update_quality', {
                quality: parseInt(qualityInput.value),
                resolution_scale: parseInt(resolutionInput.value) / 100,
                fps_limit: parseInt(fpsInput.value),
                compression: compressionSelect.value,
                optimize_mode: optimizeModeSelect.value
            });
        }
        
        // 添加事件监听
        [qualityInput, resolutionInput, fpsInput].forEach(input => {
            input.addEventListener('input', () => updateValue(input));
            input.addEventListener('change', updateQualitySettings);
        });
        
        [compressionSelect, optimizeModeSelect].forEach(select => {
            select.addEventListener('change', updateQualitySettings);
        });
        
        // 初始化显示值
        [qualityInput, resolutionInput, fpsInput].forEach(updateValue);
    }

    // 在页面加载时初始化
    initQualityControls();

    // 录制控制
    function initRecordingControls() {
        const startBtn = document.getElementById('start-recording');
        const stopBtn = document.getElementById('stop-recording');
        const timeDisplay = document.getElementById('recording-time');
        const indicator = document.getElementById('recording-indicator');
        const sizeDisplay = document.getElementById('recording-size');
        
        let recordingTimer = null;
        let startTime = 0;
        
        function updateRecordingTime() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const hours = Math.floor(elapsed / 3600).toString().padStart(2, '0');
            const minutes = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
            const seconds = (elapsed % 60).toString().padStart(2, '0');
            timeDisplay.textContent = `${hours}:${minutes}:${seconds}`;
        }
        
        function startRecording() {
            socket.emit('start_recording', {}, response => {
                if (response.status === 'success') {
                    startTime = Date.now();
                    recordingTimer = setInterval(updateRecordingTime, 1000);
                    
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    indicator.classList.add('active');
                    
                    // 更新UI状态
                    updateStatus('正在录制');
                } else {
                    showError(response.message || '开始录制失败');
                }
            });
        }
        
        function stopRecording() {
            socket.emit('stop_recording', {}, response => {
                if (response.status === 'success') {
                    clearInterval(recordingTimer);
                    recordingTimer = null;
                    
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                    indicator.classList.remove('active');
                    timeDisplay.textContent = '00:00:00';
                    
                    // 更新UI状态
                    updateStatus('录制已停止');
                } else {
                    showError(response.message || '停止录制失败');
                }
            });
        }
        
        // 监听录制大小更新
        socket.on('recording_size', data => {
            const size = (data.size / (1024 * 1024)).toFixed(1);
            sizeDisplay.textContent = `${size} MB`;
        });
        
        // 绑定事件
        startBtn.addEventListener('click', startRecording);
        stopBtn.addEventListener('click', stopRecording);
    }

    // 在页面加载时初始化
    initRecordingControls();

    // 设置和帮助功能
    function openSettings() {
        const modal = document.getElementById('settings-modal');
        modal.style.display = 'block';
        loadSettings();
    }

    function closeSettings() {
        const modal = document.getElementById('settings-modal');
        modal.style.display = 'none';
    }

    function openHelp() {
        const modal = document.getElementById('help-modal');
        modal.style.display = 'block';
    }

    function closeHelp() {
        const modal = document.getElementById('help-modal');
        modal.style.display = 'none';
    }

    function loadSettings() {
        // 从服务器加载设置
        socket.emit('get_settings', {}, response => {
            if (response.status === 'success') {
                const settings = response.settings;
                
                // 更新UI
                document.getElementById('auto-approve').checked = settings.auto_approve;
                document.getElementById('need-password').checked = settings.need_password;
                document.getElementById('default-password').value = settings.default_password;
                document.getElementById('timeout').value = settings.timeout;
                document.getElementById('reconnect-attempts').value = settings.reconnect_attempts;
                document.getElementById('recording-path').value = settings.recording_path;
                document.getElementById('auto-cleanup').checked = settings.auto_cleanup;
            }
        });
    }

    function saveSettings() {
        // 收集设置
        const settings = {
            auto_approve: document.getElementById('auto-approve').checked,
            need_password: document.getElementById('need-password').checked,
            default_password: document.getElementById('default-password').value,
            timeout: parseInt(document.getElementById('timeout').value),
            reconnect_attempts: parseInt(document.getElementById('reconnect-attempts').value),
            recording_path: document.getElementById('recording-path').value,
            auto_cleanup: document.getElementById('auto-cleanup').checked
        };
        
        // 发送到服务器
        socket.emit('save_settings', settings, response => {
            if (response.status === 'success') {
                showNotification('设置已保存');
                closeSettings();
            } else {
                showError(response.message || '保存设置失败');
            }
        });
    }

    function selectFolder() {
        // 调用系统文件夹选择对话框
        socket.emit('select_folder', {}, response => {
            if (response.status === 'success') {
                document.getElementById('recording-path').value = response.path;
            }
        });
    }

    // 通知函数
    function showNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'notification success';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    function showError(message) {
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    // 关闭模态框的快捷键
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            closeSettings();
            closeHelp();
        }
    });

    // 统计功能 - 暂时禁用图表功能，因为Chart.js库未引入
    function initStats() {
        // 暂时禁用图表功能
        console.log('图表功能已禁用，因为Chart.js库未引入');
        return;
        
        // 创建图表实例
        const charts = {
            cpu: createChart('cpu-chart'),
            memory: createChart('memory-chart'),
            fps: createChart('fps-chart'),
            network: createChart('network-chart')
        };
        
        let updateInterval = 5000;
        let isRealtime = false;
        let updateTimer = null;
        
        function createChart(canvasId) {
            const ctx = document.getElementById(canvasId).getContext('2d');
            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(20).fill(''),
                    datasets: [{
                        data: Array(20).fill(0),
                        borderColor: '#3498db',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: '#bdc3c7'
                            }
                        },
                        x: {
                            display: false
                        }
                    }
                }
            });
        }
        
        function updateCharts(data) {
            // 更新CPU使用率
            charts.cpu.data.datasets[0].data.push(data.cpu);
            charts.cpu.data.datasets[0].data.shift();
            charts.cpu.update('none');
            document.getElementById('cpu-usage').textContent = `${data.cpu}%`;
            
            // 更新内存使用
            charts.memory.data.datasets[0].data.push(data.memory);
            charts.memory.data.datasets[0].data.shift();
            charts.memory.update('none');
            document.getElementById('memory-usage').textContent = 
                `${(data.memory / 1024 / 1024).toFixed(1)} MB`;
            
            // 更新帧率
            charts.fps.data.datasets[0].data.push(data.fps);
            charts.fps.data.datasets[0].data.shift();
            charts.fps.update('none');
            document.getElementById('fps-counter').textContent = `${data.fps} FPS`;
            
            // 更新网络流量
            charts.network.data.datasets[0].data.push(data.network);
            charts.network.data.datasets[0].data.shift();
            charts.network.update('none');
            document.getElementById('network-usage').textContent = 
                `${(data.network / 1024).toFixed(1)} KB/s`;
        }
        
        function updateStats() {
            socket.emit('get_stats', {}, response => {
                if (response.status === 'success') {
                    updateCharts(response.data);
                    updateDetails(response.data);
                }
            });
        }
        
        function updateDetails(data) {
            // 更新连接统计
            document.getElementById('current-connections').textContent = 
                data.connections.current;
            document.getElementById('total-connections').textContent = 
                data.connections.total;
            document.getElementById('rejected-connections').textContent = 
                data.connections.rejected;
            
            // 更新传输统计
            document.getElementById('total-sent').textContent = 
                `${(data.transfer.sent / 1024 / 1024).toFixed(1)} MB`;
            document.getElementById('total-received').textContent = 
                `${(data.transfer.received / 1024 / 1024).toFixed(1)} MB`;
            document.getElementById('average-latency').textContent = 
                `${data.transfer.latency.toFixed(1)} ms`;
        }
        
        // 切换实时更新
        window.toggleRealtime = function() {
            isRealtime = !isRealtime;
            if (isRealtime) {
                updateTimer = setInterval(updateStats, updateInterval);
            } else {
                clearInterval(updateTimer);
            }
        };
        
        // 更新间隔
        window.updateInterval = function() {
            updateInterval = parseInt(document.getElementById('stats-interval').value);
            if (isRealtime) {
                clearInterval(updateTimer);
                updateTimer = setInterval(updateStats, updateInterval);
            }
        };
        
        // 初始更新
        updateStats();
    }

    // 初始化统计功能
    initStats();

    // 处理新的连接请求 - 由HTML中的处理程序处理
    // 处理客户端状态更新 - 由HTML中的处理程序处理

    // 审核操作函数 - 由HTML中的函数处理
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