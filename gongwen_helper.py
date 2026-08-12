# -*- coding: utf-8 -*-
"""
新北市公務雲 - 公文小助手 v17 (測試版，基於 v16)
v17 改動：
  1. 修正支線下載視窗 ChromiumOptions 設定順序
     → 解決『支線錯誤: not enough values to unpack (expected 2, got 1)』
  2. 重寫外部附件下載偵測(只認新增檔、等大小穩定)，
     避免把公文本文 PDF 誤改成附件名
  3. 收文清單開放屬性「退」(原本只收「承辦」)，供測試用
  4. 外部附件偵測全程輸出診斷訊息，不再靜默失敗
原 v8.2 說明：UI復刻+雙核心覆蓋版
Core Logic: 下載濾網 + 自動歸檔 + 自動覆蓋 + 無頭模式開關
UI Design: 圓角按鈕 + 插圖 + 黑底黃字Log + 署名保留 + 勾選框
Merged by: Gemini
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import threading
import sys
import os
import time
import json
import re
from datetime import datetime

# 引入爬蟲與 PDF 處理套件
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.errors import ContextLostError
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except Exception:
    PDFPLUMBER_OK = False

# ==========================================
# 🔧 系統設定與資源處理
# ==========================================
CONFIG_FILE = 'settings.json'

def resource_path(relative_path):
    """ 取得資源的絕對路徑 """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_settings():
    data = {'pin': '', 'download_path': '', 'class_no': '1199'}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data.update(json.load(f))
        except:
            pass
    if not str(data.get('class_no', '')).strip():
        data['class_no'] = '1199'
    return data

def save_settings(pin, path, class_no=None):
    data = load_settings()
    data['pin'] = pin
    data['download_path'] = path
    if class_no is not None:
        data['class_no'] = class_no
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"設定儲存失敗: {e}")

# ==========================================
# 🎨 UI 設定 (保留你的原始設計)
# ==========================================
COLOR_BG_WHITE = "#FFFFFF"
COLOR_PAGE = "#F4F5F7"            # 頁面底 (沉穩淺灰)
COLOR_TOP_BLUE = "#E0F7FA"
COLOR_HEADER_BLUE = "#1E3A5F"     # 深海軍藍標題帶
COLOR_SUBTITLE = "#A9BBD4"        # 副標 (淺藍灰)
COLOR_BTN_BLUE = "#1E3A5F"        # 主按鈕 (實心海軍藍)
COLOR_BTN_HOVER = "#2C4E7A"       # 主按鈕 hover
COLOR_BTN_TEXT = "#FFFFFF"
COLOR_BTN2_BG = "#EDF1F6"         # 次按鈕底
COLOR_BTN2_BORDER = "#C6D0DE"     # 次按鈕邊框
COLOR_BTN2_HOVER = "#E1E8F1"      # 次按鈕 hover
COLOR_BTN2_TEXT = "#1E3A5F"       # 次按鈕文字
COLOR_LOG_BG = "#0F1B2D"          # log 深色底
COLOR_LOG_FG = "#5EC98C"          # log 綠字
COLOR_TEXT_MAIN = "#1F2937"
COLOR_TEXT_SUB = "#64748B"

def resize_image(path, target_height):
    try:
        full_path = resource_path(path)
        if not os.path.exists(full_path): return None
        original_img = Image.open(full_path)
        scale_ratio = target_height / float(original_img.size[1])
        target_width = int(float(original_img.size[0]) * float(scale_ratio))
        resized_img = original_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(resized_img)
    except Exception as e:
        print(f"❌ 縮圖失敗：{e}")
        return None

class RoundedButton(tk.Canvas):
    """ 小圓角矩形按鈕：outline=False 實心(主)，outline=True 淺底邊框(次) """
    def __init__(self, parent, text, command, width=300, height=52, radius=8,
                 bg_color=COLOR_PAGE, btn_color=COLOR_BTN_BLUE, text_color=COLOR_BTN_TEXT,
                 hover_color=COLOR_BTN_HOVER, outline=False, border_color=COLOR_BTN2_BORDER):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0, bd=0)
        self.command = command
        self._text = text
        self.bg_color = bg_color
        self.btn_color = btn_color
        self.text_color = text_color
        self.hover_color = hover_color
        self.outline = outline
        self.border_color = border_color
        self.radius = radius
        self.w = width
        self.h = height
        self.fill_id = None
        self.text_id = None
        self._build()

        self.tag_bind("btn", "<Button-1>", self.on_click)
        self.tag_bind("btn", "<Enter>", self.on_enter)
        self.tag_bind("btn", "<Leave>", self.on_leave)
        self.config(cursor="hand2")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _base_fill(self):
        return COLOR_BTN2_BG if self.outline else self.btn_color

    def _build(self):
        self.delete("all")
        if self.outline:
            self._round_rect(1, 1, self.w-1, self.h-1, self.radius, fill=self.border_color, tags="btn")
            self.fill_id = self._round_rect(3, 3, self.w-3, self.h-3, max(self.radius-1, 1),
                                            fill=self._base_fill(), tags="btn")
        else:
            self.fill_id = self._round_rect(1, 1, self.w-1, self.h-1, self.radius,
                                            fill=self.btn_color, tags="btn")
        self.text_id = self.create_text(self.w/2, self.h/2, text=self._text, fill=self.text_color,
                                        font=("Microsoft JhengHei", 14, "bold"), tags="btn")

    def on_click(self, event):
        if self.command:
            self.command()

    def on_enter(self, event):
        self.itemconfig(self.fill_id, fill=(COLOR_BTN2_HOVER if self.outline else self.hover_color))

    def on_leave(self, event):
        self.itemconfig(self.fill_id, fill=self._base_fill())

    def set_text(self, text):
        self._text = text
        self.itemconfig(self.text_id, text=text)

# ==========================================
# 🧠 核心邏輯 (Helper Functions)
# ==========================================
ENTRY_URL = 'https://cloud.ntpc.gov.tw/certificateIndex.do'
MAX_SUBJECT_LENGTH = 15

# 外部附件的流水號前綴。v16 內部附件與外部附件都從 2 開始編，
# 同一份公文兩者並存時編號會交錯(例 -2-Ext-, -3-附件, -4-Ext-)，難以辨識。
# 改成外部附件走獨立序列 E1, E2, E3...，排序時自然聚在內部附件之後。
EXT_SEQ_PREFIX = 'E'

# 專用乾淨 Chrome 設定檔：不跳「誰在使用 Chrome」選單、沒有同事的記憶密碼、
# 不與使用者自己開的 Chrome 打架。路徑純 ASCII(避免中文路徑坑)。
PROFILE_DIR = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'DocHelperChrome')
PROFILE_DIR_EXT = PROFILE_DIR + '_ext'  # 支線下載視窗專用(與主視窗同時開，不能共用同一設定檔)

PACE_SEC = 2  # RPA 步伐：動作間隔下限(秒)。穩定比快速重要。

def quiet_chrome(co):
    """ 關掉 Chrome 會突然彈出打斷 RPA 的『原生』視窗(密碼外洩警告、密碼管理員詢問等)。
        這類彈窗不是網頁元素、DrissionPage 點不到，只能在啟動時關閉。 """
    co.set_pref('credentials_enable_service', False)
    co.set_pref('profile.password_manager_enabled', False)
    co.set_pref('profile.password_manager_leak_detection', False)
    co.set_argument('--disable-features=PasswordLeakDetection,PasswordCheck,SafetyHub')
    return co

def log_msg(text):
    """ 黑底黃字 Log 輸出 """
    try:
        log_text.insert(tk.END, f"{text}\n")
        log_text.see(tk.END)
    except:
        print(text)

def pace(sec=PACE_SEC):
    """ RPA 步伐：動作之間睡滿至少 PACE_SEC 秒 """
    time.sleep(max(sec, PACE_SEC))

def step_msg(msg, wait=PACE_SEC):
    """ 話癆模式：先報告接下來要做什麼，睡滿 wait 秒才動作，使用者才知道程式沒壞 """
    wait = max(wait, PACE_SEC)
    log_msg(f"⏳ {wait} 秒後：{msg}")
    time.sleep(wait)

def pin_fill(ele, pin, desc="PIN"):
    """ 先清空再輸入(防任何殘留/填充)。
        讀回驗證僅供 log 診斷、不擋流程——乾淨設定檔下沒有記憶密碼可疊加，
        且部分欄位(如公務雲登入頁)JS 讀不到真值，硬驗會誤殺。 """
    try:
        ele.clear()
    except Exception:
        pass
    try:
        ele.run_js("this.value='';")  # 雙保險清空
    except Exception:
        pass
    time.sleep(1)
    ele.input(pin)
    time.sleep(1)
    val = arc_read_value(ele)
    # 🔧 v17 修正：v16 這裡不論如何都 return True，導致呼叫端
    #   `if not pin_fill(...): raise RuntimeError(...)` 永遠不會觸發（死碼），
    #   PIN 打錯也會照送 → 自然人憑證有鎖卡風險。
    # 但也不能「讀不到就擋」——部分欄位(如公務雲登入頁)JS 讀不到真值，硬驗會誤殺。
    # 折衷：只有在「讀得到值、而且確定不符」時才擋下。
    if val is None or val == '':
        log_msg(f"   ({desc} 欄位讀不到值，無法驗證，續行)")
        return True
    if val != pin:
        log_msg(f"   X {desc} 讀回 {len(val)} 碼、應為 {len(pin)} 碼且內容不符——中止，避免憑證鎖卡")
        return False
    log_msg(f"   ({desc} 讀回核對無誤)")
    return True

def clean_filename(text, max_len=15):
    if not text: return "無標題"
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', text)
    cleaned = cleaned.strip().replace('\n', '').replace('\r', '').replace(' ', '')
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned

def smart_click(ele):
    try:
        ele.scroll.to_see()
        pace()
        ele.click()
    except:
        ele.click(by_js=True)

def get_smart_subject(row_ele):
    try:
        cells = row_ele.eles('tag:td')
        longest_text = ""
        for cell in cells:
            txt = cell.text.strip()
            if len(txt) > len(longest_text):
                longest_text = txt
        if len(longest_text) < 2:
            return "未命名公文"
        return longest_text
    except:
        return "未命名公文"


# ---------- v17 新增 ----------
# 收文清單要收哪些「屬性」。正式使用維持只收「承辦」。
# 測試時若要納入「退」等其他屬性，改成 ('承辦', '退') 即可
# (非承辦的列會額外要求該列有純數字文號連結，以排除表頭/選單)。
DOC_ROW_TAGS = ('承辦',)
HEADER_NOBR_SKIP = 3            # 「承辦」清單前 N 個 nobr 是表頭/選單，不是公文列

def _free_port(preferred=None):
    """ 取一個沒被佔用的本機埠。支線視窗必須用獨立埠，否則會跟主視窗打架。 """
    import socket
    if preferred:
        try:
            with socket.socket() as s:
                s.bind(('127.0.0.1', int(preferred)))
            return int(preferred)
        except OSError:
            pass
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _row_key(nobr):
    try:
        row = nobr.parent('tag:tr')
        return (row.text or '').replace('\n', ' ').strip()[:120]
    except Exception:
        return None


def _row_has_doc_link(nobr):
    """ 該列是否有『純數字』的文號連結。用來排除表頭/選單列
        (沿用 arc_goto_list_and_pick 已驗證過的判斷法)。 """
    try:
        row = nobr.parent('tag:tr')
        for a in row.eles('tag:a'):
            if a.text.strip().isdigit():
                return True
    except Exception:
        pass
    return False


def collect_doc_nobrs(frame_func, quiet=False):
    """ 撈公文列的 nobr，依 DOM 順序、去重。
        「承辦」沿用 v16 原邏輯(跳過前 HEADER_NOBR_SKIP 個表頭)，行為不變；
        其他標籤(如「退」)則要求該列有純數字文號連結，才算公文列。 """
    picked, seen = [], set()
    n_main = n_extra = 0

    try:
        base = frame_func.eles('tag:nobr@@text():承辦')
    except Exception:
        base = []
    for nb in base[HEADER_NOBR_SKIP:]:
        k = _row_key(nb)
        if not k or k in seen:
            continue
        seen.add(k); picked.append(nb); n_main += 1

    for tag in DOC_ROW_TAGS:
        if tag == '承辦':
            continue
        try:
            extra = frame_func.eles(f'tag:nobr@@text():{tag}')
        except Exception:
            extra = []
        for nb in extra:
            k = _row_key(nb)
            if not k or k in seen:
                continue
            if not _row_has_doc_link(nb):
                continue
            seen.add(k); picked.append(nb); n_extra += 1

    if not quiet:
        log_msg(f"   (清單掃描：承辦 {n_main} 筆、其他屬性 {n_extra} 筆)")
    return picked
# ---------- v17 新增結束 ----------

# ==========================================
# 📥 模組 A: 自動收文 (下載 + 覆蓋保護)
# ==========================================
# 🔧 v17：原本五個關鍵字中，實測公文只靠「驗證碼」命中，太脆弱，補上下載區用語。
EXT_KEYWORDS = ["雲端硬碟", "附件請至", "下載連結", "驗證碼", "電子附件",
                "附件下載區", "附件下載", "doc2-attach"]

def check_pdf_for_external_content(pdf_path):
    """ 讀本文 PDF 第1頁，判斷是否有「要去附件下載區抓」的外部附件。
        v17: 每一步都出聲。v16 在沒裝 pdfplumber / 抽不到文字時完全靜默，
        使用者只看到「沒有外部附件」，無從分辨是真的沒有還是程式沒做事。 """
    result = {'found': False, 'doc_number': '', 'code': ''}

    if not os.path.exists(pdf_path):
        log_msg("   ! 外部附件偵測略過：找不到本文 PDF")
        return result

    if not PDFPLUMBER_OK:
        log_msg("   ⚠️ 未安裝 pdfplumber，無法偵測外部附件！")
        log_msg("      請執行:  python -m pip install pdfplumber")
        return result

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                log_msg("   ! 本文 PDF 沒有頁面")
                return result
            text = pdf.pages[0].extract_text()
            if not text:
                log_msg("   ! 本文第1頁抽不到文字(可能是掃描圖檔)，無法偵測外部附件")
                return result

            hits = [k for k in EXT_KEYWORDS if k in text]
            log_msg(f"   (PDF掃描：第1頁 {len(text)} 字，關鍵字命中 {hits if hits else '無'})")
            if not hits:
                return result

            result['found'] = True

            code_match = re.search(r'驗證碼[:：]\s*([A-Za-z0-9]+)', text)
            if code_match:
                result['code'] = code_match.group(1)
            else:
                log_msg("   ! 有外部附件跡象，但抓不到驗證碼")

            # 優先抓「發文字號」那一行；抓不到才退回全文第一個「字第…號」。
            # (說明段常引用別的字號，例如「臺教國署國字第…號」，容易誤抓)
            doc_match = (re.search(r'發文字號[^0-9]{0,20}字第(\d+)號', text)
                         or re.search(r'字第(\d+)號', text))
            if doc_match:
                result['doc_number'] = doc_match.group(1)
            else:
                log_msg("   ! 有外部附件跡象，但抓不到文號")

            all_nums = re.findall(r'字第(\d+)號', text)
            if len(all_nums) > 1:
                log_msg(f"   (本文出現多組字號 {all_nums}，採用 {result['doc_number']})")
    except Exception as e:
        log_msg(f"❌ PDF 解析失敗: {e}")
    return result

def download_external_files_gui(doc_no, code, prefix, save_path):
    # 🔥 讀取無頭模式變數
    is_headless = headless_var.get()
    
    downloaded_files = [] 
    if not doc_no or not code: return downloaded_files
    
    log_msg(f"🕵️ [支線] 啟動下載視窗... (文號:{doc_no})")

    co = ChromiumOptions()
    # 🔧 v17 修正：v16 寫成 auto_port() → set_user_data_path()，
    # 但 set_user_data_path() 內部會把 _auto_port 設回 False，
    # 而 auto_port() 已先把 _address 清成 ''，導致 address 是空字串，
    # 最後 connect_browser 的 `ip, port = address.split(':')` 爆
    # 「not enough values to unpack (expected 2, got 1)」。
    # 正解：先 set_local_port()（寫好 _address 並關掉 auto_port），再設 user data path。
    _p = _free_port(9333)
    log_msg(f"🕵️ [支線] 使用埠號 {_p}")
    co.set_local_port(_p)
    co.set_user_data_path(PROFILE_DIR_EXT)  # 支線專用乾淨設定檔
    quiet_chrome(co)
    co.headless(is_headless) # 🔥 設定無頭
    co.set_download_path(save_path)
    co.set_pref('profile.default_content_settings.popups', 0)
    co.set_pref('download.prompt_for_download', False)
    co.set_pref('safebrowsing.enabled', False)
    co.set_pref('safebrowsing.disable_download_protection', True)

    ext_page = None
    try:
        ext_page = ChromiumPage(co)
        
        # 🔥 如果不是無頭模式，才縮小視窗
        if not is_headless:
            try: ext_page.set.window.mini()
            except: pass
            
        ext_page.set.download_path(save_path)
        ext_page.get("https://doc2-attach.ntpc.gov.tw/ntpc_sodatt/QueryAttach.aspx")

        if ext_page.ele('#txtQueryPostCode'):
            ext_page.ele('#txtQueryPostCode').input(doc_no)
            ext_page.ele('#txtQueryToken').input(code)
            log_msg("🕵️ 查詢外部附件...")
            ext_page.ele('#btnClick').click()
            time.sleep(2)
            links = ext_page.eles('tag:a@@onclick:OpenFile')
            
            if not links:
                log_msg("⚠️ 未找到外部附件連結。")
            else:
                log_msg(f"👀 找到 {len(links)} 個附件...")
                for count, link in enumerate(links, start=1):
                    raw_name = link.text.strip()
                    base_name, ext = os.path.splitext(raw_name)
                    if not ext: ext = ".pdf"
                    safe_base = clean_filename(base_name, max_len=MAX_SUBJECT_LENGTH)
                    target_name = f"{prefix}{EXT_SEQ_PREFIX}{count}-Ext-{safe_base}{ext}"
                    target_full_path = os.path.join(save_path, target_name)
                    
                    log_msg(f"⬇️ [外部] 下載: {target_name}")
                    
                    try:
                        if os.path.exists(target_full_path):
                            try: os.remove(target_full_path)
                            except: pass

                        # 🔧 v17 修正：v16 內層 while 第一圈就 break、判斷式是空 pass，
                        # 等待邏輯等於不存在；又用 max(整個資料夾, getmtime) 挑最新檔改名，
                        # 會把剛下載的公文本文 PDF 誤改成附件名。
                        # 正解：只認「這次點擊後才新增」的檔案，並等檔案大小穩定。
                        before_files = set(os.listdir(save_path))
                        link.click(by_js=True)

                        new_file = None
                        deadline = time.time() + 30
                        while time.time() < deadline:
                            time.sleep(0.5)
                            now_files = set(os.listdir(save_path))
                            if any(x.endswith(('.crdownload', '.tmp')) for x in now_files):
                                continue
                            added = [x for x in (now_files - before_files)
                                     if not x.endswith(('.crdownload', '.tmp'))]
                            if not added:
                                continue
                            cand = os.path.join(save_path, added[0])
                            try:
                                s1 = os.path.getsize(cand)
                                time.sleep(1)
                                s2 = os.path.getsize(cand)
                            except OSError:
                                continue
                            if s1 > 0 and s1 == s2:
                                new_file = cand
                                break

                        if not new_file:
                            log_msg("   X 等不到新檔案落地，略過此附件")
                        else:
                            if os.path.abspath(new_file) != os.path.abspath(target_full_path):
                                os.replace(new_file, target_full_path)
                            downloaded_files.append(target_full_path)
                            log_msg(f"   OK 已存成 {target_name}")
                             
                    except Exception as e:
                        log_msg(f"❌ 下載異常: {e}")
    except Exception as e:
        log_msg(f"❌ 支線錯誤: {e}")
    finally:
        if ext_page: ext_page.quit()
    return downloaded_files

# ---------- v18 回填上傳 ----------
# v17 失敗原因（實測釐清）：
#   1. SPEED 的「附件」視窗是同頁面的 modal，且在頁面載入時就已存在於 DOM、
#      只是隱藏著。v17 用 speed.ele('#selectfiles') 判斷「介面開好了」，
#      視窗根本沒開也會判定成功 → 檔案被塞進隱藏 input，什麼都沒發生（瞎忙）。
#      → 改成檢查視窗「可見性」，不是存在性。
#   2. 存檔鈕的 fallback 鏈裡有 'text:存檔'，排在 'text:確定' 前面。
#      附件視窗底部的鈕其實叫「確定」，所以每次都掉到工具列那顆
#      公文「存檔」→ 跳出「存檔成功！」造成已上傳的假象。
#      → 移除 'text:存檔'，只認 AttachmentSave 或視窗內可見的「確定」。
#   3. 公文剛開啟時按鈕 JS 尚未就緒，要先等。

# ======== ⏱ 調速區（覺得 RPA 跑太快、動作會漏，就把這些數字調大）========
ATTACH_BTN_TEXT     = '附件'   # 工具列上開啟附件視窗的鈕
ATTACH_OPEN_WAIT    = 3        # 公文視窗載入後，先等幾秒才點「附件」
UPLOAD_ROW_TIMEOUT  = 20       # 每個附件等它出現在清單的上限(秒)
UPLOAD_GAP          = 1.5      # 兩個附件之間的額外間隔(秒)
SAVE_BEFORE_WAIT    = 2        # 按「確定」之前先等幾秒
SAVE_AFTER_WAIT     = 3        # 按「確定」之後等幾秒
# 全域步伐 PACE_SEC 在檔案上方（目前 2 秒），那個會影響所有動作
# ======================================================================


def _visible(ele):
    try:
        return bool(ele) and ele.states.is_displayed
    except Exception:
        return False


def _attach_dialog_open(speed):
    """ 附件視窗是否『真的顯示出來』。
        不能只用 ele() 判斷存在——modal 藏在 DOM 裡一直都在。 """
    for sel in ('text:附件類別', 'text:選擇檔案', 'text:發文附件大小總計'):
        try:
            if _visible(speed.ele(sel, timeout=0.5)):
                return True
        except Exception:
            pass
    return False


def _attach_table_empty(speed):
    """ 附件清單是否還是「無相關資料」（代表一個都沒加進去） """
    try:
        return _visible(speed.ele('text:無相關資料', timeout=0.5))
    except Exception:
        return False


def _attach_row_present(speed, fname):
    """ 該檔名是否已出現在附件清單表格裡（代表系統真的收下了） """
    try:
        for e in speed.eles(f'text:{fname}'):
            if _visible(e):
                return True
    except Exception:
        pass
    return False


def _open_attach_dialog(speed):
    """ 點「附件」開視窗，點完驗證視窗真的可見，沒開就換招重試。 """
    if _attach_dialog_open(speed):
        log_msg("   附件視窗已開著")
        return True

    strategies = [
        ('CDP點擊', lambda e: e.click()),
        ('JS click', lambda e: e.click(by_js=True)),
        ('JS滑鼠事件序列', lambda e: e.run_js(
            "var el=this;"
            "['mousedown','mouseup','click'].forEach(function(t){"
            "el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}));});")),
    ]
    for name, fn in strategies:
        arc_activate(speed)
        btn = None
        for cand in speed.eles(f'text:{ATTACH_BTN_TEXT}'):
            if _visible(cand):
                btn = cand
                break
        if not btn:
            log_msg("   X 工具列找不到可見的『附件』鈕")
            return False
        try:
            fn(btn)
        except Exception as e:
            log_msg(f"   ! [{name}] 點擊出錯: {e}")
        end = time.time() + 6
        while time.time() < end:
            if _attach_dialog_open(speed):
                log_msg(f"   OK [{name}] 附件視窗已開啟")
                return True
            time.sleep(0.5)
        log_msg(f"   ! [{name}] 點了但附件視窗沒出現，換下一招...")
    return False


def _find_attach_save(speed):
    """ 找附件視窗的存檔鈕。
        絕不使用 'text:存檔'——那是工具列的公文存檔，按下去會誤存公文。 """
    for sel in ('css:a.btn.btn-primary[data-speed-action="AttachmentSave"]',
                '@data-speed-action=AttachmentSave'):
        try:
            e = speed.ele(sel, timeout=1)
            if e:
                return e, sel
        except Exception:
            pass
    # 視窗底部的「確定」，必須可見（頁面別處也有叫確定的鈕）
    try:
        for e in speed.eles('text:確定'):
            if _visible(e):
                return e, 'text:確定(可見)'
    except Exception:
        pass
    return None, None


def upload_files_to_doc(page, doc_row_ele, file_paths):
    if not file_paths:
        return False
    import shutil
    log_msg("📤 [回填] 準備上傳...")
    temps = []
    ok_all = False
    speed = None
    try:
        doc_link = None
        try:
            for c in doc_row_ele.eles('tag:td'):
                a = c.ele('tag:a', timeout=0.3)
                if a and a.text.strip().isdigit():
                    doc_link = a
                    break
        except Exception:
            pass
        if not doc_link:
            try:
                doc_link = doc_row_ele.ele('tag:a', timeout=1)
            except Exception:
                doc_link = None
        if not doc_link:
            log_msg("   X 找不到公文連結，略過回填")
            return False

        before = set(page.tab_ids)
        try:
            doc_link.click()
        except Exception:
            try:
                doc_link.click(by_js=True)
            except Exception:
                pass

        speed = None
        end = time.time() + 20
        while time.time() < end:
            for tid in page.tab_ids:
                if tid in before:
                    continue
                t = page.get_tab(tid)
                try:
                    if 'SUPERDESK' in (t.url or '') or 'Super Desk' in (t.title or ''):
                        speed = t
                        break
                except Exception:
                    pass
            if speed:
                break
            time.sleep(0.4)
        if not speed:
            speed = page.latest_tab
            log_msg("   ! 沒等到新開的 SPEED 視窗，改用最新分頁")
        try:
            speed.wait.doc_loaded(timeout=10)
        except Exception:
            pass
        arc_activate(speed)

        # 公文剛載入時按鈕 JS 未就緒，先等（實測必要）
        step_msg("開啟『附件』視窗", wait=ATTACH_OPEN_WAIT)

        if not _open_attach_dialog(speed):
            log_msg("   X 開不了附件上傳視窗，保留視窗供人工檢查")
            return False

        was_empty = _attach_table_empty(speed)
        landed, missing = [], []
        for fp in file_paths:
            if not os.path.exists(fp):
                continue
            up_path = fp
            stem, ext = os.path.splitext(os.path.basename(fp))
            if ' ' in stem:   # 系統規定：附件檔名不得含空白
                stem = stem.replace(' ', '')
            if len(stem) > 40:
                stem = stem[:40]
            newbase = stem + ext
            if newbase != os.path.basename(fp):
                cand = os.path.join(os.path.dirname(fp), "_up_" + newbase)
                try:
                    shutil.copy(fp, cand)
                    temps.append(cand)
                    up_path = cand
                    log_msg(f"   (檔名調整為 {os.path.basename(cand)})")
                except Exception:
                    up_path = fp

            base = os.path.basename(up_path)
            finp = speed.ele('#selectfiles', timeout=3) or speed.ele('css:input[type=file]', timeout=3)
            if not finp:
                log_msg(f"   X 找不到檔案輸入欄，略過 {base}")
                missing.append(base)
                continue
            log_msg(f"⬆️ 上傳: {base}")
            try:
                finp.input(up_path)
            except Exception as e:
                log_msg(f"   X 上傳動作失敗: {e}")
                missing.append(base)
                continue

            try:
                speed.handle_alert(accept=True, timeout=1)
            except Exception:
                pass

            # 🔧 v18: 逐檔驗證取代固定 sleep。
            # 實測：三個檔案用 time.sleep(2) 間隔連續丟，第三個會被 plupload 吃掉
            # (前一個 1.18MB 還在處理)。改成等它真的出現在附件清單才傳下一個，
            # 快的檔案不會空等、慢的檔案不會被蓋掉。
            appeared = False
            wait_end = time.time() + UPLOAD_ROW_TIMEOUT
            while time.time() < wait_end:
                if _attach_row_present(speed, base):
                    appeared = True
                    break
                time.sleep(0.5)
            if appeared:
                landed.append(base)
                log_msg(f"   OK 已進入附件清單 ({len(landed)}/{len(file_paths)})")
            else:
                missing.append(base)
                log_msg(f"   X 等了 {UPLOAD_ROW_TIMEOUT} 秒仍沒出現在附件清單")
            time.sleep(UPLOAD_GAP)

        if missing:
            log_msg(f"   ⚠️ 有 {len(missing)} 個檔案沒進清單: {missing}")
            log_msg("      (若常發生，把檔案上方的 UPLOAD_ROW_TIMEOUT / UPLOAD_GAP 調大)")

        if not landed:
            log_msg("   X 一個附件都沒進清單，不按確定")
            return False
        if was_empty and _attach_table_empty(speed):
            log_msg("   X 附件清單仍是『無相關資料』——檔案沒被系統接收，不按確定")
            return False

        save, how = _find_attach_save(speed)
        if not save:
            log_msg("   X 找不到附件視窗的存檔鈕(不誤按工具列存檔)，保留視窗供人工檢查")
            return False

        step_msg(f"按存檔鈕 [{how}] 送出 {len(landed)} 個附件", wait=SAVE_BEFORE_WAIT)
        try:
            save.click()
        except Exception:
            try:
                save.click(by_js=True)
            except Exception as e:
                log_msg(f"   X 存檔鈕點不動: {e}")
                return False
        time.sleep(SAVE_AFTER_WAIT)
        try:
            speed.handle_alert(accept=True, timeout=2)
        except Exception:
            pass

        ok_all = not missing
        if missing:
            log_msg(f"⚠️ 回填部分完成：成功 {len(landed)}、失敗 {len(missing)}。視窗保留供人工補傳。")
            return False
        log_msg(f"✅ 回填完成（{len(landed)} 個附件全數送出）")
        try:
            speed.close()
        except Exception:
            pass
        return True

    except Exception as e:
        log_msg(f"❌ 回填失敗: {e}")
        return False
    finally:
        for tp in temps:
            try:
                os.remove(tp)
            except Exception:
                pass
        if not ok_all and speed is not None:
            log_msg("   (公文視窗保留未關，方便你手動確認附件狀態)")


# ==========================================
# 📂 模組 B: 自動歸檔 (Archiver)
# ==========================================


CLASS_NO = "1199"
REC_KEYS = ['ODCMSETFILLDATA', '歸檔註記', '錄檔']
JS_PICK_YJ = (
    "var rs=Array.from(document.querySelectorAll('tr')),p=[];"
    "for(const r of rs){const a=r.querySelector('a');"
    "const d=a?a.textContent.trim():'';"
    "if(!/^[0-9]+$/.test(d))continue;"
    "if(!Array.from(r.querySelectorAll('td')).some(td=>td.textContent.trim()==='已決'))continue;"
    "const cb=r.querySelector('input[type=checkbox][id*=chkMark]');"
    "if(cb&&!cb.checked){cb.click();p.push(d);}}return p;"
)


def arc_wait_click(ctx, locator, timeout=12, desc=""):
    ele = ctx.ele(locator, timeout=timeout)
    if not ele:
        log_msg(f"   X 找不到可點: {locator} {desc}")
        return False
    try:
        ele.wait.clickable(timeout=timeout)
    except Exception:
        pass
    try:
        ele.click()
    except Exception:
        try:
            ele.click(by_js=True)
        except Exception as e:
            log_msg(f"   X 點擊失敗 {locator}: {e}")
            return False
    return True


def arc_find_tab(page, keys):
    # 分頁在跳轉瞬間可能生滅，取分頁/讀屬性都要包 try，斷線就跳過該分頁
    try:
        tids = page.tab_ids
    except Exception:
        return None
    for tid in tids:
        try:
            t = page.get_tab(tid)
            if any(k in (t.url or '') or k in (t.title or '') for k in keys):
                return t
        except Exception:
            pass
    return None


def arc_new_tab_after(page, before_ids, keys, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            tids = page.tab_ids
        except Exception:
            tids = []
        for tid in tids:
            if tid in before_ids:
                continue
            try:
                t = page.get_tab(tid)
                if any(k in (t.url or '') or k in (t.title or '') for k in keys):
                    return t
            except Exception:
                pass
        time.sleep(0.4)
    return None


def arc_find_frame(tab, names, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        for nm in names:
            for tagsel in (f'tag:frame@name={nm}', f'tag:iframe@name={nm}'):
                try:
                    fr = tab.ele(tagsel, timeout=0.5)
                    if fr:
                        return fr
                except Exception:
                    pass
        time.sleep(0.3)
    return None


def arc_get_main_doc2_tab(page, timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            tids = page.tab_ids
        except Exception:
            tids = []
        for tid in tids:
            try:
                t = page.get_tab(tid)
                if 'doc2' in (t.url or '') and t.ele('tag:frame@name=FUNL', timeout=0.5):
                    return t
            except Exception:
                pass
        time.sleep(0.5)
    return None


def arc_read_value(ele):
    try:
        return ele.run_js('return this.value')
    except Exception:
        return None


def arc_activate(tab):
    try:
        tab.set.activate()
    except Exception:
        pass
    try:
        tab.run_js("window.focus()")
    except Exception:
        pass


def arc_login_open_doc2(page, pin_code):
    page.get(ENTRY_URL)
    log_msg("登入中(第1次PIN)...")
    if page.ele('#txtpin', timeout=8):
        if not pin_fill(page.ele('#txtpin'), pin_code, desc="登入PIN"):
            raise RuntimeError("登入PIN輸入驗證失敗(疑瀏覽器記憶密碼干擾)，未送出登入")
        step_msg("點擊登入")
        arc_wait_click(page, '#btnLogIn', timeout=5) or arc_wait_click(page, 'text:登入', timeout=5)
    else:
        log_msg("   ! 沒看到 #txtpin，可能已登入。")
    log_msg("開啟二代公文...")
    link = page.ele("xpath://a[contains(@onclick,'ntpcdoc2-4')]", timeout=20)
    if link:
        try:
            link.click()
        except Exception:
            link.click(by_js=True)
    else:
        try:
            page.run_js("ntpcSsoOpen('ntpcdoc2-4')")
        except Exception:
            pass
    target = arc_get_main_doc2_tab(page, timeout=25)
    if not target:
        raise RuntimeError("找不到含 FUNL 的二代公文主視窗")
    log_msg(f"已進入二代公文: {target.url}")
    return target


def arc_sign_pending(page, target):
    log_msg("[簽收] 承辦人 -> 待簽收區 ...")
    try:
        fl = arc_find_frame(target, ["FUNL"], timeout=8)
        if fl:
            arc_wait_click(fl, 'text:承辦人', timeout=5)
            pace()
            step_msg("點『待簽收區』")
            arc_wait_click(fl, 'text:待簽收區', timeout=5)
        pace()
        fc = arc_find_frame(target, ["FUNC"], timeout=8)
        if not fc:
            log_msg("   ! 找不到 FUNC，略過簽收")
            return []
        try:
            fc.wait.eles_loaded('tag:tr', timeout=8)
        except Exception:
            pass
        picked = fc.run_js(JS_PICK_YJ)
        log_msg(f"   勾選已決: {picked}")
        if not picked:
            log_msg("   待簽收區無『已決』公文，略過簽收。")
            return []
        btn = fc.ele('#ctl00_MainPlace_bbtnReceive', timeout=5)
        if btn:
            step_msg("點『簽收』鈕")
            try:
                btn.click()
            except Exception:
                btn.click(by_js=True)
        else:
            log_msg("   X 找不到簽收鈕")
            return []
        ok = False
        end = time.time() + 15
        while time.time() < end:
            try:
                fc = arc_find_frame(target, ["FUNC"], timeout=2) or fc
                if fc.ele('text:簽收作業完成', timeout=1):
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(1)
        log_msg("   OK 簽收作業完成" if ok else "   ! 未確認簽收完成(仍繼續歸檔)")
        pace()
        return picked
    except Exception as e:
        log_msg(f"   ! 簽收略過: {e}")
        return []


def arc_goto_list_and_pick(target, processed):
    log_msg("切到『待辦理區』→『已決待歸』清單，找下一筆...")
    fl = arc_find_frame(target, ["FUNL"], timeout=8)
    if fl:
        arc_wait_click(fl, 'text:待辦理區', timeout=6)
    fc = arc_find_frame(target, ["FUNC"], timeout=8)
    if fc:
        arc_wait_click(fc, 'tag:input@@value:已決待歸', timeout=8)
        try:
            fc.wait.eles_loaded('tag:tr', timeout=8)
        except Exception:
            pass
        pace()
    fc = arc_find_frame(target, ["FUNC"], timeout=8)
    if not fc:
        return None, None
    for row in fc.eles('tag:tr'):
        txt = row.text.replace('\n', ' ')
        if '已決' in txt:
            a = row.ele('tag:a', timeout=0.3)
            if a and a.text.strip().isdigit() and a.text.strip() not in processed:
                return a, a.text.strip()
    return None, None


def arc_open_record_window(page, speed):
    for attempt in range(3):
        rec = arc_find_tab(page, REC_KEYS)
        if rec:
            return rec
        arc_activate(speed)
        pace()
        btn = speed.ele('text:核判存查', timeout=8)
        if not btn:
            log_msg("   X 找不到核判存查")
            return None
        step_msg("點『核判存查』")
        try:
            btn.click()
        except Exception:
            try:
                btn.click(by_js=True)
            except Exception:
                pass
        end = time.time() + 8
        while time.time() < end:
            rec = arc_find_tab(page, REC_KEYS)
            if rec:
                return rec
            time.sleep(0.5)
        log_msg(f"   ! 核判存查未開出錄檔視窗，重試({attempt + 1})")
        pace()
    return None


def arc_wait_success(speed, timeout=35):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if speed.ele('text:核判存查作業成功', timeout=1):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def arc_pin_dialog_open(speed):
    """ PIN 視窗是否還開著(可見)。True=開著 / False=已關 / None=讀不到 """
    try:
        return bool(speed.run_js(
            "var el=document.querySelector('#tempPinCode');"
            "if(!el) return false;"
            "var r=el.getBoundingClientRect();"
            "return r.width>0 && r.height>0;"))
    except Exception:
        return None


def arc_click_pin_confirm(speed):
    """ 點 PIN 視窗的『確定』(data-speed-action=PassingPinCode)。
        點完驗證視窗真的關掉，沒關就自動換招重試。
        只碰『確定』，絕不碰『我沒插卡』與『關閉』。 """
    strategies = [
        ('CDP點擊', lambda ele: ele.click()),
        ('JS click', lambda ele: ele.click(by_js=True)),
        ('JS滑鼠事件序列', lambda ele: ele.run_js(
            "var el=this;"
            "['mousedown','mouseup','click'].forEach(function(t){"
            "el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}));});")),
        ('jQuery trigger', lambda ele: ele.run_js(
            "if(window.jQuery){window.jQuery(this).trigger('click');}else{this.click();}")),
    ]
    try:
        speed.handle_alert(accept=True, timeout=0.5)
    except Exception:
        pass
    for name, fn in strategies:
        ele = speed.ele('@data-speed-action=PassingPinCode', timeout=3)
        if not ele:
            return arc_pin_dialog_open(speed) is False
        try:
            fn(ele)
        except Exception as e:
            log_msg(f"   ! [{name}] 點擊出錯: {e}")
        end = time.time() + 6
        while time.time() < end:
            try:
                if speed.ele('text:核判存查作業成功', timeout=0.5):
                    log_msg(f"   OK [{name}] 奏效(已出現成功訊息)")
                    return True
            except Exception:
                pass
            if arc_pin_dialog_open(speed) is False:
                log_msg(f"   OK [{name}] 奏效(PIN 視窗已關)")
                return True
            time.sleep(0.5)
        log_msg(f"   ! [{name}] 點了但 PIN 視窗沒關，換下一招...")
    return False


def arc_archive_one(page, link, doc_no, pin_code, class_no):
    log_msg(f"[歸檔] 處理公文 {doc_no} (分類號 {class_no}) ...")
    before = set(page.tab_ids)
    step_msg(f"點開公文 {doc_no} 詳情視窗")
    try:
        link.scroll.to_see()
        pace()
        link.click()
    except Exception:
        try:
            link.click(by_js=True)
        except Exception:
            pass
    speed = arc_new_tab_after(page, before, ['SUPERDESK', 'Super Desk'], timeout=20)
    if not speed:
        log_msg("   X 找不到新開的 SPEED 詳情視窗")
        return False
    try:
        speed.wait.doc_loaded(timeout=10)
    except Exception:
        pass
    step_msg("開啟『核判存查』錄檔視窗")
    rec = arc_open_record_window(page, speed)
    if not rec:
        log_msg("   X 核判存查多次未開出錄檔視窗")
        return False
    try:
        rec.wait.doc_loaded(timeout=8)
    except Exception:
        pass
    sel = rec.ele('#ctl00_SubPlace_cboFILE_CODE_drpCodeName', timeout=8)
    if not sel:
        log_msg("   X 找不到分類號下拉")
        return False
    step_msg(f"選擇歸檔分類號 {class_no}")
    try:
        sel.select.by_value(class_no)
    except Exception as e:
        log_msg(f"   X 選分類號失敗: {e}")
        return False
    filled = False
    for _ in range(16):
        y = arc_read_value(rec.ele('#ctl00_SubPlace_txtSAVE_YEAR', timeout=2))
        if y:
            filled = True
            break
        time.sleep(0.5)
    if not filled:
        log_msg("   ! 保存年限未自動帶出，仍嘗試確定")
    step_msg("點『錄檔確定』送出歸檔")
    if not arc_wait_click(rec, '#ctl00_SubPlace_bbtnSAVE', timeout=5, desc="錄檔確定"):
        log_msg("   X 點不到錄檔確定")
        return False
    pace()
    for ctx in (rec, page, speed):
        try:
            if ctx.handle_alert(accept=True):
                break
        except Exception:
            pass
    arc_activate(speed)
    pin_in = speed.ele('#tempPinCode', timeout=8)
    if pin_in:
        log_msg("   出現 PIN 視窗(當天第一次)，清空重打...")
        try:
            pin_in.clear()
        except Exception:
            pass
        pin_in.input(pin_code)
        val = arc_read_value(speed.ele('#tempPinCode', timeout=3))
        if val != pin_code:
            log_msg(f"   X PIN 核對失敗(讀到 {val!r})，中止避免鎖卡")
            return False
        log_msg("   PIN 已核對無誤，送出...")
        step_msg("點 PIN 視窗『確定』(點後驗證視窗有無關閉，最多換四招)")
        if not arc_click_pin_confirm(speed):
            log_msg("   X PIN 確定鈕四種點法都沒反應(視窗未關)，中止以策安全")
            return False
    else:
        log_msg("   未跳 PIN(當天已輸入過)，直接等結果。")
    log_msg("⏳ 等待『核判存查作業成功』訊息(最長 35 秒，請耐心)...")
    if not arc_wait_success(speed, timeout=35):
        log_msg("   X 未出現『核判存查作業成功』，中止以策安全")
        return False
    log_msg(f"   OK {doc_no} 歸檔成功")
    arc_wait_click(speed, 'text:關閉', timeout=4)
    time.sleep(1)
    try:
        speed.close()
    except Exception:
        pass
    time.sleep(1)
    return True


# ==========================================
# 🤖 執行緒管理 (修正版：無資料夾 + 覆蓋)
# ==========================================

def _looks_like_chrome_conn_error(e):
    """ 判斷是否為「連不上 Chrome」類錯誤 (握手/WebSocket/連線) """
    s = str(e).lower()
    keys = ['handshake', 'websocket', '404', 'cannot connect', 'connectionerror',
            'connection refused', 'browserconnect', 'failed to connect', 'no browser']
    return any(k in s for k in keys)

def _warn_chrome_conn():
    log_msg("⚠️ 連不上 Chrome：請關閉所有 Chrome 視窗後重試，或勾選「無頭模式」。")
    messagebox.showwarning(
        "無法連上 Chrome",
        "為確保系統正常運作，請擇一後重試：\n\n"
        "①  勾選「無頭模式（背景執行）」\n"
        "②  或先關閉所有 Chrome 視窗（含背景）再執行")

def run_automation_thread():
    # 下載模式 (2026/05/29 優化: 智慧等待取代死等; 二代公文用SSO連結)
    btn_start.tag_unbind("button", "<Button-1>")
    btn_start.set_text("⏳ 下載執行中...")
    is_headless = headless_var.get()
    pin_code = entry_pin.get().strip()
    base_path = entry_path.get().strip()

    if not pin_code or not os.path.exists(base_path):
        messagebox.showwarning("警告", "請檢查 PIN 碼或路徑！")
        btn_start.set_text("🚀 自動收文 (開始下載)")
        btn_start.tag_bind("button", "<Button-1>", btn_start.on_click)
        return

    save_settings(pin_code, base_path)
    download_path = base_path
    log_msg("🚀 啟動收文！(直接存於選擇的資料夾)")
    # 🔧 v17：印出實際使用的直譯器與套件狀態。
    # 一台電腦常裝多個 Python(例如 Anaconda 與 python.org 版)，
    # 在 A 裝套件、程式卻跑在 B，是最容易誤判的坑。
    log_msg(f"   直譯器: {sys.executable}")
    log_msg(f"   pdfplumber: {'已安裝' if PDFPLUMBER_OK else '✗ 未安裝(外部附件將無法偵測)'}")

    page = None
    try:
        co = ChromiumOptions()
        co.set_user_data_path(PROFILE_DIR)  # 乾淨設定檔：不跳選單、無記憶密碼
        quiet_chrome(co)
        co.headless(is_headless)
        co.set_download_path(download_path)
        co.set_pref('profile.default_content_settings.popups', 0)
        co.set_pref('download.prompt_for_download', False)
        co.set_pref('plugins.always_open_pdf_externally', True)
        page = ChromiumPage(co)
        if not is_headless:
            try:
                page.set.window.mini()
            except Exception:
                pass
        page.set.download_path(download_path)
        page.get(ENTRY_URL)

        if page.ele('#txtpin', timeout=8):
            if not pin_fill(page.ele('#txtpin'), pin_code, desc="登入PIN"):
                raise RuntimeError("登入PIN輸入驗證失敗(疑瀏覽器記憶密碼干擾)，未送出登入")
            step_msg("點擊登入")
            btn = page.ele('#btnLogIn') or page.ele('text:登入')
            if btn:
                btn.click()

        # 二代公文: 點帶 onclick 的 SSO 連結(非標題文字), 再等含 FUNL 的主視窗
        log_msg("開啟二代公文...")
        doc2_link = page.ele("xpath://a[contains(@onclick,'ntpcdoc2-4')]", timeout=20)
        if doc2_link:
            try:
                doc2_link.click()
            except Exception:
                doc2_link.click(by_js=True)
        else:
            try:
                page.run_js("ntpcSsoOpen('ntpcdoc2-4')")
            except Exception:
                pass

        target_tab = arc_get_main_doc2_tab(page, timeout=25)
        if not target_tab:
            raise Exception("找不到二代公文")

        # 承辦人 -> 待辦理區
        frame_left = target_tab.ele('tag:frame@name=FUNL', timeout=8)
        btn_contractor = frame_left.ele('tag:span@@text:承辦人') or frame_left.ele('text:承辦人')
        if btn_contractor:
            smart_click(btn_contractor)
            btn_process = frame_left.ele('text:待辦理區', timeout=6)
            if btn_process:
                btn_process.click()

        # 等公文清單(FUNC的承辦列)載入, 取代固定 sleep
        date_str = datetime.now().strftime("%m%d")
        frame_func = None
        for _ in range(24):
            try:
                frame_func = target_tab.ele('tag:frame@name=FUNC', timeout=1)
                if frame_func and frame_func.eles('tag:nobr@@text():承辦'):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not frame_func:
            frame_func = target_tab.ele('tag:frame@name=FUNC', timeout=5)

        # 🔧 v17 測試：原本只撈含「承辦」的 nobr，屬性「退」的公文不會被列入。
        doc_nobrs = collect_doc_nobrs(frame_func)
        total_count = len(doc_nobrs)
        log_msg(f"🧐 發現 {total_count} 筆公文...")

        for i in range(total_count):
            doc_idx = i + 1
            log_msg(f"--- 處理第 {doc_idx}/{total_count} 筆 ---")
            try:
                target_tab.run_js("window.focus()")
                frame_func = target_tab.ele('tag:frame@name=FUNC', timeout=5)
                current_nobrs = collect_doc_nobrs(frame_func, quiet=True)
                if len(current_nobrs) <= i:
                    continue

                target_nobr = current_nobrs[i]
                target_row = target_nobr.parent('tag:tr')
                subject_text = get_smart_subject(target_row)
                log_msg(f"📖 主旨: {subject_text[:15]}...")

                smart_click(target_nobr)

                # 等頁面刷新完成(避免 ContextLostError「頁面被刷新」)
                try:
                    target_tab.wait.doc_loaded(timeout=8)
                except Exception:
                    pass
                time.sleep(1.5)

                # 等詳情底框 #Foot 載入(容錯)
                frame_foot = None
                for _ in range(16):
                    try:
                        frame_foot = target_tab.ele('#Foot', timeout=1) or target_tab.ele('tag:frame@id=Foot', timeout=1)
                        if frame_foot:
                            break
                    except Exception:
                        pass
                    time.sleep(0.5)

                if frame_foot:
                    tab_file = frame_foot.ele('text:電子檔案', timeout=3)
                    if tab_file and tab_file.states.is_displayed:
                        smart_click(tab_file)
                        time.sleep(1)
                        # 等附件清單 iframe 載入(容錯)
                        iframe_detail = None
                        for _ in range(12):
                            try:
                                iframe_detail = frame_foot.ele('#iframeDetial', timeout=1)
                                if iframe_detail:
                                    break
                            except Exception:
                                pass
                            time.sleep(0.5)
                        if iframe_detail:
                            candidates = iframe_detail.eles('tag:a')
                            file_links = [l for l in candidates if l.text.strip() and l.text.strip()[0].isdigit() and "." in l.text.strip()]
                            file_counter = 1
                            for fl in file_links:
                                if file_counter == 1:
                                    clean_subj = clean_filename(subject_text, max_len=200)
                                    new_name = f"{date_str}-{doc_idx}-{file_counter}-{clean_subj}"
                                else:
                                    new_name = f"{date_str}-{doc_idx}-{file_counter}-附件"

                                # 🔧 v18: 不再「先刪舊檔 → 猜檔名去找」。
                                # 舊做法只要下載慢一點或 Chrome 改了名，就找不到檔案，
                                # 而舊檔已經先被刪掉 → 資料夾全空、外部附件偵測整段跳過。
                                # 改為監看資料夾「這次點擊後新增的檔案」，落地後我們自己改名。
                                log_msg(f"⬇️ 下載: {new_name}")
                                before_dl = set(os.listdir(download_path))
                                try:
                                    page.set.download_file_name(new_name)
                                except Exception:
                                    pass
                                time.sleep(0.5)
                                smart_click(fl)
                                try:
                                    page.wait.download_begin(timeout=15)
                                except Exception:
                                    pass

                                got = None
                                dl_end = time.time() + 40
                                while time.time() < dl_end:
                                    time.sleep(0.5)
                                    now_dl = set(os.listdir(download_path))
                                    if any(x.endswith(('.crdownload', '.tmp')) for x in now_dl):
                                        continue          # 還在下載
                                    fresh = [x for x in (now_dl - before_dl)
                                             if not x.endswith(('.crdownload', '.tmp'))]
                                    if not fresh:
                                        continue
                                    cpath = os.path.join(download_path, fresh[0])
                                    try:
                                        z1 = os.path.getsize(cpath)
                                        time.sleep(1)
                                        z2 = os.path.getsize(cpath)
                                    except OSError:
                                        continue
                                    if z1 > 0 and z1 == z2:
                                        got = cpath
                                        break

                                if not got:
                                    log_msg("   X 等不到檔案落地(Chrome 沒下載成功?)，略過此檔")
                                    file_counter += 1
                                    continue

                                ext_now = os.path.splitext(got)[1] or '.pdf'
                                want = os.path.join(download_path, new_name + ext_now)
                                if os.path.abspath(got) != os.path.abspath(want):
                                    try:
                                        os.replace(got, want)   # 有同名舊檔會直接覆蓋
                                    except OSError as e:
                                        log_msg(f"   ! 改名失敗({e})，沿用原檔名")
                                        want = got
                                log_msg(f"   OK 已存成 {os.path.basename(want)}")

                                if file_counter == 1:
                                    check_res = check_pdf_for_external_content(want)
                                    if check_res['found']:
                                        log_msg(f"🚨 發現外部附件！(文號:{check_res['doc_number']} 碼:{check_res['code']})")
                                        base_prefix = f"{date_str}-{doc_idx}-"
                                        if not (check_res['doc_number'] and check_res['code']):
                                            log_msg("   X 文號或驗證碼缺一，無法查詢附件下載區")
                                        ext_files = download_external_files_gui(check_res['doc_number'], check_res['code'], base_prefix, download_path)
                                        if ext_files:
                                            log_msg(f"   共取得 {len(ext_files)} 個外部附件，準備回填")
                                            upload_files_to_doc(page, target_row, ext_files)
                                            target_tab.run_js("window.focus()")
                                        else:
                                            log_msg("   X 外部附件一個都沒下載成功，略過回填")
                                file_counter += 1
                                time.sleep(1)
                    else:
                        log_msg("⚠️ 無附件")
            except Exception as e:
                log_msg(f"❌ 單筆失敗: {e}")
                continue
        log_msg("✅ 下載完成！")
        messagebox.showinfo("完成", f"公文已下載至：\n{download_path}")
    except Exception as e:
        if _looks_like_chrome_conn_error(e):
            log_msg(f"❌ 無法連上 Chrome: {e}")
            _warn_chrome_conn()
        else:
            log_msg(f"❌ 發生錯誤: {e}")
            messagebox.showerror("錯誤", f"執行失敗：\n{e}")
    finally:
        # 無頭模式看不到視窗, 結束時自動關閉, 避免背景殘留 Chrome 吃資源;
        # 有頭則保留視窗讓使用者檢查。
        if is_headless and page is not None:
            try:
                page.quit()
            except Exception:
                pass
        btn_start.set_text("🚀 自動收文 (開始下載)")
        btn_start.tag_bind("button", "<Button-1>", btn_start.on_click)

def run_archive_thread():
    # 簽收 + 歸檔 (2026/05/29 實測驗證版)
    btn_archive.tag_unbind("button", "<Button-1>")
    btn_archive.set_text("⏳ 歸檔執行中...")
    is_headless = headless_var.get()
    pin_code = entry_pin.get().strip()
    base_path = entry_path.get().strip()
    class_no = entry_class.get().strip()

    if not pin_code:
        messagebox.showwarning("警告", "請輸入 PIN 碼！")
        btn_archive.set_text("📂 自動歸檔 (簽收+存查)")
        btn_archive.tag_bind("button", "<Button-1>", btn_archive.on_click)
        return

    if not (class_no.isdigit() and len(class_no) == 4):
        messagebox.showwarning("警告", "歸檔分類號請輸入 4 位數字（例如 1199）！")
        btn_archive.set_text("📂 自動歸檔 (簽收+存查)")
        btn_archive.tag_bind("button", "<Button-1>", btn_archive.on_click)
        return

    save_settings(pin_code, base_path, class_no)
    log_msg(f"🚀 啟動簽收 + 歸檔！(分類號 {class_no})")

    page = None
    try:
        co = ChromiumOptions()
        co.set_user_data_path(PROFILE_DIR)  # 乾淨設定檔：不跳選單、無記憶密碼
        quiet_chrome(co)
        co.headless(is_headless)
        page = ChromiumPage(co)
        if not is_headless:
            try:
                page.set.window.max()
            except Exception:
                pass

        target = arc_login_open_doc2(page, pin_code)
        arc_sign_pending(page, target)

        processed = set()
        success = 0
        for i in range(50):
            target = arc_get_main_doc2_tab(page, timeout=15) or target
            link, doc_no = arc_goto_list_and_pick(target, processed)
            if not link:
                log_msg("沒有更多『已決待歸』公文。")
                break
            ok = arc_archive_one(page, link, doc_no, pin_code, class_no)
            processed.add(doc_no)
            if ok:
                success += 1
            else:
                log_msg("該筆未成功，為安全起見中止整個流程。")
                break

        log_msg(f"🏁 完成。成功歸檔 {success} 筆。")
        messagebox.showinfo("完成", f"自動歸檔完成！成功 {success} 筆。")

    except Exception as e:
        if _looks_like_chrome_conn_error(e):
            log_msg(f"❌ 無法連上 Chrome: {e}")
            _warn_chrome_conn()
        else:
            log_msg(f"❌ 歸檔失敗: {e}")
            messagebox.showerror("錯誤", f"歸檔失敗：\n{e}")
    finally:
        # 無頭模式結束時自動關閉瀏覽器, 避免背景殘留 Chrome; 有頭則保留供檢查。
        if is_headless and page is not None:
            try:
                page.quit()
            except Exception:
                pass
        btn_archive.set_text("📂 自動歸檔 (簽收+存查)")
        btn_archive.tag_bind("button", "<Button-1>", btn_archive.on_click)


def start_process():
    threading.Thread(target=run_automation_thread, daemon=True).start()

def start_archive_process():
    threading.Thread(target=run_archive_thread, daemon=True).start()

def dummy_browse():
    path = filedialog.askdirectory()
    if path:
        entry_path.delete(0, tk.END)
        entry_path.insert(0, path)

# ==========================================
# ⚙ 使用說明（右上角齒輪）
# ==========================================
HELP_TEXT = """【這個軟體在做什麼】

