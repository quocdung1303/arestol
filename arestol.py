#!/usr/bin/env python3
# CTOOL.py -- Phiên bản gộp WebSocket (ARES)
# Yêu cầu: pip install colorama requests websocket-client

import os
import re
import sys
import time
import json
import random
import requests   # <-- THÊM MỚI
import websocket  # <-- THÊM MỚI
import threading  # <-- THÊM MỚI
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# ----------------- Config / Defaults -----------------
CONFIG_FILE = "config.json"
MONITOR_ID = random.randint(100000, 999999)

# [QUAN TRỌNG] TÔI ĐÃ THÊM THẲNG CÁC KEY CỦA BẠN VÀO ĐÂY
DEFAULT_CONFIG = {
    "user_id": "4735716",
    "secret_key": "94621ef380ad5941a816d89904603cb17a81dab2750ba7d9f0e15a6d8dc7012f",
    
    # URL "Cái Tay" (Để đặt cược)
    "url_dat_cuoc": "https://api.escapemaster.net/escape_game/bet",
    
    # URL "Cái Tai" (Để nghe)
    "url_websocket": "wss://api.escapemaster.net/escape_game/ws",
    
    # Origin (Server gốc, RẤT QUAN TRỌNG)
    "origin": "https://escapemaster.net", 

    "webhook": "",
    "send_webhook": False,
    "currency": "BUILD", # Bạn cần kiểm tra lại xem API có cần 'currency' không
    "amount": 10,
    
    # Cài đặt "Não"
    "min_streak_length": 3, # Chờ 3 ván bệt liên tiếp mới theo
    
    "pause_after": 999,
    "pause_len": 0,
    "logic": 1 # Logic giờ sẽ là "Theo Cầu Bệt"
}

# ----------------- Runtime state (Toàn cục) -----------------
# Các biến này sẽ được chia sẻ giữa "Tai" và "Não"
state = {
    "wins": 0,
    "losses": 0,
    "rounds_played": 0, # Số vòng đã cược
    "current_chain": 0,
    "max_chain": 0,
    "profit": 0.0,
    "lich_su_thang": [] # DANH SÁCH CÁC PHÒNG THẮNG GẦN NHẤT
}
# Biến này để lưu config đang chạy
current_config = {}

# ----------------- ARES LOGO (green + yellow) -----------------
LOGO = f"""
{Fore.GREEN}    █████╗ ██████╗ ███████╗███████╗
   ██╔══██╗██╔══██╗██╔════╝██╔════╝
   ███████║██████╔╝█████╗  ███████╗
   ██╔══██║██╔══██╗██╔══╝  ╚════██║
   ██║  ██║██║  ██║███████╗███████║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝
{Fore.YELLOW}               POWERED BY ARES TOOL
{Style.RESET_ALL}
"""

# ----------------- Utilities -----------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # fill missing keys
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.RED + "Lỗi khi lưu config:", e)

# (Hàm parse_link_extract không cần thiết nữa vì bạn đã có key)

# ----------------- UI components -----------------
# (Giữ nguyên print_main_screen, show_link_instructions)
def print_main_screen(cfg):
    clear()
    print(LOGO)
    print(Fore.BLUE + "YouTube".ljust(12) + ":" + Style.RESET_ALL, "https://www.youtube.com/@CTOOL")
    print(Fore.BLUE + "TikTok".ljust(12) + ":" + Style.RESET_ALL, "https://www.tiktok.com/@ctool7929")
    print(Fore.BLUE + "Zalo Group".ljust(12) + ":" + Style.RESET_ALL, "https://zalo.me/g/qowvzu729")
    print(Fore.BLUE + "Telegram".ljust(12) + ":" + Style.RESET_ALL, "https://t.me/+PByWNy8hDxYzYTRl")
    print(Fore.BLUE + "Admin".ljust(12) + ":" + Style.RESET_ALL, "Thành Công\n")
    print(Fore.GREEN + "1. Tool vua thoát hiểm")
    print(Fore.GREEN + "2. Cấu hình tài khoản chạy tool")
    print(Fore.GREEN + "3. Cấu hình webhook")
    print(Fore.GREEN + "4. Bảng giám sát (chạy tool)")
    print(Fore.GREEN + "q. Thoát" + Style.RESET_ALL)
    print("\nNhập : ", end="", flush=True)

# ----------------- Logic "Não" -----------------
def logic_theo_cau_bet(lich_su):
    """
    Logic 1: Theo Cầu Bệt.
    Phân tích lịch sử và trả về TÊN phòng, hoặc "SKIP".
    """
    min_streak = current_config.get("min_streak_length", 3)
    
    print(f"[NÃO]: Đang phân tích lịch sử: {lich_su[-5:]}") # In 5 ván cuối
    
    if len(lich_su) < min_streak:
        print("[NÃO]: Không đủ dữ liệu lịch sử.")
        return "SKIP"

    # Lấy N kết quả gần nhất
    cac_van_gan_nhat = lich_su[-min_streak:]
    
    # Kiểm tra xem tất cả có giống nhau không
    phong_dau_tien = cac_van_gan_nhat[0]
    la_cau_bet = all(ket_qua == phong_dau_tien for ket_qua in cac_van_gan_nhat)

    if la_cau_bet:
        print(f"[NÃO]: PHÁT HIỆN CẦU BỆT! Quyết định cược vào -> {phong_dau_tien}")
        return phong_dau_tien # Tên của phòng đang bệt
    else:
        print("[NÃO]: Không có cầu bệt rõ ràng.")
        return "SKIP"

