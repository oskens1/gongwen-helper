# -*- coding: utf-8 -*-
"""
pin_probe.py — 唯讀偵察腳本
【安全性】只讀取頁面結構，不點任何按鈕、不輸入任何文字、不碰 PIN。

用途：PIN 視窗開著的時候執行，把視窗的真實 DOM 結構抓下來，
     存成「PIN偵察報告.txt」，用來診斷為什麼程式點不到「確定」。
用法：雙擊 pin_probe.bat（或 python pin_probe.py）
"""
import json
import datetime

OUT = 'PIN偵察報告.txt'
L = []


def w(s=''):
    s = str(s)
    print(s)
    L.append(s)


SCAN_JS = r"""
function scanDoc(doc, path, out){
    try{
        var pin = doc.querySelector('#tempPinCode');
        var actions = [];
        doc.querySelectorAll('[data-speed-action]').forEach(function(el){
            var r = el.getBoundingClientRect();
            var st = el.ownerDocument.defaultView.getComputedStyle(el);
            actions.push({
                tag: el.tagName,
                action: el.getAttribute('data-speed-action'),
                text: (el.innerText || el.value || '').trim().slice(0,40),
                id: el.id || '',
                cls: (el.className || '').toString().slice(0,60),
                visible: (r.width>0 && r.height>0 && st.display!=='none' && st.visibility!=='hidden'),
                rect: [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],
                disabled: el.disabled === true,
                onclick: (el.getAttribute('onclick')||'').slice(0,150)
            });
        });
        var btns = [];
        doc.querySelectorAll('button, input[type=button], input[type=submit], a, span, div').forEach(function(el){
            var txt = (el.innerText || el.value || '').trim();
            if(txt.length>0 && txt.length<12 && /(確定|我沒插卡|關閉|送出|OK)/.test(txt)){
                if(el.children.length>2) return;  // 避免整個容器都進來
                var r = el.getBoundingClientRect();
                btns.push({
                    tag: el.tagName, text: txt.slice(0,20), id: el.id||'',
                    cls: (el.className||'').toString().slice(0,60),
                    attrs: Array.from(el.attributes).map(function(a){return a.name+'='+String(a.value).slice(0,40);}).join(' | ').slice(0,300),
                    rect: [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)]
                });
            }
        });
        var dialogHTML = null;
        if(pin){
            var node = pin, up = 0;
            while(node.parentElement && up < 6){
                node = node.parentElement; up++;
                var cls = (node.className||'').toString();
                if(/modal|dialog|popup|layer|window/i.test(cls)) break;
            }
            dialogHTML = node.outerHTML.slice(0, 6000);
        }
        out.push({
            path: path, hasPin: !!pin,
            pinVisible: pin ? (function(){var r=pin.getBoundingClientRect();return r.width>0&&r.height>0;})() : null,
            pinValueLen: pin ? (pin.value||'').length : null,
            actions: actions, btns: btns, dialogHTML: dialogHTML
        });
    }catch(e){
        out.push({path: path, error: String(e)});
    }
    var frames = doc.querySelectorAll('iframe, frame');
    for(var i=0;i<frames.length;i++){
        var f = frames[i];
        var p = path + ' > iframe[' + i + '](name=' + (f.name||'') + ', id=' + (f.id||'') + ')';
        try{
            if(f.contentDocument) scanDoc(f.contentDocument, p, out);
            else out.push({path: p, error: '跨網域 iframe，讀不到'});
        }catch(e){ out.push({path: p, error: String(e)}); }
    }
}
var out = [];
scanDoc(document, 'top', out);
return JSON.stringify(out);
"""


def main():
    w('=== PIN 視窗偵察報告 ===')
    w('時間: %s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    try:
        from DrissionPage import ChromiumPage
    except ImportError:
        w('X 沒裝 DrissionPage：pip install DrissionPage')
        return
    try:
        page = ChromiumPage()
    except Exception as e:
        w('X 連不上 Chrome(9222): %s' % e)
        w('  請確認公文小助手用的那個 Chrome 視窗還開著。')
        return
    w('分頁數: %d' % len(page.tab_ids))
    hit = 0
    for tid in page.tab_ids:
        try:
            t = page.get_tab(tid)
            url = (t.url or '')[:100]
            title = (t.title or '')[:50]
        except Exception as e:
            w('- (讀不到分頁 %s: %s)' % (tid, e))
            continue
        w('')
        w('--- 分頁: %s | %s' % (title, url))
        try:
            raw = t.run_js(SCAN_JS)
            data = json.loads(raw)
        except Exception as e:
            w('  X 掃描失敗: %s' % e)
            continue
        for d in data:
            if d.get('error'):
                w('  [%s] error: %s' % (d['path'], d['error']))
                continue
            if not d['hasPin'] and not d['actions'] and not d['btns']:
                continue
            w('  [%s]' % d['path'])
            w('    #tempPinCode: %s (可見=%s, 已填字數=%s)' % (d['hasPin'], d.get('pinVisible'), d.get('pinValueLen')))
            if d['hasPin']:
                hit += 1
            for a in d['actions']:
                w('    <data-speed-action> %s' % json.dumps(a, ensure_ascii=False))
            for b in d['btns']:
                w('    <候選按鈕> %s' % json.dumps(b, ensure_ascii=False))
            if d.get('dialogHTML'):
                w('    --- 對話框 HTML ---')
                w(d['dialogHTML'])
                w('    --- HTML 結束 ---')
    w('')
    w('找到 #tempPinCode 的文件數: %d' % hit)
    if hit == 0:
        w('! PIN 視窗可能已經關掉了。下次它跳出來時再跑一次本腳本即可。')


if __name__ == '__main__':
    main()
    try:
        with open(OUT, 'w', encoding='utf-8') as f:
            f.write('\n'.join(L))
        print('\n已存檔: %s' % OUT)
    except Exception as e:
        print('存檔失敗: %s' % e)
    input('\n按 Enter 結束...')