它就像一台「錄音播放機」：我事先把收文、歸檔要做的每一個步驟「錄製」下來，你按下按鈕，它就照著「播放」執行——自動登入、點擊、下載、簽收歸檔。

【操作四步驟】

1. 輸入 PIN 碼（自然人憑證卡密碼）

2. 選「儲存位置」（下載的公文要存的資料夾）

3. 按「🚀 自動收文」或「📂 自動歸檔」

4. 過程看黑底執行紀錄，完成會跳提示

【注意事項】

・「無頭模式」請勿勾選：背景模式讀不到自然人憑證，會登入失敗

・歸檔分類號預設 1199（其他），可自行修改

・PIN 一天只需輸入一次，之後自動略過

・Chrome 若跳「要更新密碼嗎」→ 按「不用了，謝謝」

【如果程式卡住了】

每個人的電腦配置、公文情境不完全相同，過程中可能遇到我沒「錄」過的預期外步驟，程式就會停在那裡。

遇到時請把畫面截圖傳給我，我會再增加軟體的彈性，讓它越用越聰明。
"""

def show_help():
    win = tk.Toplevel(root)
    win.title("使用說明")
    win.geometry("450x560")
    win.configure(bg=COLOR_PAGE)
    win.transient(root)
    try:
        win.iconbitmap(resource_path("icon.ico"))
    except Exception:
        pass
    txt = tk.Text(win, wrap="word", bg=COLOR_BG_WHITE, fg=COLOR_TEXT_MAIN,
                  font=("Microsoft JhengHei", 12), relief="flat",
                  padx=18, pady=14, bd=0)
    sb = tk.Scrollbar(win, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y", pady=14)
    txt.pack(fill="both", expand=True, padx=(14, 0), pady=14)
    txt.insert("1.0", HELP_TEXT)
    txt.configure(state="disabled")

# ==========================================
# 🖥️ 主視窗建置 (完全復刻原版風格)
# ==========================================
root = tk.Tk()
root.title("自動化公文小助手 · 新北市公務雲")
try:
    root.iconbitmap(resource_path("icon.ico"))
except Exception:
    pass

# 視窗寬度調整
root.geometry("560x860")  # 拉長視窗，log 區可看更多行
root.configure(bg=COLOR_PAGE)
root.withdraw()  # 先隱藏, 等 UI 建好、關掉 splash 後再顯示 (避免半成品視窗閃現)

# 載入設定
saved_settings = load_settings()

style = ttk.Style()
style.theme_use('clam')
style.configure("Magic.TButton", background=COLOR_BTN_BLUE, foreground=COLOR_BTN_TEXT, borderwidth=0, focuscolor='none')

# 圖片 (確認有 char_right.png 在同目錄)
TARGET_IMG_HEIGHT = 110
img_right_data = resize_image("char_right.png", TARGET_IMG_HEIGHT)

# --- A. 上方藍色標題帶 ---
top_frame = tk.Frame(root, bg=COLOR_HEADER_BLUE)
top_frame.pack(side="top", fill="x")

lbl_title = tk.Label(top_frame, text="自動化公文小助手",
                     font=("Microsoft JhengHei", 22, "bold"),
                     bg=COLOR_HEADER_BLUE, fg="white")
lbl_title.pack(pady=(15, 0))

lbl_subtitle = tk.Label(top_frame, text="新北市公務雲 · 精準濾網版",
                        font=("Microsoft JhengHei", 11),
                        bg=COLOR_HEADER_BLUE, fg=COLOR_SUBTITLE)
lbl_subtitle.pack(pady=(2, 16))

# 右上角 ⚙ 使用說明鈕
lbl_help = tk.Label(top_frame, text="⚙", font=("Segoe UI Emoji", 15),
                    bg=COLOR_HEADER_BLUE, fg="white", cursor="hand2")
lbl_help.place(relx=1.0, x=-16, y=10, anchor="ne")
lbl_help.bind("<Button-1>", lambda e: show_help())
lbl_help.bind("<Enter>", lambda e: lbl_help.config(fg=COLOR_SUBTITLE))
lbl_help.bind("<Leave>", lambda e: lbl_help.config(fg="white"))

# --- A2. 表單區 (灰底) ---
form_frame = tk.Frame(root, bg=COLOR_PAGE)
form_frame.pack(pady=(20, 4))

# PIN 碼
tk.Label(form_frame, text="PIN 碼：", bg=COLOR_PAGE, fg=COLOR_TEXT_MAIN, font=("Microsoft JhengHei", 14)).grid(row=0, column=0, sticky="e", padx=6, pady=7)
entry_pin = tk.Entry(form_frame, width=22, font=("Arial", 14), show="*", relief="solid", bd=1)
entry_pin.insert(0, saved_settings.get('pin', ''))
entry_pin.grid(row=0, column=1, sticky="ew", padx=6, pady=7, ipady=3)

# 路徑
tk.Label(form_frame, text="儲存位置：", bg=COLOR_PAGE, fg=COLOR_TEXT_MAIN, font=("Microsoft JhengHei", 14)).grid(row=1, column=0, sticky="e", padx=6, pady=7)
entry_path = tk.Entry(form_frame, width=22, font=("Arial", 14), relief="solid", bd=1)
entry_path.insert(0, saved_settings.get('download_path', ''))
entry_path.grid(row=1, column=1, sticky="ew", padx=6, pady=7, ipady=3)
btn_browse = RoundedButton(form_frame, text="瀏覽", command=dummy_browse,
                           width=76, height=36, radius=8,
                           bg_color=COLOR_PAGE, outline=True, text_color=COLOR_BTN2_TEXT)
btn_browse.grid(row=1, column=2, padx=6, pady=6)

# 歸檔分類號 (可自訂, 預設 1199)
tk.Label(form_frame, text="歸檔分類號：", bg=COLOR_PAGE, fg=COLOR_TEXT_MAIN, font=("Microsoft JhengHei", 14)).grid(row=2, column=0, sticky="e", padx=6, pady=7)
entry_class = tk.Entry(form_frame, width=8, font=("Arial", 14), relief="solid", bd=1, justify="center")
entry_class.insert(0, saved_settings.get('class_no', '1199'))
entry_class.grid(row=2, column=1, sticky="w", padx=6, pady=7, ipady=3)
tk.Label(form_frame, text="4 碼數字 · 預設 1199", bg=COLOR_PAGE, fg=COLOR_TEXT_SUB, font=("Microsoft JhengHei", 10)).grid(row=3, column=1, sticky="w", padx=6, pady=(0, 2))

# 無頭模式勾選框
headless_var = tk.BooleanVar()
headless_var.set(False) # 預設不勾選 (有頭)
chk_headless = tk.Checkbutton(form_frame, text="無頭模式 (背景執行)", variable=headless_var, bg=COLOR_PAGE, fg=COLOR_TEXT_SUB, font=("Microsoft JhengHei", 12), activebackground=COLOR_PAGE, activeforeground=COLOR_TEXT_SUB, selectcolor=COLOR_BG_WHITE)
chk_headless.grid(row=4, column=1, sticky="w", padx=(44, 6), pady=(8, 2))


# --- B. 按鈕區 (主 + 次) ---
btn_container = tk.Frame(root, bg=COLOR_PAGE, pady=14)
btn_container.pack(fill="x")

# 主按鈕: 收文 (實心海軍藍)
btn_start = RoundedButton(btn_container,
                          text="🚀  自動收文 (開始下載)",
                          command=start_process,
                          width=320, height=52,
                          bg_color=COLOR_PAGE)
btn_start.pack(pady=6)

# 次按鈕: 歸檔 (淺底邊框)
btn_archive = RoundedButton(btn_container,
                            text="📂  自動歸檔 (簽收+存查)",
                            command=start_archive_process,
                            width=320, height=52,
                            bg_color=COLOR_PAGE,
                            outline=True, text_color=COLOR_BTN2_TEXT)
btn_archive.pack(pady=6)

# 署名 (獨立頁尾, 靠視窗底部右側, 不擠在按鈕上)
footer = tk.Frame(root, bg=COLOR_PAGE)
footer.pack(side="bottom", fill="x", pady=(4, 10))
tk.Label(footer, text="Designed by 楊智琨", font=("Microsoft JhengHei", 9),
         bg=COLOR_PAGE, fg="#94A3B8").pack(side="right", padx=18)

# --- C. Log 區 ---
log_frame = tk.Frame(root, bg=COLOR_PAGE, padx=22)
log_frame.pack(fill="both", expand=True, pady=(0, 20))
log_head = tk.Frame(log_frame, bg=COLOR_PAGE)
log_head.pack(fill="x", pady=(0, 6))
tk.Label(log_head, text="執行紀錄", bg=COLOR_PAGE, fg=COLOR_TEXT_SUB, font=("Microsoft JhengHei", 13)).pack(side="left")
tk.Label(log_head, text="● 就緒", bg=COLOR_PAGE, fg="#16A34A", font=("Microsoft JhengHei", 11)).pack(side="right")

# 深色終端機 Log
log_text = tk.Text(log_frame, height=14, bg=COLOR_LOG_BG, fg=COLOR_LOG_FG,
                   insertbackground=COLOR_LOG_FG, font=("Consolas", 13),
                   relief="flat", padx=12, pady=10, bd=0)
log_text.pack(fill="both", expand=True)
log_text.insert(tk.END, "> 系統就緒，等待指令\n")

# 關閉 PyInstaller 載入圖 (splash)；僅打包版有 pyi_splash，直接跑 .py 會略過
try:
    import pyi_splash
    pyi_splash.close()
except Exception:
    pass

root.deiconify()  # 顯示已建好的視窗
root.mainloop()