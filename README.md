# taiko_filter — 太鼓の達人曲目篩選器

依 **類型 (genre)** 與 **難易度 (difficulty)** 篩選曲目，依難度 (★) 排序，
輸出曲名與其在 [taiko.wiki](https://taiko.wiki/) 上的連結。

## 資料來源

taikowiki 官方專案：

- 全曲 API：`GET https://taiko.wiki/api/v1/song/all`
- 曲目頁面：`https://taiko.wiki/song/{songNo}?lang=zh-tw`
- 離線鏡像：taiko-song-database（GitHub，每日 15:00 UTC 更新）

程式會依 **官方 API → GitHub 鏡像 → 本地檔** 的順序自動取得資料，任一可用即可。

## 對應表（見專案 `類型.png` / `難易度.png`）

| 類型 | 代碼 | | 難易度 | 代碼 |
|------|------|-|--------|------|
| 流行音樂 | `pops` | | 簡單 | `easy` |
| 動畫 | `anime` | | 普通 | `normal` |
| 兒童 | `kids` | | 困難 | `hard` |
| VOCALOID™ | `vocaloid` | | 魔鬼(表) | `oni` |
| 遊戲音樂 | `game` | | 魔鬼(裏) | `ura` |
| 南科原創 | `namco` | | | |
| 綜藝 | `variety` | | ★ 星等 | `courses[難度].level`（1–10）|
| 古典 | `classic` | | | |

中文標籤或代碼皆可輸入。

## 需求

Python 3.9+，無第三方套件（只用標準函式庫）。

## 用法

```bash
# VOCALOID + 魔鬼(表)，全部星等
python taiko_filter.py --genre VOCALOID™ --difficulty "魔鬼(表)"

# 遊戲音樂 + 困難，只要 ★6，輸出 Markdown
python taiko_filter.py -g 遊戲音樂 -d 困難 --level 6 --format md

# 多類型 × 多難度，★7~9，輸出 CSV 檔
python taiko_filter.py -g pops,anime -d oni,ura --min-level 7 --max-level 9 \
                       --format csv -o result.csv

# 不連網，使用本地快照
python taiko_filter.py -g 古典 -d oni --offline database.json
```

## 主要參數

| 參數 | 說明 |
|------|------|
| `-g, --genre` | 類型（逗號分隔多選；不指定 = 全部類型） |
| `-d, --difficulty` | 難易度（逗號分隔多選；不指定 = 全部難度） |
| `--level N` | 精確星等，等同 `--min-level N --max-level N` |
| `--min-level` / `--max-level` | 星等範圍 |
| `--lang` | 連結語系 `en/ja/ko/zh-tw/zh-cn`（預設 `zh-tw`） |
| `--format` | `table`(預設)`/md/csv/json` |
| `-o, --output` | 輸出檔路徑 |
| `--offline` | 使用本地 `database.json` |
| `--include-deleted` | 納入已下架曲目 |
| `-q, --quiet` | 靜默模式 |

## 排序邏輯

先依 **★ 星等** 由低到高，同星等再依 **難度階級**（易→難），最後依 **曲名**。
一首曲的每個符合難度各自成為一列（例如同時勾選表/裏會各列一次）。

## 授權

`太鼓の達人™` 為 Bandai Namco Entertainment 之商標；曲目與譜面著作權屬各權利人。
本工具僅串接 taikowiki 公開資料，與 Bandai Namco 無關。

---

## 圖形介面 (GUI)

除 CLI 外，另附 `taiko_gui.py`（Tkinter 桌面視窗，須與 `taiko_filter.py` 同資料夾）。

```bash
python taiko_gui.py
```

操作：以彩色鈕多選類型與難易度 → 拖 ★ 星等雙滑桿設範圍 → 按「篩選」→
結果表格雙擊任一列即用瀏覽器開啟該曲 taiko.wiki 頁；下方可一鍵匯出 CSV / JSON / Markdown。

- **需求**：Python 3.9+；Tkinter（Windows / macOS 內建，多數 Linux 需
  `sudo apt install python3-tk`）。無其他第三方套件。
- 啟動時自動走「官方 API → 線上鏡像 → 本地 database.json」載入資料。
