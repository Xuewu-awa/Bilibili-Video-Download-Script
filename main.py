#!/usr/bin/env python3
"""
Bilibili Video Download Script（bvds）
"""

import requests
import re
import json
import os
import subprocess
import sys
import time
import threading
import uuid
import concurrent.futures
import qrcode
from datetime import datetime

# 配置
CONFIG_FILE = "bilibili_downloader_config.json"
COOKIE_FILE = "bilibili_cookies.json"
DEFAULT_DOWNLOAD_DIR = "./downloads"


QUALITY_MAP = {
    "1": {"code": 120, "name": "4K 超高清", "need_vip": True},
    "2": {"code": 80, "name": "1080P 高清", "need_vip": False},
    "3": {"code": 64, "name": "720P 准高清", "need_vip": False},
    "4": {"code": 32, "name": "480P 清晰", "need_vip": False},
    "5": {"code": 16, "name": "360P 流畅", "need_vip": False},
}

# 配置
def load_config():
    config = {
        "download_dir": DEFAULT_DOWNLOAD_DIR,
        "download_mode": "3",
        "quality": "2"  
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                config.update(saved_config)
    except Exception as e:
        print(f"读取配置文件失败: {e}")
    return config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置文件失败: {e}")

# landing
class BilibiliLogin:
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bilibili.com/'
        })
    
    def load_cookies(self):
        try:
            if os.path.exists(COOKIE_FILE):
                with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    for name, value in cookies.items():
                        self.session.cookies.set(name, value)
                
                if self.check_login():
                    print("✓ 已加载保存的登录状态")
                    return True
                else:
                    print("✗ 保存的登录状态已过期")
                    return False
        except Exception as e:
            print(f"加载cookies失败: {e}")
        return False
    
    def check_login(self):
        try:
            resp = self.session.get('https://api.bilibili.com/x/web-interface/nav', timeout=10)
            data = resp.json()
            if data['code'] == 0 and data['data'].get('isLogin', False):
                username = data['data'].get('uname', '未知用户')
                print(f"✓ 当前登录用户: {username}")
                return True
        except:
            pass
        return False
    
    def save_cookies(self):
        cookies = self.session.cookies.get_dict()
        if cookies:
            with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print("✓ 登录状态已保存")
    
    def get_qrcode(self):
        try:
            resp = self.session.get('https://passport.bilibili.com/x/passport-login/web/qrcode/generate', timeout=10)
            data = resp.json()
            if data['code'] == 0:
                return data['data']['qrcode_key'], data['data']['url']
            return None, None
        except:
            return None, None
    
    def display_qrcode(self, qrcode_url):
        qr = qrcode.QRCode(box_size=2, border=2)
        qr.add_data(qrcode_url)
        print("\n" + "——" * 25)
        print("      请使用B站APP扫码登录")
        print("——" * 25)
        qr.print_ascii(invert=True)
        print("——" * 25)
        print("\n操作步骤：")
        print("1. 打开B站APP")
        print("2. 点击右下角我的")
        print("3. 再点击右上角扫描图标")
        print("4. 扫描上方二维码")
        print("5. 在手机上确认登录")
    
    def poll_login_status(self, qrcode_key):
        print("\n等待扫码...")
        
        while True:
            try:
                resp = self.session.get(
                    f'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}',
                    timeout=10
                )
                data = resp.json()
                
                if data['code'] == 0:
                    inner_code = data['data'].get('code', 0)
                    
                    if inner_code == 0:
                        print("\n✓ 登录成功！")
                        return True
                    elif inner_code == 86038:
                        print("\n✗ 二维码已过期")
                        return False
                    elif inner_code == 86090:
                        print("\r✓ 已扫描，请在手机上确认...", end='', flush=True)
                    elif inner_code == 86101:
                        print("\r 等待...", end='', flush=True)
                
                time.sleep(2)
            except:
                time.sleep(2)
    
    def login(self):
        print("\n" + "——" * 25)
        print("         二维码登录")
        print("——" * 25)
        
        qrcode_key, qrcode_url = self.get_qrcode()
        if not qrcode_key:
            print("✗ 获取二维码失败，请检查网络")
            return False
        
        self.display_qrcode(qrcode_url)
        
        if self.poll_login_status(qrcode_key):
            self.save_cookies()
            return True
        
        return False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return True
    except:
        return False

