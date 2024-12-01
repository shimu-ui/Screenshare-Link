<div align="center">

# Screenshare Link (SS-Link)

🖥️ 一个强大的多客户端屏幕共享解决方案

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-windows-lightgrey.svg)](https://www.microsoft.com)
[![Author](https://img.shields.io/badge/author-shimu--ui-orange.svg)](https://github.com/shimu-ui)

![SS-Link](docs/logo.png)

</div>

## ✨ 功能特点

- 🖥️ 全屏/窗口投屏
- 👥 多客户端同时观看
- 🔒 客户端审核机制
- ⛔ 黑名单管理
- 📊 实时性能监控
- 🏷️ 自动设备ID分配
- 🔄 自动重连机制
- 🔍 自动发现主端
- 💻 设备名称自动获取

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows 操作系统
- 局域网环境

### 📥 安装步骤

1. 克隆项目到本地

```bash
git clone https://github.com/shimuui/screen-share.git
cd screen-share
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 运行程序

```bash
# 运行主端
python 主端/app.py

# 运行客户端
python 客户端/app.py
```

### 📦 打包部署

直接运行打包脚本:

```bash
build.bat
```

## 💡 使用说明

### 🖥️ 主端
1. 运行主端程序
2. 访问主页面(默认 http://localhost:5000)
3. 选择投屏模式(全屏/窗口)
4. 开始/停止投屏
5. 管理客户端连接

### 💻 客户端
1. 运行客户端程序
2. 自动搜索并连接主端
3. 等待审核通过
4. 接收投屏画面
5. 可切换全屏/窗口模式

## ⚙️ 配置说明

### 主端配置

```ini
[主端]
默认端口 = 5000
最大客户端数 = 10
图像质量 = 80
目标帧率 = 60
目标分辨率 = 1920x1080
需要密码 = false
默认密码 = 123456
自动审核 = true
黑名单启用 = true
```

### 客户端配置

```ini
[主端]
IP地址 = auto  # auto表示自动搜索主端
默认端口 = 5000

[客户端]
默认端口 = 5001
自动连接 = true
全屏模式 = false
设备名称 = auto  # auto表示自动获取主机名

[网络]
超时时间 = 10000
重连次数 = 5
心跳间隔 = 25
```

### 📝 配置详解

#### 主端IP地址
- `auto`: 自动搜索局域网内的主端(推荐)
- `具体IP`: 手动指定主端IP
- `不设置`: 默认使用 127.0.0.1

#### 设备名称
- `auto`: 自动获取主机名(推荐)
- `具体名称`: 手动指定设备名称
- `不设置`: 使用默认编号

## 🛠️ 调试功能

- 📊 实时性能监控
- 🔌 客户端连接状态
- 📝 日志记录
- ⛔ 黑名单管理
- 🏷️ 设备ID管理

## ⚠️ 注意事项

1. 确保主端和客户端在同一局域网
2. 检查防火墙设置
3. 建议使用有线网络
4. 性能取决于网络状况
5. 首次使用建议使用自动配置

## 🔧 技术栈

- Flask - Web框架
- Socket.IO - 实时通信
- OpenCV - 图像处理
- Numba - 性能优化
- PIL - 图像处理
- MSS - 屏幕捕获
- cx_Freeze - 程序打包

## 📦 主要依赖

```txt
flask==2.0.1
flask-socketio==5.1.1
flask-cors==3.0.10
python-socketio==5.3.0
python-engineio==4.3.4
mss==9.0.1
Pillow==10.1.0
opencv-python-headless==4.8.1.78
numpy==1.24.3
pywin32==306
```

## 📚 项目结构

```
汇联/
├── 主端/                # 主端程序
│   ├── app.py          # 主端入口
│   ├── config.ini      # 主端配置
│   ├── static/         # 静态资源
│   └── templates/      # 页面模板
├── 客户端/              # 客户端程序
│   ├── app.py          # 客户端入口
│   ├── config.ini      # 客户端配置
│   ├── static/         # 静态资源
│   └── templates/      # 页面模板
├── docs/               # 文档资源
├── build.bat           # 打包脚本
├── config.ini          # 全局配置
├── requirements.txt    # 依赖清单
├── LICENSE             # 许可证
└── README.md          # 说明文档
```

## 👨‍💻 开发者

- 作者: shimu-ui
- 版本: 1.0.0
- 许可: MIT License

## 📄 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交问题和改进建议！

1. Fork 本仓库
2. 创建新分支: `git checkout -b feature/xxxx`
3. 提交更改: `git commit -am 'Add some feature'`
4. 推送分支: `git push origin feature/xxxx`
5. 提交 Pull Request

## 📞 联系方式

如有问题或建议，请联系作者。

---

<div align="center">

Made with ❤️ by shimu-ui

</div>
