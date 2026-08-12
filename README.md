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

- `gongwen_helper.py`：最新版原始碼（目前為 v17）
- `requirements.txt`：Python 相依套件
- `icon.ico`：程式圖示
- GitHub Releases：已封裝、可直接使用的 Windows 版本

## 版本

v17 修正外部附件下載等 9 項問題，封裝版自帶 VC runtime，免另裝相依套件。

## 授權

本專案採用 [MIT License](LICENSE)，歡迎下載、研究、修改與改良。

本工具為個人開源專案，並非新北市政府官方軟體。公務系統頁面若改版，自動化功能可能需要跟著調整。