def clean_filename(filename):
    if not filename:
        return "untitled"
    
    if '《' in filename and '》' in filename:
        match = re.search(r'《([^《》]+)》', filename)
        if match:
            filename = match.group(1)
    
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    
    return cleaned.strip()

def get_real_url(session, url):
    try:
        resp = session.get(url, allow_redirects=True, timeout=10)
        return resp.url
    except:
        return url

def extract_source_id(session, url):
    real_url = get_real_url(session, url)
    
    bv_match = re.search(r'BV[0-9a-zA-Z]{10}', real_url)
    if bv_match:
        return f"BV:{bv_match.group(0)}"
    
    ep_match = re.search(r'ep(\d+)', real_url)
    if ep_match:
        return f"EP:{ep_match.group(1)}"
    
    ss_match = re.search(r'ss(\d+)', real_url)
    if ss_match:
        return f"SS:{ss_match.group(1)}"
    
    return f"URL:{real_url}"

def add_metadata_to_video(video_path, source_id, title):
    try:
        temp_path = video_path.replace('.mp4', '_temp.mp4')
        comment = f"{source_id}|{title}"
        
        cmd = f'ffmpeg -i "{video_path}" -metadata comment="{comment}" -c copy "{temp_path}" -y -hide_banner -loglevel error'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(temp_path):
            os.replace(temp_path, video_path)
            return True
        return False
    except:
        return False

def extract_urls(text):
    urls = []
    parts = re.split(r'[\s,;\n]+', text.strip())
    for part in parts:
        if part and (part.startswith('http://') or part.startswith('https://')):
            urls.append(part)
    return urls

def get_video_info(session, url):
    try:
        response = session.get(url, timeout=10)
        html = response.text
        
        title_match = re.search(r'<title>(.*?)</title>', html)
        if title_match:
            title = title_match.group(1).replace('_哔哩哔哩_bilibili', '').strip()
            return title
        
        return "未知标题"
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        return "未知标题"

def get_video_urls(session, url, quality_code=80):
    try:
        response = session.get(url, timeout=10)
        html = response.text
        
        match = re.search(r'window.__playinfo__=(.*?)</script>', html)
        if match:
            data = json.loads(match.group(1))
            
            if 'data' in data and 'dash' in data['data']:
                videos = data['data']['dash'].get('video', [])
                audios = data['data']['dash'].get('audio', [])
                
                if videos and audios:
                    selected_video = None
                    for video in videos:
                        if video.get('id') == quality_code:
                            selected_video = video
                            break
                    
                    if not selected_video and videos:
                        selected_video = min(videos, key=lambda x: abs(x.get('id', 0) - quality_code))
                    
                    best_audio = max(audios, key=lambda x: x.get('bandwidth', 0))
                    
                    if selected_video:
                        return selected_video.get('baseUrl'), best_audio.get('baseUrl')
        
        return None, None
    except Exception as e:
        print(f"解析视频URL失败: {e}")
        return None, None

def get_pgc_video_urls(session, url, quality_code=80):
    match = re.search(r'ep(\d+)', url)
    if not match:
        return None, None
    
    ep_id = match.group(1)
    
    api_url = "https://api.bilibili.com/pgc/player/web/playurl"
    params = {
        "ep_id": ep_id,
        "qn": quality_code,
        "fnval": 4048,
        "fourk": 1,
    }
    
    try:
        resp = session.get(api_url, params=params, timeout=10)
        data = resp.json()
        
        if data['code'] == 0 and 'result' in data:
            dash = data['result'].get('dash')
            if dash:
                videos = dash.get('video', [])
                audios = dash.get('audio', [])
                
                if videos and audios:
                    best_video = max(videos, key=lambda x: x.get('bandwidth', 0))
                    best_audio = max(audios, key=lambda x: x.get('bandwidth', 0))
                    
                    return best_video.get('baseUrl'), best_audio.get('baseUrl')
        
        return None, None
    except Exception as e:
        print(f"获取番剧URL失败: {e}")
        return None, None

def download_file(session, url, output_path, callback=None):
    try:
        response = session.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if callback and total > 0:
                            callback(downloaded / total * 100)
            return True
        return False
    except Exception as e:
        print(f"下载出错: {e}")
        return False

def merge_video_audio(video_path, audio_path, output_path):
    try:
        cmd = f'ffmpeg -i "{video_path}" -i "{audio_path}" -c:v copy -c:a aac "{output_path}" -y -hide_banner -loglevel error'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
            return True
        return False
    except:
        return False

