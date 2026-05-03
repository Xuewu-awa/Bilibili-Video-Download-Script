# Bilibili Video Download Script(bvds)
 这是一个B 站视频下载脚本

## 环境依赖

- Python 3.6+
- **FFmpeg（需添加到系统环境变量）**
- **Python 库：requests, qrcode**

## 安装依赖：

```bash
pip install requests qrcode
```

## 说明

- 首次运行可按提示扫码登录（可不登录，登录后可选择更高画质）
- 批量下载时输入url要用空格分隔
- 支持短链
- 可选择清晰度
- 可选择仅下载视频、仅下载音频，或下载完整视频（音频+视频合并）
- 下载文件默认保存在 ./downloads 目录中

## 配置文件

首次运行后会在脚本同目录生成 bilibili_downloader_config.json，可修改默认下载目录、清晰度等。

## 注意事项

- 下载高清或 4K 视频可能需要登录大会员账号
- 请遵守 B 站相关用户协议，本项目仅供学习交流，请勿用于商业或违规用途，使用者自行承担法律责任

## License
MIT
