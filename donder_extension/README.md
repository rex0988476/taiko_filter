# Donder → taiko_filter 匯出擴充 — 安裝與使用說明

在你**已登入的 donderhiroba 頁面**上執行的瀏覽器擴充，一鍵把遊玩成績
（通關 / 全連 FC / 全良）匯出成 `marks.json`，供 taiko_filter 使用。

因為擴充是在 `donderhiroba.jp` 頁面內以你的登入身分發送同源請求，
**不需要解密任何 cookie、也沒有 CORS 問題**，比讀取本機 cookie 可靠得多。

---

## 一、檔案位置

```
donder_extension/
├── manifest.json
└── content.js
```

---

## 二、安裝（Chrome / Edge / Brave 等 Chromium 瀏覽器）

1. 開啟擴充管理頁：
   - Chrome：網址列輸入 `chrome://extensions`
   - Edge：網址列輸入 `edge://extensions`
2. 打開右上角（Edge 在左下角）的 **開發人員模式 / Developer mode**。
3. 按 **載入未封裝項目 / Load unpacked**。
4. 選擇資料夾：
   ```
   c:\Users\user\Desktop\taiko_filter\donder_extension
   ```
5. 清單中出現「Donder → taiko_filter 匯出」即安裝完成。

> 更新程式後（例如 `git pull`），回到擴充管理頁按該擴充的**重新整理 / Reload**
> 圖示即可套用新版。

---

## 三、使用

1. 用**同一個瀏覽器**登入 <https://donderhiroba.jp> 並選好卡片（太鼓番）。
2. 頁面右下角會出現綠色按鈕 **「⬇ 匯出成績 marks.json」**，點它。
3. 擴充會依序：
   - 刷新成績快取（`update_score.php`）
   - 抓取 8 個曲風的成績頁（`score_list.php?genre=1..8`）
   - 解析每首歌每難度的冠色
   - **下載 `marks.json`**
4. 按鈕上方會顯示「掃描 N 筆記錄，匯出 M 個標記」。

---

## 四、冠色對應規則

| donderhiroba 冠色 | taiko_filter 標記 |
|-------------------|-------------------|
| 虹冠（全良）       | `perfect`（全良）  |
| 金冠（全連）       | `fc`（FC）         |
| 銀冠（通關）       | 略過（目前無對應狀態）|

難度對應：`easy=1、normal=2、hard=3、oni=4、ura=5`。

> 「快全良（剩 N 可）」需逐首另抓 `score_detail`，此版本未包含。

---

## 五、匯出後怎麼用

下載到的 `marks.json` 就是 taiko_filter 的標記格式：

```json
{ "1512|oni": { "status": "fc" }, "883|ura": { "status": "perfect" } }
```

- **本地 GUI**：把檔案覆蓋到
  `c:\Users\user\Desktop\taiko_filter\marks.json`，
  開啟 `taiko_gui.py`（或重新篩選）即可看到全良／FC 底色。
- **線上網站**：覆蓋後於專案資料夾執行 `.\push.ps1`，約 1～2 分鐘後
  <https://rex0988476.github.io/taiko_filter/> 同步更新。

> ⚠️ 直接覆蓋會蓋掉你**手動標記的「快全良(剩 N 可)」**。若要保留，
> 請先備份原本的 `marks.json`。

---

## 六、疑難排解

- **看不到按鈕**：確認網址在 `https://donderhiroba.jp/*`、擴充已啟用；
  重新整理頁面。
- **匯出 0 個標記**：多半是尚未登入或未選卡片；請先登入並選卡片。
- **掃描有數字但匯出 0**：代表冠色圖檔名與預期不同。把某首歌的冠圖網址
  （對圖片按右鍵 → 複製圖片網址）提供出來，即可依實際檔名調整解析規則。

---

## 七、說明與免責

- 本擴充僅讀取**你自己帳號**可見的成績並在本機下載，不上傳任何資料、
  不寫入其他檔案。
- 屬非官方工具，與 Bandai Namco 無關；此類自動化操作可能違反
  donderhiroba 使用條款，使用風險自負。
