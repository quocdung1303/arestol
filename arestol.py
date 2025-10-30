#!/usr/bin/env python3
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
