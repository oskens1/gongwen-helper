# -*- coding: utf-8 -*-
"""
pin_click_now.py — 一次性實測腳本
對「目前開著、PIN 已填好」的 PIN 視窗執行四招點擊(同主程式新邏輯)，
回報哪一招奏效。只點『確定』，絕不碰『我沒插卡』與『關閉』。

【注意】這會真的送出 PIN、完成該筆核判存查。PIN 欄位若未填滿 6 碼會直接中止，不會亂按。
"""
import time


def pin_dialog_open(tab):
    try:
        return bool(tab.run_js(
            "var el=document.querySelector('#tempPinCode');"
            "if(!el) return false;"
            "var r=el.getBoundingClientRect();"
            "return r.width>0 && r.height>0;"))
    except Exception:
        return None


def main():
    from DrissionPage import ChromiumPage
    page = ChromiumPage()
    target = None
    for tid in page.tab_ids:
        try:
            t = page.get_tab(tid)
            if pin_dialog_open(t):
                target = t
                break
        except Exception:
            pass
    if not target:
        print('X 沒有找到開著的 PIN 視窗，結束(什麼都沒做)。')
        return
    print('找到 PIN 視窗分頁:', (target.title or '')[:50])

    n = target.run_js(
        "var el=document.querySelector('#tempPinCode');"
        "return el ? (el.value||'').length : 0;")
    print('PIN 欄位已填字數:', n)
    if not n or int(n) < 6:
        print('X PIN 欄位未填滿 6 碼，中止以策安全(不點任何按鈕)。')
        return

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
        target.handle_alert(accept=True, timeout=0.5)
    except Exception:
        pass
    winner = None
    for name, fn in strategies:
        ele = target.ele('@data-speed-action=PassingPinCode', timeout=3)
        if not ele:
            if pin_dialog_open(target) is False:
                winner = name + '(按鈕已消失=視窗已關)'
                break
            print('X 找不到確定鈕，中止。')
            return
        print('嘗試 [%s] ...' % name)
        try:
            fn(ele)
        except Exception as e:
            print('  ! 點擊出錯:', e)
        end = time.time() + 6
        while time.time() < end:
            try:
                if target.ele('text:核判存查作業成功', timeout=0.5):
                    winner = name + '(出現成功訊息)'
                    break
            except Exception:
                pass
            if pin_dialog_open(target) is False:
                winner = name + '(視窗已關)'
                break
            time.sleep(0.5)
        if winner:
            break
        print('  ! [%s] 沒反應，換下一招' % name)

    if not winner:
        print('X 四招都沒用，PIN 視窗仍開著。請截圖回報。')
        return
    print('==> 奏效的招式：', winner)
    print('等待「核判存查作業成功」訊息(最多 35 秒)...')
    end = time.time() + 35
    while time.time() < end:
        try:
            if target.ele('text:核判存查作業成功', timeout=1):
                print('OK 核判存查作業成功！該筆歸檔完成。')
                return
        except Exception:
            pass
        time.sleep(1)
    print('! 視窗關了但 35 秒內沒看到成功訊息，請自行到系統確認該筆狀態。')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('X 執行失敗:', e)
    input('\n按 Enter 結束...')