# ----------------- Logic "Tay" (Hành động thật) -----------------
def place_real_bet(room_id, room_name):
    """
    Hàm này dùng "Tay" (requests) để gửi lệnh đặt cược.
    """
    cfg = current_config # Lấy config đang chạy
    
    # [QUAN TRỌNG] Tạo headers với các key BẠN ĐÃ TÌM THẤY
    headers = {
        'user-id': cfg['user_id'],
        'user-secret-key': cfg['secret_key'],
        'origin': cfg['origin'],
        'User-Agent': 'Mozilla/5.0 ... (Thêm User-Agent của bạn)'
    }
    
    # [QUAN TRỌNG] Tạo payload
    # (TODO: Bạn cần kiểm tra lại xem payload có cần 'currency' không)
    payload = {
        'roomId': room_id, # ID của phòng, ví dụ 1, 2, 3...
        'amount': cfg['amount']
    }
    
    try:
        print(Fore.YELLOW + f"!!! [TAY]: Đang cược {payload['amount']} vào phòng {room_name} (ID: {room_id}) !!!")
        response = requests.post(cfg['url_dat_cuoc'], headers=headers, json=payload)
        
        if response.status_code == 200:
            print(Fore.GREEN + "[TAY]: Đặt cược THÀNH CÔNG.")
            state["rounds_played"] += 1
        else:
            print(Fore.RED + f"[TAY]: LỖI ĐẶT CƯỢC. Server: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(Fore.RED + f"[LỖI API]: Không thể đặt cược: {e}")

# ----------------- Logic "Tai" (WebSocket) -----------------

def on_message(ws, message):
    """
    Đây là "CÁI TAI". Nó Lắng nghe mọi thứ server nói.
    """
    global state
    print(Fore.CYAN + f"\n[TAI]: Nhận được tin nhắn từ server:" + Style.RESET_ALL)
    print(message) # In ra để debug
    
    try:
        data = json.loads(message)
        
        # [TODO] ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT BẠN CẦN CHÚ Ý
        # Tôi đang "ĐOÁN" cấu trúc tin nhắn JSON mà server gửi.
        # Bạn hãy chạy tool và xem tin nhắn thật (ở dòng "print(message)")
        # rồi sửa lại 'data['type']' 'data['winner']' cho đúng.
        
        # --- KỊCH BẢN 1: Server báo KẾT QUẢ VÁN TRƯỚC ---
        # (Tôi đoán tin nhắn có 'type' là 'ROUND_RESULT' hoặc 'winner')
        if 'winner' in data or data.get('type') == 'ROUND_RESULT':
            # (Giả sử data['winner'] là một object: {'name': 'Phòng họp', 'id': 2})
            winning_room = data.get('winner', data) 
            winning_room_name = winning_room.get('name', 'N/A')
            
            print(Fore.GREEN + f"[KẾT QUẢ]: Vòng trước thắng: {winning_room_name}")
            state["lich_su_thang"].append(winning_room_name)
            
            # (Bạn có thể thêm code kiểm tra thắng/thua ở đây)

        # --- KỊCH BẢN 2: Server báo VÒNG MỚI BẮT ĐẦU ---
        # (Tôi đoán tin nhắn có 'type' là 'NEW_ROUND' hoặc 'rooms')
        elif 'rooms' in data or data.get('type') == 'NEW_ROUND':
            print(Fore.CYAN + "[HÀNH ĐỘNG]: Vòng mới bắt đầu, chạy bộ não phân tích...")
            
            # Lấy danh sách phòng từ tin nhắn
            # (Giả sử data['rooms'] là list: [{'id': 1, 'name': 'Nhà kho'}, ...])
            danh_sach_phong_hien_tai = data.get('rooms', [])
            if not danh_sach_phong_hien_tai:
                print(Fore.RED + "Lỗi: Tin nhắn vòng mới không có 'rooms'!")
                return

            # 1. Chạy "Não"
            quyet_dinh = logic_theo_cau_bet(state["lich_su_thang"])
            
            if quyet_dinh != "SKIP":
                # 2. Tìm ID phòng từ TÊN phòng
                room_to_bet = None
                for phong in danh_sach_phong_hien_tai:
                    if phong.get('name') == quyet_dinh:
                        room_to_bet = phong
                        break
                
                if room_to_bet:
                    # 3. Chạy "Tay"
                    place_real_bet(room_to_bet['id'], room_to_bet['name'])
                else:
                    print(f"[LỖI]: Não chọn '{quyet_dinh}' nhưng không tìm thấy phòng này trong danh sách!")
            else:
                print(f">>> QUYẾT ĐỊNH: BỎ QUA (SKIP) VÒNG NÀY <<<")
        
        # In ra bảng trạng thái (nếu cần)
        print(f"Lịch sử thắng: {state['lich_su_thang'][-10:]}")
        print(f"Rounds: {state['rounds_played']} | Thắng: {state['wins']} | Thua: {state['losses']} | Lời: {state['profit']:.2f}")

    except json.JSONDecodeError:
        print(Fore.RED + "[LỖI TAI]: Server gửi tin nhắn không phải JSON.")
    except Exception as e:
        print(Fore.RED + f"[LỖI XỬ LÝ]: {e}")


def on_error(ws, error):
    print(Fore.RED + f"[LỖI WS]: {error}")

def on_close(ws, close_status_code, close_msg):
    print(Fore.YELLOW + "!!! Mất kết nối WebSocket. Đang thử kết nối lại sau 10s...")
    time.sleep(10)
    # Thử chạy lại
    run_monitor(current_config) 

def on_open(ws):
    print(Fore.GREEN + "--- ĐÃ KẾT NỐI VỚI SERVER GAME (WebSocket) ---")
    # (Một số game có thể yêu cầu gửi 1 tin nhắn 'init' ở đây)
    # ws.send(json.dumps({"action": "subscribe"}))

# ----------------- Monitor main loop -----------------
def run_monitor(cfg):
    global current_config, state
    # Lưu config để các hàm khác dùng
    current_config = cfg
    
    # Reset state khi bắt đầu
    state = {key: (0 if isinstance(v, (int, float)) else []) for key, v in state.items()}

    print("--- TOOL TỰ ĐỘNG KHỞI CHẠY (Chế độ WebSocket) ---")
    print(f"Số tiền đặt: {cfg['amount']} {cfg['currency']}")
    print(f"Logic: Theo cầu bệt (chờ {cfg['min_streak_length']} ván)")
    print(f"Kết nối với ID: {cfg['user_id']}")
    
    # [QUAN TRỌNG] Tạo headers cho WebSocket
    # (Giống hệt headers bạn tìm thấy)
    headers = {
        'user-id': cfg['user_id'],
        'user-secret-key': cfg['secret_key'],
        'origin': cfg['origin'],
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36'
    }
    
    # Khởi tạo "Cái Tai"
    ws_app = websocket.WebSocketApp(
        cfg['url_websocket'],
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        header=headers
    )
    
    try:
        # Chạy "Cái Tai" (Nó sẽ chạy mãi mãi, block ở đây)
        # Nó sẽ tự động gọi 'on_message' khi có tin nhắn
        ws_app.run_forever()
    except KeyboardInterrupt:
        ws_app.close()
        print("\n" + Fore.YELLOW + "Đã dừng. Quay lại menu chính." + Style.RESET_ALL)
        time.sleep(0.6)

# ----------------- Configuration flows -----------------
def configure_account_flow(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình tài khoản chạy tool---" + Style.RESET_ALL)
    print(Fore.CYAN + "Các 'chìa khóa' của bạn đã được điền sẵn.")
    print(Fore.CYAN + "Nhấn Enter để bỏ qua nếu không muốn thay đổi.")
    
    # Các câu hỏi, với giá trị mặc định là key của bạn
    cfg["user_id"] = input(Fore.YELLOW + f"Nhập user_id [{cfg['user_id']}]: " + Style.RESET_ALL).strip() or cfg["user_id"]
    cfg["secret_key"] = input(Fore.YELLOW + f"Nhập user_secret_key [{cfg['secret_key'][:10]}...]: " + Style.RESET_ALL).strip() or cfg["secret_key"]
    cfg["url_dat_cuoc"] = input(Fore.YELLOW + f"Nhập URL đặt cược [{cfg['url_dat_cuoc']}]: " + Style.RESET_ALL).strip() or cfg["url_dat_cuoc"]
    cfg["url_websocket"] = input(Fore.YELLOW + f"Nhập URL WebSocket [{cfg['url_websocket']}]: " + Style.RESET_ALL).strip() or cfg["url_websocket"]
    
    print()
    print("1. BUILD\n2. USDT\n3. WORLD")
    while True:
        c = input(Fore.YELLOW + "Chọn loại tiền bạn muốn chơi (1/2/3): " + Style.RESET_ALL).strip()
        if c in ("1","2","3"):
            cfg["currency"] = {"1":"BUILD","2":"USDT","3":"WORLD"}[c]
            break
        else:
            print("Nhập 1/2/3.")
    while True:
        v = input(Fore.YELLOW + f"Nhập số lượng {cfg['currency']} để đặt (vd 10): " + Style.RESET_ALL).strip()
        try:
            val = float(v)
            if val > 0:
                cfg["amount"] = val
                break
        except:
            pass
        print("Nhập số hợp lệ > 0.")
    while True:
        v = input(Fore.YELLOW + "Chờ tối thiểu bao nhiêu ván bệt thì theo (vd 3): " + Style.RESET_ALL).strip()
        try:
            cfg["min_streak_length"] = int(v)
            break
        except:
            print("Nhập số nguyên.")

    print()
    w = input(Fore.YELLOW + "Nhập webhook URL (Enter để bỏ qua): " + Style.RESET_ALL).strip()
    if w:
        cfg["webhook"] = w
        cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    
    save_config(cfg)
    print(Fore.GREEN + "Đã lưu cấu hình vào config.json" + Style.RESET_ALL)
    input("Nhấn Enter để quay lại menu...")

def configure_webhook(cfg):
    # (Giữ nguyên hàm này)
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình webhook---" + Style.RESET_ALL)
    w = input("Webhook URL: ").strip()
    if w:
        cfg["webhook"] = w
    cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print("Đã lưu.")
    input("Nhấn Enter ...")

# ----------------- Main program -----------------
def main():
    cfg = load_config()
    while True:
        print_main_screen(cfg)
        ch = input().strip().lower()
        if ch == "1" or ch == "4": # Gộp 1 và 4
            run_monitor(cfg)
        elif ch == "2":
            configure_account_flow(cfg)
        elif ch == "3":
            configure_webhook(cfg)
        elif ch in ("q","quit","exit"):
            print("Bye.")
            break
        else:
            print("Nhập 1/2/3/4 hoặc q.")
            time.sleep(0.6)
        clear()

if __name__ == "__main__":
    try:
        print("Vui lòng cài đặt thư viện nếu chưa có:")
        print(Fore.YELLOW + "pip install requests websocket-client")
        print(Style.RESET_ALL)
        main()
    except KeyboardInterrupt:
        print("\nThoát chương trình.")
    "pause_len": 1,
    "logic": 1,
    "auto_start_monitor": False,
    "bet_threshold": 4 # Ngưỡng cầu bệt
}

ROOM_NAMES = [
    "Nhà kho", "Phòng họp", "Phòng Giám đốc", "Phòng trò chuyện",
    "Phòng Giám sát", "Văn phòng", "Phòng Tài Vụ", "Phòng Nhân sự"
]

# ----------------- ARES LOGO (green + yellow) -----------------
LOGO = f"""
{Fore.GREEN}    █████╗ ██████╗ ███████╗███████╗
   ██╔══██╗██╔══██╗██╔════╝██╔════╝
   ███████║██████╔╝█████╗  ███████╗
   ██╔══██║██╔══██╗██╔══╝  ╚════██║
   ██║  ██║██║  ██║███████╗███████║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝
{Fore.YELLOW}               POWERED BY ARES TOOL
{Style.RESET_ALL}
"""

# ----------------- LỚP PHÂN TÍCH LOGIC CẦU -----------------
class GameAnalyzer:
    def __init__(self, bet_threshold=4, history_size=20):
        self.BET_THRESHOLD = bet_threshold 
        self.history = deque(maxlen=history_size)
        self.current_streak_result = None
        self.current_streak_count = 0
        print(f"[Analyzer]: Sẵn sàng! Phát hiện 'Cầu Bệt' >= {self.BET_THRESHOLD} ván.")

    def add_result(self, result):
        if not result:
            return
        self.history.append(result)
        print(f"[Analyzer]: Nhận kết quả: {result}. Lịch sử: {list(self.history)}")
        self.check_bet_streak(result)
        self.check_1_1_pattern()

    def check_bet_streak(self, result):
        if result == self.current_streak_result:
            self.current_streak_count += 1
        else:
            self.current_streak_result = result
            self.current_streak_count = 1
            
        if self.current_streak_count == self.BET_THRESHOLD:
            print("\n" + Fore.RED + "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(f"!!! CẦU BỆT: Đang bệt {self.current_streak_result}, {self.current_streak_count} ván!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n" + Style.RESET_ALL)
        elif self.current_streak_count > self.BET_THRESHOLD:
            print(Fore.RED + f"--- (Tiếp tục bệt {self.current_streak_result}: {self.current_streak_count} ván) ---" + Style.RESET_ALL)

    def check_1_1_pattern(self):
        if len(self.history) < 4:
            return
        last_4 = list(self.history)[-4:]
        if (last_4[0] == last_4[2] and 
            last_4[1] == last_4[3] and 
            last_4[0] != last_4[1]):
            print("\n" + Fore.CYAN + "*****************************************")
            print(f"!!! CẦU 1-1: Phát hiện {last_4[0]}-{last_4[1]} (ít nhất 4 ván)")
            print("*****************************************\n" + Style.RESET_ALL)

# ----------------- Runtime state -----------------
state = {
    "chosen_room": None,
    "placed_amount": 0.0,
    "wins": 0,
    "losses": 0,
    "rounds": 0,
    "current_chain": 0,
    "max_chain": 0,
    "profit": 0.0,
    "sending": False,
    "current_rooms": [] # Lưu danh sách phòng thật
}

# ----------------- Utilities -----------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.RED + "Lỗi khi lưu config:", e)

def parse_link_extract(link: str):
    uid = None
    skey = None
    m_uid = re.search(r"userId=([0-9]+)", link)
    if m_uid:
        uid = m_uid.group(1)
    m_key = re.search(r"secretKey=([0-9a-fA-F]+)", link)
    if m_key:
        skey = m_key.group(1)
    if not skey:
        m = re.search(r"([0-9a-f]{20,})", link, re.IGNORECASE)
        if m:
            skey = m.group(1)
    return uid, skey

# ----------------- UI components -----------------
def print_main_screen(cfg):
    clear()
    print(LOGO)
    print(Fore.BLUE + "YouTube".ljust(12) + ":" + Style.RESET_ALL, "https://www.youtube.com/@CTOOL")
    print(Fore.BLUE + "TikTok".ljust(12) + ":" + Style.RESET_ALL, "https://www.tiktok.com/@ctool7929")
    print(Fore.BLUE + "Zalo Group".ljust(12) + ":" + Style.RESET_ALL, "https://zalo.me/g/qowvzu729")
    print(Fore.BLUE + "Telegram".ljust(12) + ":" + Style.RESET_ALL, "https://t.me/+PByWNy8hDxYzYTRl")
    print(Fore.BLUE + "Admin".ljust(12) + ":" + Style.RESET_ALL, "Thành Công\n")
    print(Fore.GREEN + "1. Tool vua thoát hiểm")
    print(Fore.GREEN + "2. Cấu hình tài khoản chạy tool")
    print(Fore.GREEN + "3. Cấu hình webhook")
    print(Fore.GREEN + "4. Bảng giám sát (chạy tool)")
    print(Fore.GREEN + "q. Thoát" + Style.RESET_ALL)
    print("\nNhập : ", end="", flush=True)

def show_link_instructions():
    print(Fore.YELLOW + "Hướng dẫn lấy link:" + Style.RESET_ALL)
    print(" 0. Mở chrome")
    print(" 1. Truy cập website xworld.io")
    print(" 2. Đăng nhập vào tài khoản")
    print(" 3. Tìm và nhấp vào Vua thoát hiểm")
    print(" 4. Nhấn lập tức truy cập")
    print(" 5. Sao chép link website và dán vào đây\n")

# ----------------- Logic to choose room -----------------
def choose_room_by_logic(rooms, logic):
    # rooms giờ là danh sách thật từ server
    if not rooms:
        return None
        
    if logic == 1:
        return random.choice(rooms)
    if logic == 2:
        return rooms[0]
    if logic == 3: # Giả sử rooms có 'money'
        return max(rooms, key=lambda r: r.get("money", 0))
    if logic == 4: # Giả sử rooms có 'money'
        return min(rooms, key=lambda r: r.get("money", 0))
    # fallback: random
    return random.choice(rooms)

# ----------------- Monitor / UI table -----------------
def print_table(rooms, cfg):
    # Hàm này bây giờ dùng state["current_rooms"]
    print(Fore.CYAN + f"CTOOL-Bảng giám sát (Connecting...)" + Style.RESET_ALL)
    print("-" * 74)
    print("┌────┬──────────────────────┬──────────┬────────────┬──────────────────────────────┐")
    print("│ STT│ Phòng                │ Số người │ Số tiền    │ THÔNG TIN                   │")
    print("├────┼──────────────────────┼──────────┼────────────┼──────────────────────────────┤")
    
    if not rooms:
        print(f"│ {''.ljust(72)} │")
        print(f"│ {Fore.YELLOW}{'Đang chờ dữ liệu phòng từ WebSocket...'.center(72)}{Style.RESET_ALL} │")
        
    for r in rooms:
        # PHẢI SỬA: Thay 'stt', 'name', 'people', 'money' bằng key thật
        stt = str(r.get("stt", r.get("id", "?"))).rjust(2)
        name = str(r.get("name", "N/A"))[:20].ljust(20)
        people = str(r.get("people", 0)).rjust(8)
        money = f"{r.get('money', 0):,.2f}".rjust(10)
        
        chosen = (state["chosen_room"] is not None and state["chosen_room"].get("id") == r.get("id"))
        
        info_lines = []
        info_lines.append(f"LOGIC:{cfg['logic']}")
        if chosen:
            info_lines.append(f"Phòng đã vào:{stt}")
            info_lines.append(f"Đã đặt:{int(state['placed_amount']) if cfg['currency']=='BUILD' else state['placed_amount']}")
            info_lines.append(f"Trận thắng:{state['wins']}/{state['rounds']}")
            info_lines.append(f"Chuỗi:{state['current_chain']}")
            info_lines.append(f"Max:{state['max_chain']}")
            info_lines.append(f"Lời:{state['profit']:.2f}")
            info_lines.append(f"Wb:{state['sending']}")
        info = "; ".join(info_lines)
        if len(info) > 26:
            info = info[:26] + "…"
        print(f"│ {stt} │ {name} │ {people} │ {money} │ {Fore.CYAN}{info.ljust(26)}{Style.RESET_ALL} │")
    
    print("└────┴──────────────────────┴──────────┴────────────┴──────────────────────────────┘")
    print()
    print(Fore.GREEN + "---Cấu hình của bạn---" + Style.RESET_ALL)
    print(f"Loại tiền: {cfg['currency']}")
    print(f"Số {cfg['currency']} đặt cho mỗi ván: {cfg['amount']}")
    print(f"Hệ số: {cfg['multiplier']}")
    print(f"Logic: {cfg['logic']}")
    print(f"Sau khi chơi {cfg['pause_after']} thì nghỉ {cfg['pause_len']} ván")
    print("-" * 74)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  Rounds:{state['rounds']}  Wins:{state['wins']}  Losses:{state['losses']}  Profit:{state['profit']:.2f} {cfg['currency']}")

# ----------------- PHẦN CHẠY THẬT (WEBSOCKET) -----------------

def listen_for_quit(stop_event: asyncio.Event):
    """
    (Hàm này chạy ở luồng phụ)
    Chờ người dùng nhập 'q' để dừng.
    """
    print(Fore.CYAN + "\n[CONTROL]: Nhấn 'q' rồi Enter bất cứ lúc nào để DỪNG và quay về menu." + Style.RESET_ALL)
    try:
        # Chờ input() ở luồng này (không ảnh hưởng asyncio)
        key = input() 
        if key.strip().lower() == 'q':
            if not stop_event.is_set():
                print(Fore.YELLOW + "[CONTROL]: Đã nhận 'q', đang yêu cầu dừng..." + Style.RESET_ALL)
                # Đặt tín hiệu để báo cho luồng async
                stop_event.set()
    except EOFError:
        # Xảy ra khi chương trình bị ngắt đột ngột
        pass 

async def websocket_receiver(websocket, cfg, analyzer):
    """
    (Hàm Async) Chỉ làm nhiệm vụ nhận và xử lý tin nhắn.
    """
    async for message in websocket:
        try:
            data = json.loads(message)
            
            # In ra để debug (bạn có thể tắt sau)
            print(Fore.MAGENTA + f"[RECV]: {json.dumps(data, indent=2)}" + Style.RESET_ALL)
            
            # ----------------------------------------------------
            # === !!! PHẦN BẠN CẦN SỬA (QUAN TRỌNG) !!! ===
            # ----------------------------------------------------
            # (Logic ví dụ của bạn đến đây)

            # VÍ DỤ: Nếu nhận được danh sách phòng
            # if data.get('type') == 'room_list':
            #    state["current_rooms"] = data.get('rooms', [])
            #    
            #    # Chọn phòng theo logic
            #    chosen_room = choose_room_by_logic(state["current_rooms"], cfg['logic'])
            #    if chosen_room:
            #        state["chosen_room"] = chosen_room
            #        
            #        # Gửi tin nhắn đặt cược
            #        bet_payload = { ... }
            #        await websocket.send(json.dumps(bet_payload))
            #        ...

            # VÍ DỤ: Nếu nhận được kết quả ván
            # if data.get('type') == 'game_result':
            #    ... (Cập nhật state, profit, wins, losses) ...
            #    
            #    # Lấy kết quả (VÍ DỤ: "Tài", "Xỉu")
            #    result_value = data.get('result_name') 
            #    analyzer.add_result(result_value)
            #
            #    # Yêu cầu danh sách phòng cho ván mới
            #    await asyncio.sleep(1) # Chờ 1s
            #    await websocket.send(json.dumps({"type": "get_rooms"}))

            # Cập nhật giao diện (vẽ lại bảng)
            clear()
            print(LOGO)
            print_table(state["current_rooms"], cfg)


        except json.JSONDecodeError:
            print(f"\n[Server-Text]: {message}")
        except Exception as e:
            print(f"Lỗi khi xử lý tin nhắn: {e}")

async def websocket_main_loop(cfg, stop_event: asyncio.Event):
    """
    (Hàm Async) Vòng lặp chính, quản lý kết nối,
    chạy bộ lắng nghe (receiver) và bộ dừng (stop listener).
    """
    analyzer = GameAnalyzer(bet_threshold=cfg.get("bet_threshold", 4))
    
    URI = "wss://escapemaster.net/" # CÓ THỂ CẦN THÊM PATH
    HEADERS = {
        "Origin": "https://escapemaster.net",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
        "X-User-ID": cfg.get("user_id", ""),
        "X-Secret-Key": cfg.get("secret_key", "")
    }
    
    # Khởi động luồng nghe phím 'q'
    # Phải dùng 'asyncio.to_thread' (Python 3.9+) hoặc 'run_in_executor'
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, listen_for_quit, stop_event)
    
    # Vòng lặp tự động kết nối lại, CHỈ DỪNG khi có tín hiệu 'q'
    while not stop_event.is_set():
        try:
            clear()
            print(LOGO)
            print_table(state["current_rooms"], cfg)
            print(Fore.YELLOW + f"Đang kết nối tới {URI} với UserID: {cfg.get('user_id')}" + Style.RESET_ALL)
            
            async with websockets.connect(
                URI, 
                extra_headers=HEADERS,
                ping_interval=20,
                ping_timeout=20
            ) as websocket:
                
                print(Fore.GREEN + "\n=== KẾT NỐI THÀNH CÔNG! ===" + Style.RESET_ALL)
                
                # TODO: Gửi tin nhắn xác thực (nếu cần)
                
                # TODO: Gửi tin nhắn yêu cầu danh sách phòng
                
                # Chạy 2 tác vụ song song:
                # 1. recv_task: Nhận tin nhắn từ server
                # 2. stop_task: Chờ tín hiệu 'q'
                
                recv_task = asyncio.create_task(
                    websocket_receiver(websocket, cfg, analyzer)
                )
                stop_task = asyncio.create_task(stop_event.wait())
                
                # Chờ 1 trong 2 tác vụ hoàn thành
                done, pending = await asyncio.wait(
                    [recv_task, stop_task], 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Hủy các tác vụ còn lại
                for task in pending:
                    task.cancel()

                if stop_task in done:
                    # Nếu 'q' được nhấn, thoát vòng lặp kết nối
                    print(Fore.YELLOW + "Đã nhận tín hiệu dừng, ngắt kết nối..." + Style.RESET_ALL)
                    break 
                
                # Nếu recv_task_done (tức là websocket bị ngắt kết nối),
                # vòng lặp 'while' sẽ tự động chạy lại để kết nối lại.

        except websockets.exceptions.ConnectionClosedError as e:
            if stop_event.is_set(): break
            print(Fore.RED + f"LỖI: Mất kết nối (Code: {e.code}). Thử lại sau 5s..." + Style.RESET_ALL)
            await asyncio.sleep(5)
        except Exception as e:
            if stop_event.is_set(): break
            print(Fore.RED + f"Lỗi không xác định: {e}. Thử lại sau 5s..." + Style.RESET_ALL)
            await asyncio.sleep(5)
    
    print("Đã dừng Bảng Giám Sát.")


# ----------------- Monitor main loop (ĐÃ SỬA) -----------------
def run_monitor(cfg):
    # Tạo tín hiệu DỪNG
    stop_event = asyncio.Event()
    
    try:
        # Chạy vòng lặp async
        asyncio.run(websocket_main_loop(cfg, stop_event))
    except KeyboardInterrupt:
        # Xử lý Ctrl+C (fallback)
        print("\n" + Fore.YELLOW + "Đã dừng (Ctrl+C). Quay lại menu chính." + Style.RESET_ALL)
        time.sleep(0.6)

# ----------------- Configuration flows (GIỮ NGUYÊN) -----------------
def configure_account_flow(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình tài khoản chạy tool---" + Style.RESET_ALL)
    print()
    show_link_instructions()
    link = input(Fore.YELLOW + "📋 Nhập liên kết của bạn (paste link Vua thoát hiểm): " + Style.RESET_ALL).strip()
    if link:
        uid, skey = parse_link_extract(link)
        if uid:
            cfg["user_id"] = uid
            print(Fore.GREEN + "Your user id is" + Style.RESET_ALL, uid)
        else:
            print(Fore.YELLOW + "Không tìm thấy userId trong link.")
        if skey:
            cfg["secret_key"] = skey
            print(Fore.GREEN + "Your user secret key is" + Style.RESET_ALL, skey[:40] + "...")
        else:
            print(Fore.YELLOW + "Không tìm thấy secretKey trong link.")
    else:
        uid = input("Nhập user id (hoặc Enter để bỏ qua): ").strip()
        if uid:
            cfg["user_id"] = uid
        sk = input("Nhập secret key (hoặc Enter để bỏ qua): ").strip()
        if sk:
            cfg["secret_key"] = sk

    print()
    print("1. BUILD\n2. USDT\n3. WORLD")
    while True:
        c = input(Fore.YELLOW + "Chọn loại tiền bạn muốn chơi (1/2/3): " + Style.RESET_ALL).strip()
        if c in ("1","2","3"):
            cfg["currency"] = {"1":"BUILD","2":"USDT","3":"WORLD"}[c]
            break
        else:
            print("Nhập 1/2/3.")
    while True:
        v = input(Fore.YELLOW + f"Nhập số lượng {cfg['currency']} để đặt (vd 10): " + Style.RESET_ALL).strip()
        try:
            val = float(v)
            if val > 0:
                cfg["amount"] = val
                break
        except:
            pass
        print("Nhập số hợp lệ > 0.")
    while True:
        v = input(Fore.YELLOW + "Nhập hệ số cược sau khi thua (vd 1): " + Style.RESET_ALL).strip()
        try:
            cfg["multiplier"] = float(v)
            break
        except:
            print("Nhập số hợp lệ.")
    while True:
        v = input(Fore.YELLOW + "Sau bao nhiêu ván thì tạm nghỉ (999 nếu không muốn tạm nghỉ): " + Style.RESET_ALL).strip()
        try:
            cfg["pause_after"] = int(v)
            break
        except:
            print("Nhập số nguyên.")
    while True:
        v = input(Fore.YELLOW + "Sau đó tạm nghỉ bao nhiêu ván (0 nếu không muốn nghỉ): " + Style.RESET_ALL).strip()
        try:
            cfg["pause_len"] = int(v)
            break
        except:
            print("Nhập số nguyên.")
    print()
    print(Fore.GREEN + "Chọn Logic (1..4). 1=Random, 2=Phòng đầu, 3=Nhiều tiền, 4=Ít tiền" + Style.RESET_ALL)
    while True:
        v = input(Fore.YELLOW + "Nhập STT logic cần dùng: " + Style.RESET_ALL).strip()
        if v.isdigit() and 1 <= int(v) <= 4: # Sửa logic
            cfg["logic"] = int(v)
            break
        else:
            print("Nhập 1..4.")
    print()
    w = input(Fore.YELLOW + "Nhập webhook URL (Enter để bỏ qua): " + Style.RESET_ALL).strip()
    if w:
        cfg["webhook"] = w
        cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print(Fore.GREEN + "Đã lưu cấu hình vào config.json" + Style.RESET_ALL)
    input("Nhấn Enter để quay lại menu...")

def configure_webhook(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình webhook---" + Style.RESET_ALL)
    w = input("Webhook URL: ").strip()
    if w:
        cfg["webhook"] = w
    cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print("Đã lưu.")
    input("Nhấn Enter ...")

# ----------------- Main program (GIỮ NGUYÊN) -----------------
def main():
    cfg = load_config()
    while True:
        print_main_screen(cfg)
        ch = input().strip().lower()
        if ch == "1":
            print("\n>> Loading..\n")
            time.sleep(0.4)
            # input("Nhấn Enter để bắt đầu giám sát (Ctrl-C để dừng)...") # Bỏ dòng này
            run_monitor(cfg)
        elif ch == "2":
            configure_account_flow(cfg)
        elif ch == "3":
            configure_webhook(cfg)
        elif ch == "4":
            run_monitor    "pause_len": 1,
    "logic": 1,
    "auto_start_monitor": False,
    "bet_threshold": 4 # Ngưỡng cầu bệt
}

ROOM_NAMES = [
    "Nhà kho", "Phòng họp", "Phòng Giám đốc", "Phòng trò chuyện",
    "Phòng Giám sát", "Văn phòng", "Phòng Tài Vụ", "Phòng Nhân sự"
]

# ----------------- ARES LOGO (green + yellow) -----------------
LOGO = f"""
{Fore.GREEN}    █████╗ ██████╗ ███████╗███████╗
   ██╔══██╗██╔══██╗██╔════╝██╔════╝
   ███████║██████╔╝█████╗  ███████╗
   ██╔══██║██╔══██╗██╔══╝  ╚════██║
   ██║  ██║██║  ██║███████╗███████║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝
{Fore.YELLOW}               POWERED BY ARES TOOL
{Style.RESET_ALL}
"""

# ----------------- LỚP PHÂN TÍCH LOGIC CẦU -----------------
class GameAnalyzer:
    def __init__(self, bet_threshold=4, history_size=20):
        self.BET_THRESHOLD = bet_threshold 
        self.history = deque(maxlen=history_size)
        self.current_streak_result = None
        self.current_streak_count = 0
        print(f"[Analyzer]: Sẵn sàng! Phát hiện 'Cầu Bệt' >= {self.BET_THRESHOLD} ván.")

    def add_result(self, result):
        if not result:
            return
        self.history.append(result)
        print(f"[Analyzer]: Nhận kết quả: {result}. Lịch sử: {list(self.history)}")
        self.check_bet_streak(result)
        self.check_1_1_pattern()

    def check_bet_streak(self, result):
        if result == self.current_streak_result:
            self.current_streak_count += 1
        else:
            self.current_streak_result = result
            self.current_streak_count = 1
            
        if self.current_streak_count == self.BET_THRESHOLD:
            print("\n" + Fore.RED + "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(f"!!! CẦU BỆT: Đang bệt {self.current_streak_result}, {self.current_streak_count} ván!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n" + Style.RESET_ALL)
        elif self.current_streak_count > self.BET_THRESHOLD:
            print(Fore.RED + f"--- (Tiếp tục bệt {self.current_streak_result}: {self.current_streak_count} ván) ---" + Style.RESET_ALL)

    def check_1_1_pattern(self):
        if len(self.history) < 4:
            return
        last_4 = list(self.history)[-4:]
        if (last_4[0] == last_4[2] and 
            last_4[1] == last_4[3] and 
            last_4[0] != last_4[1]):
            print("\n" + Fore.CYAN + "*****************************************")
            print(f"!!! CẦU 1-1: Phát hiện {last_4[0]}-{last_4[1]} (ít nhất 4 ván)")
            print("*****************************************\n" + Style.RESET_ALL)

# ----------------- Runtime state -----------------
state = {
    "chosen_room": None,
    "placed_amount": 0.0,
    "wins": 0,
    "losses": 0,
    "rounds": 0,
    "current_chain": 0,
    "max_chain": 0,
    "profit": 0.0,
    "sending": False,
    "current_rooms": [] # Lưu danh sách phòng thật
}

# ----------------- Utilities -----------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.RED + "Lỗi khi lưu config:", e)

def parse_link_extract(link: str):
    uid = None
    skey = None
    m_uid = re.search(r"userId=([0-9]+)", link)
    if m_uid:
        uid = m_uid.group(1)
    m_key = re.search(r"secretKey=([0-9a-fA-F]+)", link)
    if m_key:
        skey = m_key.group(1)
    if not skey:
        m = re.search(r"([0-9a-f]{20,})", link, re.IGNORECASE)
        if m:
            skey = m.group(1)
    return uid, skey

# ----------------- UI components -----------------
def print_main_screen(cfg):
    clear()
    print(LOGO)
    print(Fore.BLUE + "YouTube".ljust(12) + ":" + Style.RESET_ALL, "https://www.youtube.com/@CTOOL")
    print(Fore.BLUE + "TikTok".ljust(12) + ":" + Style.RESET_ALL, "https://www.tiktok.com/@ctool7929")
    print(Fore.BLUE + "Zalo Group".ljust(12) + ":" + Style.RESET_ALL, "https://zalo.me/g/qowvzu729")
    print(Fore.BLUE + "Telegram".ljust(12) + ":" + Style.RESET_ALL, "https://t.me/+PByWNy8hDxYzYTRl")
    print(Fore.BLUE + "Admin".ljust(12) + ":" + Style.RESET_ALL, "Thành Công\n")
    print(Fore.GREEN + "1. Tool vua thoát hiểm")
    print(Fore.GREEN + "2. Cấu hình tài khoản chạy tool")
    print(Fore.GREEN + "3. Cấu hình webhook")
    print(Fore.GREEN + "4. Bảng giám sát (chạy tool)")
    print(Fore.GREEN + "q. Thoát" + Style.RESET_ALL)
    print("\nNhập : ", end="", flush=True)

def show_link_instructions():
    print(Fore.YELLOW + "Hướng dẫn lấy link:" + Style.RESET_ALL)
    print(" 0. Mở chrome")
    print(" 1. Truy cập website xworld.io")
    print(" 2. Đăng nhập vào tài khoản")
    print(" 3. Tìm và nhấp vào Vua thoát hiểm")
    print(" 4. Nhấn lập tức truy cập")
    print(" 5. Sao chép link website và dán vào đây\n")

# ----------------- Logic to choose room -----------------
def choose_room_by_logic(rooms, logic):
    # rooms giờ là danh sách thật từ server
    if not rooms:
        return None
        
    if logic == 1:
        return random.choice(rooms)
    if logic == 2:
        return rooms[0]
    if logic == 3: # Giả sử rooms có 'money'
        return max(rooms, key=lambda r: r.get("money", 0))
    if logic == 4: # Giả sử rooms có 'money'
        return min(rooms, key=lambda r: r.get("money", 0))
    # fallback: random
    return random.choice(rooms)

# ----------------- Monitor / UI table -----------------
def print_table(rooms, cfg):
    # Hàm này bây giờ dùng state["current_rooms"]
    print(Fore.CYAN + f"CTOOL-Bảng giám sát (Connecting...)" + Style.RESET_ALL)
    print("-" * 74)
    print("┌────┬──────────────────────┬──────────┬────────────┬──────────────────────────────┐")
    print("│ STT│ Phòng                │ Số người │ Số tiền    │ THÔNG TIN                   │")
    print("├────┼──────────────────────┼──────────┼────────────┼──────────────────────────────┤")
    
    if not rooms:
        print(f"│ {''.ljust(72)} │")
        print(f"│ {Fore.YELLOW}{'Đang chờ dữ liệu phòng từ WebSocket...'.center(72)}{Style.RESET_ALL} │")
        
    for r in rooms:
        # PHẢI SỬA: Thay 'stt', 'name', 'people', 'money' bằng key thật
        stt = str(r.get("stt", r.get("id", "?"))).rjust(2)
        name = str(r.get("name", "N/A"))[:20].ljust(20)
        people = str(r.get("people", 0)).rjust(8)
        money = f"{r.get('money', 0):,.2f}".rjust(10)
        
        chosen = (state["chosen_room"] is not None and state["chosen_room"].get("id") == r.get("id"))
        
        info_lines = []
        info_lines.append(f"LOGIC:{cfg['logic']}")
        if chosen:
            info_lines.append(f"Phòng đã vào:{stt}")
            info_lines.append(f"Đã đặt:{int(state['placed_amount']) if cfg['currency']=='BUILD' else state['placed_amount']}")
            info_lines.append(f"Trận thắng:{state['wins']}/{state['rounds']}")
            info_lines.append(f"Chuỗi:{state['current_chain']}")
            info_lines.append(f"Max:{state['max_chain']}")
            info_lines.append(f"Lời:{state['profit']:.2f}")
            info_lines.append(f"Wb:{state['sending']}")
        info = "; ".join(info_lines)
        if len(info) > 26:
            info = info[:26] + "…"
        print(f"│ {stt} │ {name} │ {people} │ {money} │ {Fore.CYAN}{info.ljust(26)}{Style.RESET_ALL} │")
    
    print("└────┴──────────────────────┴──────────┴────────────┴──────────────────────────────┘")
    print()
    print(Fore.GREEN + "---Cấu hình của bạn---" + Style.RESET_ALL)
    print(f"Loại tiền: {cfg['currency']}")
    print(f"Số {cfg['currency']} đặt cho mỗi ván: {cfg['amount']}")
    print(f"Hệ số: {cfg['multiplier']}")
    print(f"Logic: {cfg['logic']}")
    print(f"Sau khi chơi {cfg['pause_after']} thì nghỉ {cfg['pause_len']} ván")
    print("-" * 74)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  Rounds:{state['rounds']}  Wins:{state['wins']}  Losses:{state['losses']}  Profit:{state['profit']:.2f} {cfg['currency']}")

# ----------------- PHẦN CHẠY THẬT (WEBSOCKET) -----------------

def listen_for_quit(stop_event: asyncio.Event):
    """
    (Hàm này chạy ở luồng phụ)
    Chờ người dùng nhập 'q' để dừng.
    """
    print(Fore.CYAN + "\n[CONTROL]: Nhấn 'q' rồi Enter bất cứ lúc nào để DỪNG và quay về menu." + Style.RESET_ALL)
    try:
        # Chờ input() ở luồng này (không ảnh hưởng asyncio)
        key = input() 
        if key.strip().lower() == 'q':
            if not stop_event.is_set():
                print(Fore.YELLOW + "[CONTROL]: Đã nhận 'q', đang yêu cầu dừng..." + Style.RESET_ALL)
                # Đặt tín hiệu để báo cho luồng async
                stop_event.set()
    except EOFError:
        # Xảy ra khi chương trình bị ngắt đột ngột
        pass 

async def websocket_receiver(websocket, cfg, analyzer):
    """
    (Hàm Async) Chỉ làm nhiệm vụ nhận và xử lý tin nhắn.
    """
    async for message in websocket:
        try:
            data = json.loads(message)
            
            # In ra để debug (bạn có thể tắt sau)
            print(Fore.MAGENTA + f"[RECV]: {json.dumps(data, indent=2)}" + Style.RESET_ALL)
            
            # ----------------------------------------------------
            # === !!! PHẦN BẠN CẦN SỬA (QUAN TRỌNG) !!! ===
            # ----------------------------------------------------
            # (Logic ví dụ của bạn đến đây)

            # VÍ DỤ: Nếu nhận được danh sách phòng
            # if data.get('type') == 'room_list':
            #    state["current_rooms"] = data.get('rooms', [])
            #    
            #    # Chọn phòng theo logic
            #    chosen_room = choose_room_by_logic(state["current_rooms"], cfg['logic'])
            #    if chosen_room:
            #        state["chosen_room"] = chosen_room
            #        
            #        # Gửi tin nhắn đặt cược
            #        bet_payload = { ... }
            #        await websocket.send(json.dumps(bet_payload))
            #        ...

            # VÍ DỤ: Nếu nhận được kết quả ván
            # if data.get('type') == 'game_result':
            #    ... (Cập nhật state, profit, wins, losses) ...
            #    
            #    # Lấy kết quả (VÍ DỤ: "Tài", "Xỉu")
            #    result_value = data.get('result_name') 
            #    analyzer.add_result(result_value)
            #
            #    # Yêu cầu danh sách phòng cho ván mới
            #    await asyncio.sleep(1) # Chờ 1s
            #    await websocket.send(json.dumps({"type": "get_rooms"}))

            # Cập nhật giao diện (vẽ lại bảng)
            clear()
            print(LOGO)
            print_table(state["current_rooms"], cfg)


        except json.JSONDecodeError:
            print(f"\n[Server-Text]: {message}")
        except Exception as e:
            print(f"Lỗi khi xử lý tin nhắn: {e}")

async def websocket_main_loop(cfg, stop_event: asyncio.Event):
    """
    (Hàm Async) Vòng lặp chính, quản lý kết nối,
    chạy bộ lắng nghe (receiver) và bộ dừng (stop listener).
    """
    analyzer = GameAnalyzer(bet_threshold=cfg.get("bet_threshold", 4))
    
    URI = "wss://escapemaster.net/" # CÓ THỂ CẦN THÊM PATH
    HEADERS = {
        "Origin": "https://escapemaster.net",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
        "X-User-ID": cfg.get("user_id", ""),
        "X-Secret-Key": cfg.get("secret_key", "")
    }
    
    # Khởi động luồng nghe phím 'q'
    # Phải dùng 'asyncio.to_thread' (Python 3.9+) hoặc 'run_in_executor'
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, listen_for_quit, stop_event)
    
    # Vòng lặp tự động kết nối lại, CHỈ DỪNG khi có tín hiệu 'q'
    while not stop_event.is_set():
        try:
            clear()
            print(LOGO)
            print_table(state["current_rooms"], cfg)
            print(Fore.YELLOW + f"Đang kết nối tới {URI} với UserID: {cfg.get('user_id')}" + Style.RESET_ALL)
            
            async with websockets.connect(
                URI, 
                extra_headers=HEADERS,
                ping_interval=20,
                ping_timeout=20
            ) as websocket:
                
                print(Fore.GREEN + "\n=== KẾT NỐI THÀNH CÔNG! ===" + Style.RESET_ALL)
                
                # TODO: Gửi tin nhắn xác thực (nếu cần)
                
                # TODO: Gửi tin nhắn yêu cầu danh sách phòng
                
                # Chạy 2 tác vụ song song:
                # 1. recv_task: Nhận tin nhắn từ server
                # 2. stop_task: Chờ tín hiệu 'q'
                
                recv_task = asyncio.create_task(
                    websocket_receiver(websocket, cfg, analyzer)
                )
                stop_task = asyncio.create_task(stop_event.wait())
                
                # Chờ 1 trong 2 tác vụ hoàn thành
                done, pending = await asyncio.wait(
                    [recv_task, stop_task], 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Hủy các tác vụ còn lại
                for task in pending:
                    task.cancel()

                if stop_task in done:
                    # Nếu 'q' được nhấn, thoát vòng lặp kết nối
                    print(Fore.YELLOW + "Đã nhận tín hiệu dừng, ngắt kết nối..." + Style.RESET_ALL)
                    break 
                
                # Nếu recv_task_done (tức là websocket bị ngắt kết nối),
                # vòng lặp 'while' sẽ tự động chạy lại để kết nối lại.

        except websockets.exceptions.ConnectionClosedError as e:
            if stop_event.is_set(): break
            print(Fore.RED + f"LỖI: Mất kết nối (Code: {e.code}). Thử lại sau 5s..." + Style.RESET_ALL)
            await asyncio.sleep(5)
        except Exception as e:
            if stop_event.is_set(): break
            print(Fore.RED + f"Lỗi không xác định: {e}. Thử lại sau 5s..." + Style.RESET_ALL)
            await asyncio.sleep(5)
    
    print("Đã dừng Bảng Giám Sát.")


# ----------------- Monitor main loop (ĐÃ SỬA) -----------------
def run_monitor(cfg):
    # Tạo tín hiệu DỪNG
    stop_event = asyncio.Event()
    
    try:
        # Chạy vòng lặp async
        asyncio.run(websocket_main_loop(cfg, stop_event))
    except KeyboardInterrupt:
        # Xử lý Ctrl+C (fallback)
        print("\n" + Fore.YELLOW + "Đã dừng (Ctrl+C). Quay lại menu chính." + Style.RESET_ALL)
        time.sleep(0.6)

# ----------------- Configuration flows (GIỮ NGUYÊN) -----------------
def configure_account_flow(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình tài khoản chạy tool---" + Style.RESET_ALL)
    print()
    show_link_instructions()
    link = input(Fore.YELLOW + "📋 Nhập liên kết của bạn (paste link Vua thoát hiểm): " + Style.RESET_ALL).strip()
    if link:
        uid, skey = parse_link_extract(link)
        if uid:
            cfg["user_id"] = uid
            print(Fore.GREEN + "Your user id is" + Style.RESET_ALL, uid)
        else:
            print(Fore.YELLOW + "Không tìm thấy userId trong link.")
        if skey:
            cfg["secret_key"] = skey
            print(Fore.GREEN + "Your user secret key is" + Style.RESET_ALL, skey[:40] + "...")
        else:
            print(Fore.YELLOW + "Không tìm thấy secretKey trong link.")
    else:
        uid = input("Nhập user id (hoặc Enter để bỏ qua): ").strip()
        if uid:
            cfg["user_id"] = uid
        sk = input("Nhập secret key (hoặc Enter để bỏ qua): ").strip()
        if sk:
            cfg["secret_key"] = sk

    print()
    print("1. BUILD\n2. USDT\n3. WORLD")
    while True:
        c = input(Fore.YELLOW + "Chọn loại tiền bạn muốn chơi (1/2/3): " + Style.RESET_ALL).strip()
        if c in ("1","2","3"):
            cfg["currency"] = {"1":"BUILD","2":"USDT","3":"WORLD"}[c]
            break
        else:
            print("Nhập 1/2/3.")
    while True:
        v = input(Fore.YELLOW + f"Nhập số lượng {cfg['currency']} để đặt (vd 10): " + Style.RESET_ALL).strip()
        try:
            val = float(v)
            if val > 0:
                cfg["amount"] = val
                break
        except:
            pass
        print("Nhập số hợp lệ > 0.")
    while True:
        v = input(Fore.YELLOW + "Nhập hệ số cược sau khi thua (vd 1): " + Style.RESET_ALL).strip()
        try:
            cfg["multiplier"] = float(v)
            break
        except:
            print("Nhập số hợp lệ.")
    while True:
        v = input(Fore.YELLOW + "Sau bao nhiêu ván thì tạm nghỉ (999 nếu không muốn tạm nghỉ): " + Style.RESET_ALL).strip()
        try:
            cfg["pause_after"] = int(v)
            break
        except:
            print("Nhập số nguyên.")
    while True:
        v = input(Fore.YELLOW + "Sau đó tạm nghỉ bao nhiêu ván (0 nếu không muốn nghỉ): " + Style.RESET_ALL).strip()
        try:
            cfg["pause_len"] = int(v)
            break
        except:
            print("Nhập số nguyên.")
    print()
    print(Fore.GREEN + "Chọn Logic (1..4). 1=Random, 2=Phòng đầu, 3=Nhiều tiền, 4=Ít tiền" + Style.RESET_ALL)
    while True:
        v = input(Fore.YELLOW + "Nhập STT logic cần dùng: " + Style.RESET_ALL).strip()
        if v.isdigit() and 1 <= int(v) <= 4: # Sửa logic
            cfg["logic"] = int(v)
            break
        else:
            print("Nhập 1..4.")
    print()
    w = input(Fore.YELLOW + "Nhập webhook URL (Enter để bỏ qua): " + Style.RESET_ALL).strip()
    if w:
        cfg["webhook"] = w
        cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print(Fore.GREEN + "Đã lưu cấu hình vào config.json" + Style.RESET_ALL)
    input("Nhấn Enter để quay lại menu...")

def configure_webhook(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình webhook---" + Style.RESET_ALL)
    w = input("Webhook URL: ").strip()
    if w:
        cfg["webhook"] = w
    cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print("Đã lưu.")
    input("Nhấn Enter ...")

# ----------------- Main program (GIỮ NGUYÊN) -----------------
def main():
    cfg = load_config()
    while True:
        print_main_screen(cfg)
        ch = input().strip().lower()
        if ch == "1":
            print("\n>> Loading..\n")
            time.sleep(0.4)
            # input("Nhấn Enter để bắt đầu giám sát (Ctrl-C để dừng)...") # Bỏ dòng này
            run_monitor(cfg)
        elif ch == "2":
            configure_account_flow(cfg)
        elif ch == "3":
            configure_webhook(cfg)
        elif ch == "4":
            run_monitor#!/usr/bin/env python3
# CTOOL.py -- Full tool (menu, config, monitor) with ARES logo (green/yellow)
# Save as CTOOL.py and run: python3 CTOOL.py
# Requires: pip install colorama

import os
import re
import sys
import time
import json
import random
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# ----------------- Config / Defaults -----------------
CONFIG_FILE = "config.json"
REFRESH_SEC = 3.0
MONITOR_ID = random.randint(100000, 999999)

DEFAULT_CONFIG = {
    "user_id": "",
    "secret_key": "",
    "webhook": "",
    "send_webhook": False,
    "currency": "BUILD",
    "amount": 10,
    "multiplier": 1.0,
    "pause_after": 1,
    "pause_len": 1,
    "logic": 1,
    "auto_start_monitor": False
}

ROOM_NAMES = [
    "Nhà kho", "Phòng họp", "Phòng Giám đốc", "Phòng trò chuyện",
    "Phòng Giám sát", "Văn phòng", "Phòng Tài Vụ", "Phòng Nhân sự"
]

# ----------------- Runtime state -----------------
state = {
    "chosen_room": None,
    "placed_amount": 0.0,
    "wins": 0,
    "losses": 0,
    "rounds": 0,
    "current_chain": 0,
    "max_chain": 0,
    "profit": 0.0,
    "sending": False
}

# ----------------- ARES LOGO (green + yellow) -----------------
LOGO = f"""
{Fore.GREEN}    █████╗ ██████╗ ███████╗███████╗
   ██╔══██╗██╔══██╗██╔════╝██╔════╝
   ███████║██████╔╝█████╗  ███████╗
   ██╔══██║██╔══██╗██╔══╝  ╚════██║
   ██║  ██║██║  ██║███████╗███████║
   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝
{Fore.YELLOW}               POWERED BY ARES TOOL
{Style.RESET_ALL}
"""

# ----------------- Utilities -----------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # fill missing keys
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(Fore.RED + "Lỗi khi lưu config:", e)

def parse_link_extract(link: str):
    """
    Cố gắng trích userId và secretKey từ link dạng query hoặc token trong link.
    """
    uid = None
    skey = None
    m_uid = re.search(r"userId=([0-9]+)", link)
    if m_uid:
        uid = m_uid.group(1)
    m_key = re.search(r"secretKey=([0-9a-fA-F]+)", link)
    if m_key:
        skey = m_key.group(1)
    if not skey:
        m = re.search(r"([0-9a-f]{20,})", link, re.IGNORECASE)
        if m:
            skey = m.group(1)
    return uid, skey

# ----------------- UI components -----------------
def print_main_screen(cfg):
    clear()
    print(LOGO)
    print(Fore.BLUE + "YouTube".ljust(12) + ":" + Style.RESET_ALL, "https://www.youtube.com/@CTOOL")
    print(Fore.BLUE + "TikTok".ljust(12) + ":" + Style.RESET_ALL, "https://www.tiktok.com/@ctool7929")
    print(Fore.BLUE + "Zalo Group".ljust(12) + ":" + Style.RESET_ALL, "https://zalo.me/g/qowvzu729")
    print(Fore.BLUE + "Telegram".ljust(12) + ":" + Style.RESET_ALL, "https://t.me/+PByWNy8hDxYzYTRl")
    print(Fore.BLUE + "Admin".ljust(12) + ":" + Style.RESET_ALL, "Thành Công\n")
    print(Fore.GREEN + "1. Tool vua thoát hiểm")
    print(Fore.GREEN + "2. Cấu hình tài khoản chạy tool")
    print(Fore.GREEN + "3. Cấu hình webhook")
    print(Fore.GREEN + "4. Bảng giám sát (chạy tool)")
    print(Fore.GREEN + "q. Thoát" + Style.RESET_ALL)
    print("\nNhập : ", end="", flush=True)

def show_link_instructions():
    print(Fore.YELLOW + "Hướng dẫn lấy link:" + Style.RESET_ALL)
    print(" 0. Mở chrome")
    print(" 1. Truy cập website xworld.io")
    print(" 2. Đăng nhập vào tài khoản")
    print(" 3. Tìm và nhấp vào Vua thoát hiểm")
    print(" 4. Nhấn lập tức truy cập")
    print(" 5. Sao chép link website và dán vào đây\n")

# ----------------- Mock fetch rooms (simulated) -----------------
def mock_fetch_rooms():
    out = []
    for i, name in enumerate(ROOM_NAMES, start=1):
        people = random.randint(1, 8)
        base = random.uniform(20000, 60000)
        money = round(base + people * random.uniform(1000, 5000), 2)
        out.append({"stt": i, "name": name, "people": people, "money": money, "idx": i-1})
    return out

# ----------------- Logic to choose room -----------------
def choose_room_by_logic(rooms, logic):
    if logic == 1:
        return random.choice(rooms)
    if logic == 2:
        return rooms[0]
    if logic == 3:
        return max(rooms, key=lambda r: r["money"])
    if logic == 4:
        return min(rooms, key=lambda r: r["money"])
    # fallback: random
    return random.choice(rooms)

# ----------------- Monitor / UI table -----------------
def print_table(rooms, cfg):
    print(Fore.CYAN + f"CTOOL-Bảng giám sát kì {MONITOR_ID}" + Style.RESET_ALL)
    print("-" * 74)
    print("┌────┬──────────────────────┬──────────┬────────────┬──────────────────────────────┐")
    print("│ STT│ Phòng                │ Số người │ Số tiền    │ THÔNG TIN                   │")
    print("├────┼──────────────────────┼──────────┼────────────┼──────────────────────────────┤")
    for r in rooms:
        stt = str(r["stt"]).rjust(2)
        name = r["name"][:20].ljust(20)
        people = str(r["people"]).rjust(8)
        money = f"{r['money']:,.2f}".rjust(10)
        chosen = (state["chosen_room"] is not None and state["chosen_room"]["idx"] == r["idx"])
        info_lines = []
        info_lines.append(f"LOGIC:{cfg['logic']}")
        if chosen:
            info_lines.append(f"Phòng đã vào:{r['stt']}")
            info_lines.append(f"Đã đặt:{int(state['placed_amount']) if cfg['currency']=='BUILD' else state['placed_amount']}")
            info_lines.append(f"Trận thắng:{state['wins']}/{state['rounds']}")
            info_lines.append(f"Chuỗi:{state['current_chain']}")
            info_lines.append(f"Max:{state['max_chain']}")
            info_lines.append(f"Lời:{state['profit']:.2f}")
            info_lines.append(f"Wb:{state['sending']}")
        info = "; ".join(info_lines)
        if len(info) > 26:
            info = info[:26] + "…"
        print(f"│ {stt} │ {name} │ {people} │ {money} │ {Fore.CYAN}{info.ljust(26)}{Style.RESET_ALL} │")
    print("└────┴──────────────────────┴──────────┴────────────┴──────────────────────────────┘")
    print()
    print(Fore.GREEN + "---Cấu hình của bạn---" + Style.RESET_ALL)
    print(f"Loại tiền: {cfg['currency']}")
    print(f"Số {cfg['currency']} đặt cho mỗi ván: {cfg['amount']}")
    print(f"Hệ số: {cfg['multiplier']}")
    print(f"Logic: {cfg['logic']}")
    print(f"Sau khi chơi {cfg['pause_after']} thì nghỉ {cfg['pause_len']} ván")
    print("-" * 74)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  Rounds:{state['rounds']}  Wins:{state['wins']}  Losses:{state['losses']}  Profit:{state['profit']:.2f} {cfg['currency']}")

# ----------------- Simulate placing a bet (mock) -----------------
def simulate_round(selected_room, cfg):
    state["placed_amount"] = cfg["amount"]
    state["rounds"] += 1
    win = random.random() < 0.40
    if win:
        state["wins"] += 1
        state["current_chain"] += 1
        state["profit"] += cfg["amount"]
        if state["current_chain"] > state["max_chain"]:
            state["max_chain"] = state["current_chain"]
    else:
        state["losses"] += 1
        state["current_chain"] = 0
        state["profit"] -= cfg["amount"] * cfg["multiplier"]
    payload = {
        "user": cfg.get("user_id"),
        "room": selected_room["name"],
        "stt": selected_room["stt"],
        "amount": cfg["amount"],
        "currency": cfg["currency"],
        "win": win,
        "wins": state["wins"],
        "losses": state["losses"],
        "profit": state["profit"],
        "round": state["rounds"]
    }
    return payload

# ----------------- Monitor main loop -----------------
def run_monitor(cfg):
    try:
        while True:
            rooms = mock_fetch_rooms()
            chosen = choose_room_by_logic(rooms, cfg["logic"])
            state["chosen_room"] = chosen
            clear()
            print(LOGO)
            print_table(rooms, cfg)
            payload = simulate_round(chosen, cfg)
            state["sending"] = cfg.get("send_webhook", False)
            # if real webhook: send here using requests
            time.sleep(REFRESH_SEC)
    except KeyboardInterrupt:
        print("\n" + Fore.YELLOW + "Stopped. Quay lại menu chính." + Style.RESET_ALL)
        time.sleep(0.6)

# ----------------- Configuration flows -----------------
def configure_account_flow(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình tài khoản chạy tool---" + Style.RESET_ALL)
    print()
    show_link_instructions()
    link = input(Fore.YELLOW + "📋 Nhập liên kết của bạn (paste link Vua thoát hiểm): " + Style.RESET_ALL).strip()
    if link:
        uid, skey = parse_link_extract(link)
        if uid:
            cfg["user_id"] = uid
            print(Fore.GREEN + "Your user id is" + Style.RESET_ALL, uid)
        else:
            print(Fore.YELLOW + "Không tìm thấy userId trong link.")
        if skey:
            cfg["secret_key"] = skey
            print(Fore.GREEN + "Your user secret key is" + Style.RESET_ALL, skey[:40] + "...")
        else:
            print(Fore.YELLOW + "Không tìm thấy secretKey trong link.")
    else:
        uid = input("Nhập user id (hoặc Enter để bỏ qua): ").strip()
        if uid:
            cfg["user_id"] = uid
        sk = input("Nhập secret key (hoặc Enter để bỏ qua): ").strip()
        if sk:
            cfg["secret_key"] = sk

    print()
    print("1. BUILD\n2. USDT\n3. WORLD")
    while True:
        c = input(Fore.YELLOW + "Chọn loại tiền bạn muốn chơi (1/2/3): " + Style.RESET_ALL).strip()
        if c in ("1","2","3"):
            cfg["currency"] = {"1":"BUILD","2":"USDT","3":"WORLD"}[c]
            break
        else:
            print("Nhập 1/2/3.")
    while True:
        v = input(Fore.YELLOW + f"Nhập số lượng {cfg['currency']} để đặt (vd 10): " + Style.RESET_ALL).strip()
        try:
            val = float(v)
            if val > 0:
                cfg["amount"] = val
                break
        except:
            pass
        print("Nhập số hợp lệ > 0.")
    while True:
        v = input(Fore.YELLOW + "Nhập hệ số cược sau khi thua (vd 1): " + Style.RESET_ALL).strip()
        try:
            cfg["multiplier"] = float(v)
            break
        except:
            print("Nhập số hợp lệ.")
    while True:
        v = input(Fore.YELLOW + "Sau bao nhiêu ván thì tạm nghỉ (999 nếu không muốn tạm nghỉ): " + Style.RESET_ALL).strip()
        try:
            cfg["pause_after"] = int(v)
            break
        except:
            print("Nhập số nguyên.")
    while True:
        v = input(Fore.YELLOW + "Sau đó tạm nghỉ bao nhiêu ván (0 nếu không muốn nghỉ): " + Style.RESET_ALL).strip()
        try:
            cfg["pause_len"] = int(v)
            break
        except:
            print("Nhập số nguyên.")
    print()
    print(Fore.GREEN + "Chọn Logic (1..12). 1=Random 1 trong 8" + Style.RESET_ALL)
    while True:
        v = input(Fore.YELLOW + "Nhập STT logic cần dùng: " + Style.RESET_ALL).strip()
        if v.isdigit() and 1 <= int(v) <= 12:
            cfg["logic"] = int(v)
            break
        else:
            print("Nhập 1..12.")
    print()
    w = input(Fore.YELLOW + "Nhập webhook URL (Enter để bỏ qua): " + Style.RESET_ALL).strip()
    if w:
        cfg["webhook"] = w
        cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print(Fore.GREEN + "Đã lưu cấu hình vào config.json" + Style.RESET_ALL)
    input("Nhấn Enter để quay lại menu...")

def configure_webhook(cfg):
    clear()
    print(LOGO)
    print(Fore.YELLOW + "---Cấu hình webhook---" + Style.RESET_ALL)
    w = input("Webhook URL: ").strip()
    if w:
        cfg["webhook"] = w
    cfg["send_webhook"] = input("Bật gửi webhook? (y/n): ").strip().lower() == "y"
    save_config(cfg)
    print("Đã lưu.")
    input("Nhấn Enter ...")

# ----------------- Main program -----------------
def main():
    cfg = load_config()
    while True:
        print_main_screen(cfg)
        ch = input().strip().lower()
        if ch == "1":
            print("\n>> Loading..\n")
            time.sleep(0.4)
            input("Nhấn Enter để bắt đầu giám sát (Ctrl-C để dừng)...")
            run_monitor(cfg)
        elif ch == "2":
            configure_account_flow(cfg)
        elif ch == "3":
            configure_webhook(cfg)
        elif ch == "4":
            run_monitor(cfg)
        elif ch in ("q","quit","exit"):
            print("Bye.")
            break
        else:
            print("Nhập 1/2/3/4 hoặc q.")
            time.sleep(0.6)
        clear()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nThoát chương trình.")