def convert_to_mp4(input_path, output_path):
    try:
        cmd = f'ffmpeg -i "{input_path}" -c copy "{output_path}" -y -hide_banner -loglevel error'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            if os.path.exists(input_path):
                os.remove(input_path)
            return True
        return False
    except:
        return False

def convert_to_mp3(input_path, output_path):
    try:
        cmd = f'ffmpeg -i "{input_path}" -codec:a libmp3lame -q:a 2 "{output_path}" -y -hide_banner -loglevel error'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            if os.path.exists(input_path):
                os.remove(input_path)
            return True
        return False
    except:
        return False

class ProgressDisplay:
    
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.lock = threading.Lock()
        self.results = []
    
    def update(self, task_id, title, status, progress=None):
        with self.lock:
            short_title = title[:30] + '...' if len(title) > 30 else title
            
            if status == "完成":
                self.completed += 1
                print(f"[{self.completed}/{self.total}] ✓ {short_title} - 完成")
            elif status == "失败":
                print(f"[{self.completed}/{self.total}] ✗ {short_title} - 失败")
            else:
                print(f"[{self.completed}/{self.total}] → {short_title} - {status}")

def download_video(session, url, config, mode, task_id, display):
    temp_files = []
    
    try:
        source_id = extract_source_id(session, url)
        
        title = get_video_info(session, url)
        display.update(task_id, title, "获取信息")
        
        quality_key = config.get("quality", "2")
        quality_code = QUALITY_MAP.get(quality_key, {"code": 80})["code"]
        quality_name = QUALITY_MAP.get(quality_key, {"name": "1080P"})["name"]
        
        display.update(task_id, title, f"清晰度: {quality_name}")
        
        if '/ep' in url or '/bangumi' in url:
            video_url, audio_url = get_pgc_video_urls(session, url, quality_code)
        else:
            video_url, audio_url = get_video_urls(session, url, quality_code)
        
        if not video_url:
            display.update(task_id, title, "失败(无法获取视频链接)")
            return False
        
        unique_id = str(uuid.uuid4())[:8]
        clean_title = clean_filename(title)
        download_dir = config["download_dir"]
        
        os.makedirs(download_dir, exist_ok=True)
        
        if mode == "1":
            output = os.path.join(download_dir, f"{clean_title}.mp4")
            temp = os.path.join(download_dir, f"temp_{unique_id}.m4v")
            temp_files.append(temp)
            
            if download_file(session, video_url, temp, None):
                if check_ffmpeg() and convert_to_mp4(temp, output):
                    add_metadata_to_video(output, source_id, clean_title)
                    display.update(task_id, title, "完成")
                    return True
                else:
                    os.rename(temp, output.replace('.mp4', '.m4v'))
                    add_metadata_to_video(output.replace('.mp4', '.m4v'), source_id, clean_title)
                    display.update(task_id, title, "完成")
                    return True
            else:
                display.update(task_id, title, "失败")
                return False
        
        elif mode == "2":
            output = os.path.join(download_dir, f"{clean_title}.mp3")
            temp = os.path.join(download_dir, f"temp_{unique_id}.m4a")
            temp_files.append(temp)
            
            if download_file(session, audio_url, temp, None):
                if check_ffmpeg() and convert_to_mp3(temp, output):
                    display.update(task_id, title, "完成")
                    return True
                else:
                    os.rename(temp, output.replace('.mp3', '.m4a'))
                    display.update(task_id, title, "完成")
                    return True
            else:
                display.update(task_id, title, "失败")
                return False
        
        elif mode == "3":
            video_temp = os.path.join(download_dir, f"video_{unique_id}.m4v")
            audio_temp = os.path.join(download_dir, f"audio_{unique_id}.m4a")
            output = os.path.join(download_dir, f"{clean_title}.mp4")
            temp_files.extend([video_temp, audio_temp])
            
            display.update(task_id, title, "下载中")
            
            video_ok = download_file(session, video_url, video_temp, None)
            audio_ok = download_file(session, audio_url, audio_temp, None)
            
            if video_ok and audio_ok:
                display.update(task_id, title, "合并中")
                if check_ffmpeg() and merge_video_audio(video_temp, audio_temp, output):
                    add_metadata_to_video(output, source_id, clean_title)
                    display.update(task_id, title, "完成")
                    return True
                else:
                    display.update(task_id, title, "合并失败")
                    return False
            else:
                display.update(task_id, title, "下载失败")
                return False
                
    except Exception as e:
        display.update(task_id, "错误", "失败")
        return False
    finally:
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass

def quality_menu(config):
    clear_screen()
    print("——" * 25)
    print("          清晰度设置")
    print("——" * 25)
    
    current = config.get("quality", "2")
    print(f"\n当前清晰度: {QUALITY_MAP.get(current, {'name': '1080P'})['name']}")
    print("\n可选清晰度：")
    print("  1. 4K 超高清 (需要大会员)")
    print("  2. 1080P 高清")
    print("  3. 720P 准高清")
    print("  4. 480P 清晰")
    print("  5. 360P 流畅")
    print("\n" + ("——" * 15))
    print("0. 返回")
    print(("——" * 15))
    
    choice = input("\n请选择: ").strip()
    
    if choice in QUALITY_MAP:
        config["quality"] = choice
        save_config(config)
        print(f"\n✓ 清晰度已设置为: {QUALITY_MAP[choice]['name']}")
        input("\n按回车继续...")
    elif choice == "0":
        return
    else:
        input("\n无效选择，按回车继续...")

def single_download(session, config):
    clear_screen()
    print("——" * 25)
    print("          单视频下载")
    print("——" * 25)
    
    url = input("\n请输入视频网址: ").strip()
    if not url:
        input("\n网址不能为空，按回车返回...")
        return
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    source_id = extract_source_id(session, url)
    print(f"\n✓ 识别到来源: {source_id}")
    
    print("\n" + ("——" * 15))
    print("下载模式：")
    print("  1. 仅视频 (MP4)")
    print("  2. 仅音频 (MP3)")
    print("  3. 完整视频 (视频+音频)")
    print(("——" * 15))
    
    mode = input("\n请选择 (1-3，默认3): ").strip()
    if mode not in ["1", "2", "3"]:
        mode = "3"
    
    config["download_mode"] = mode
    save_config(config)
    
    quality_name = QUALITY_MAP.get(config.get("quality", "2"), {"name": "1080P"})["name"]
    print(f"\n当前清晰度: {quality_name}")
    change = input("是否修改清晰度？(y/n，默认n): ").strip().lower()
    if change == 'y':
        quality_menu(config)
        quality_name = QUALITY_MAP.get(config.get("quality", "2"), {"name": "1080P"})["name"]
    
    print(f"\n开始下载 (清晰度: {quality_name})...\n")
    display = ProgressDisplay(1)
    result = download_video(session, url, config, mode, 1, display)
    
    if result:
        print(f"\n✓ 下载完成！保存位置: {config['download_dir']}")
    else:
        print("\n✗ 下载失败")
    
    input("\n按回车返回...")

def batch_download(session, config):
    clear_screen()
    print("——" * 25)
    print("          批量下载")
    print("——" * 25)
    print("\n提示：多个URL，用空格、逗号或换行分隔")
    print("-" * 50)
    
    text = input("\n请输入视频网址: ").strip()
    if not text:
        input("\n网址不能为空，按回车返回...")
        return
    
    urls = extract_urls(text)
    if not urls:
        input("\n未找到有效URL，按回车返回...")
        return
    
    print(f"\n找到 {len(urls)} 个视频")
    for i, url in enumerate(urls, 1):
        source_id = extract_source_id(session, url)
        print(f"  {i}. {source_id}")
    
    print("\n" + ("——" * 15))
    print("下载模式：")
    print("  1. 仅视频 (MP4)")
    print("  2. 仅音频 (MP3)")
    print("  3. 完整视频 (视频+音频)")
    print(("——" * 15))
    
    mode = input("\n请选择 (1-3，默认3): ").strip()
    if mode not in ["1", "2", "3"]:
        mode = "3"
    
    quality_name = QUALITY_MAP.get(config.get("quality", "2"), {"name": "1080P"})["name"]
    print(f"\n当前清晰度: {quality_name}")
    change = input("是否修改清晰度？(y/n，默认n): ").strip().lower()
    if change == 'y':
        quality_menu(config)
        quality_name = QUALITY_MAP.get(config.get("quality", "2"), {"name": "1080P"})["name"]
    
    print(f"\n开始下载 {len(urls)} 个视频 (清晰度: {quality_name})...")
    confirm = input("\n确认开始？(y/n): ").strip().lower()
    if confirm != 'y':
        input("已取消，按回车返回...")
        return
    
    print()
    display = ProgressDisplay(len(urls))
    success = 0
    lock = threading.Lock()
    
    def task(url, tid):
        nonlocal success
        if download_video(session, url, config, mode, tid, display):
            with lock:
                success += 1
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(task, url, i) for i, url in enumerate(urls, 1)]
        concurrent.futures.wait(futures)
    
    print(f"\n{'='*50}")
    print(f"下载完成: 成功 {success} / 失败 {len(urls) - success}")
    print(f"{'='*50}")
    input("\n按回车返回...")

