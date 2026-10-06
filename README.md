# 公文小助手

協助新北市公務雲進行收文、附件下載、簽收與歸檔的桌面工具。

## 直接下載

不需要安裝 Python，下載並解壓縮後，執行 `gongwen_helper.exe`：

**[下載最新版（Windows ZIP）](https://github.com/oskens1/gongwen-helper/releases/latest/download/gongwen-helper.zip)**

使用前請先安裝 [Google Chrome](https://www.google.com/chrome/)。請保留解壓縮後的完整資料夾；不要只移動 EXE，程式需要同資料夾內的 `_internal`。

## 從原始碼執行

需求：Windows、Python 3.10+、Google Chrome。

```powershell
python -m pip install -r requirements.txt
python gongwen_helper.py
```

程式第一次使用時會在本機建立 `settings.json`。此檔可能包含自然人憑證 PIN，已由 `.gitignore` 排除，請勿分享或提交。

## 專案檔案

- `gongwen_helper.py`：最新版原始碼（目前為 v18）
- `requirements.txt`：Python 相依套件
- `icon.ico`：程式圖示
- GitHub Releases：已封裝、可直接使用的 Windows 版本

## v18（2026/10/06）

新增「收文身分」：組長選「承辦人」，主任選「主管作業」，再按「自動收文」。主任模式依選單層級尋找待辦理區，使用文號連結辨識公文，不限定承辦／核稿／決行文字。

自動歸檔仍是原承辦人的簽收＋存查流程，不提供主任核稿或決行功能。主任實際帳號尚待使用者測試；若無法辨識選單或清單，程式會停止提示。

封裝採乾淨 CPython 環境、onedir、不用 UPX，包含 Python、VC runtime 與 Tcl/Tk，不需另裝 Python。已通過 GUI、PDF 抽取／渲染、原生 DLL 相依檢查，以及清除 Python／Conda 環境後的中文路徑搬移測試；這不等於乾淨 Windows 他機或主任帳號驗證。

操作及重建方式見 [使用說明](使用說明.md)。來源相依鎖定於 `requirements-lock.txt`；`build_v18.py` 先建 console 驗證，再建 windowed 正式版。

v17 修正外部附件下載等 9 項問題，舊版仍保留於 Releases。

## 授權

本專案採用 [MIT License](LICENSE)，歡迎下載、研究、修改與改良。

本工具為個人開源專案，並非新北市政府官方軟體。公務系統頁面若改版，自動化功能可能需要跟著調整。
