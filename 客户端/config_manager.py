import configparser
import os

class Config:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file):
                self.create_default_config()
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self.create_default_config()

    def create_default_config(self):
        """创建默认配置"""
        self.config['主端'] = {
            '默认端口': '5000',
            '最大客户端数': '10',
            '图像质量': '80',
            '目标帧率': '60',
            '目标分辨率': '1920x1080'
        }
        self.config['客户端'] = {
            '默认端口': '5001',
            '自动连接': 'true',
            '全屏模式': 'false'
        }
        self.config['网络'] = {
            '超时时间': '10000',
            '重连次数': '5',
            '心跳间隔': '25'
        }
        self.save_config()

    def save_config(self):
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get(self, section, key, fallback=None):
        """获取配置值"""
        try:
            return self.config.get(section, key)
        except:
            return fallback

    def get_int(self, section, key, fallback=0):
        """获取整数配置值"""
        try:
            return self.config.getint(section, key)
        except:
            return fallback

    def get_bool(self, section, key, fallback=False):
        """获取布尔配置值"""
        try:
            return self.config.getboolean(section, key)
        except:
            return fallback

    def get_resolution(self):
        """获取分辨率配置"""
        try:
            res = self.get('主端', '目标分辨率')
            width, height = map(int, res.split('x'))
            return width, height
        except:
            return 1920, 1080

    def set(self, section, key, value):
        """设置配置值"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        self.save_config() 