def settings_menu(config):
    while True:
        clear_screen()
        print("——" * 25)
        print("          设置")
        print("——" * 25)
        print(f"\n当前下载目录: {config['download_dir']}")
        print(f"当前清晰度: {QUALITY_MAP.get(config.get('quality', '2'), {'name': '1080P'})['name']}")
        print(f"FFmpeg状态: {'✓ 可用' if check_ffmpeg() else '✗ 未安装'}")
        print("\n" + ("——" * 15))
        print("1. 修改下载目录")
        print("2. 修改清晰度")
        print("3. 返回主菜单")
        print(("——" * 15))
        
        choice = input("\n请选择: ").strip()
        
        if choice == "1":
            new_dir = input("新目录: ").strip()
            if new_dir:
                try:
                    os.makedirs(new_dir, exist_ok=True)
                    config["download_dir"] = new_dir
                    save_config(config)
                    print(f"\n✓ 目录已更改为: {new_dir}")
                except Exception as e:
                    print(f"\n✗ 创建目录失败: {e}")
                input("\n按回车继续...")
        elif choice == "2":
            quality_menu(config)
        elif choice == "3":
            break

def download_menu(session, config):
    while True:
        clear_screen()
        print("——" * 25)
        print("          下载")
        print("——" * 25)
        print("\n1. 单视频下载")
        print("2. 批量下载")
        print("3. 返回主菜单")
        print("\n" + "——" * 25)
        
        choice = input("\n请选择: ").strip()
        
        if choice == "1":
            single_download(session, config)
        elif choice == "2":
            batch_download(session, config)
        elif choice == "3":
            break
        else:
            input("无效选择，按回车继续...")

def main_menu(session, config):
    while True:
        clear_screen()
        print("——" * 25)
        print("        B站视频下载器 v2.0")
        print("——" * 25)
        
        print(f"\n下载目录: {config['download_dir']}")
        print(f"清晰度: {QUALITY_MAP.get(config.get('quality', '2'), {'name': '1080P'})['name']}")
        print(f"FFmpeg: {'✓' if check_ffmpeg() else '✗'}")
        
        try:
            resp = session.get('https://api.bilibili.com/x/web-interface/nav')
            data = resp.json()
            if data['code'] == 0 and data['data'].get('isLogin', False):
                print(f"登录: ✓ {data['data'].get('uname', '用户')}")
            else:
                print(f"登录: ✗ 未登录")
        except:
            print(f"登录: ? 未知")
        
        print("\n" + ("——" * 15))
        print("1. 开始下载")
        print("2. 设置")
        print("3. 退出")
        print(("——" * 15))
        
        choice = input("\n请选择: ").strip()
        
        if choice == "1":
            download_menu(session, config)
        elif choice == "2":
            settings_menu(config)
        elif choice == "3":
            clear_screen()
            print("\n再见！\n")
            sys.exit(0)
        else:
            input("无效选择，按回车继续...")

def main():
    config = load_config()
    login_mgr = BilibiliLogin()
    
    clear_screen()
    print("——" * 25)
    print("        B站视频下载器 v2.0")
    print("——" * 25)
    
    if not login_mgr.load_cookies():
        print("\n提示：登录后可下载更高画质视频")
        choice = input("\n是否扫码登录？(y/n，默认n): ").strip().lower()
        if choice == 'y':
            if login_mgr.login():
                print("\n✓ 登录成功！")
            else:
                print("\n✗ 登录失败，将使用游客模式")
            input("\n按回车继续...")
    
    main_menu(login_mgr.session, config)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序出错: {e}")
        input("按回车退出...")