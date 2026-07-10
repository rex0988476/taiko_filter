#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
taiko_filter.py
================
依「類型 (genre)」與「難易度 (difficulty)」篩選《太鼓の達人》曲目，
依難度 (★ level) 排序，輸出曲名與其在 taiko.wiki 上的連結。

資料來源
--------
taiko.wiki 官方 API（taikowiki 專案）：
  - 全曲資料 : GET https://taiko.wiki/api/v1/song/all
  - 曲目頁面 : https://taiko.wiki/song/{songNo}?lang=zh-tw
若無法連線，會自動改用 taiko-song-database (GitHub) 的鏡像資料，
或使用者以 --offline 指定的本地 database.json。

對應（見專案 files 中 類型.png / 難易度.png）
-------------------------------------------------
類型 (genre)                難易度 (difficulty)
  流行音樂  -> pops           簡單      -> easy
  動畫      -> anime          普通      -> normal
  兒童      -> kids           困難      -> hard
  VOCALOID™ -> vocaloid       魔鬼(表)  -> oni
  遊戲音樂  -> game           魔鬼(裏)  -> ura
  南科原創  -> namco
  綜藝      -> variety        ★ 星等   -> courses[difficulty].level (1–10)
  古典      -> classic

用法範例
--------
  # VOCALOID + 魔鬼(表)，全部星等，依難度排序
  python taiko_filter.py --genre VOCALOID™ --difficulty 魔鬼\(表\)

  # 遊戲音樂 + 困難，只要 ★6，輸出成 Markdown
  python taiko_filter.py --genre 遊戲音樂 --difficulty 困難 --level 6 --format md

  # 多類型 + 多難度，星等 7~9，離線資料
  python taiko_filter.py -g pops,anime -d oni,ura --min-level 7 --max-level 9 \
                         --offline database.json --format csv -o out.csv

作者：為碩士研究用途撰寫，資料版權屬 Bandai Namco Entertainment 及各權利人。
"""

import argparse
import csv
import json
import sys
import urllib.request
import urllib.error
from typing import Any, Optional

# --------------------------------------------------------------------------- #
#  常數與對應表
# --------------------------------------------------------------------------- #

API_ALL_SONGS = "https://taiko.wiki/api/v1/song/all"
# taiko-song-database 每日 15:00 UTC 更新，作為 API 無法連線時的鏡像
DB_MIRROR = ("https://raw.githubusercontent.com/taikowiki/"
             "taiko-song-database/master/database.json")
SONG_PAGE = "https://taiko.wiki/song/{songNo}"

# 類型：中文標籤（含常見別名）-> 內部代碼
GENRE_MAP = {
    "流行音樂": "pops", "流行": "pops", "pops": "pops", "pop": "pops",
    "動畫": "anime", "動漫": "anime", "anime": "anime",
    "兒童": "kids", "童謠": "kids", "kids": "kids",
    "vocaloid™": "vocaloid", "vocaloid": "vocaloid", "vocal": "vocaloid",
    "遊戲音樂": "game", "遊戲": "game", "game": "game",
    "南科原創": "namco", "namco原創": "namco", "namco": "namco",
    "綜藝": "variety", "variety": "variety",
    "古典": "classic", "classic": "classic", "classical": "classic",
}
GENRE_LABEL = {  # 內部代碼 -> 顯示用中文
    "pops": "流行音樂", "anime": "動畫", "kids": "兒童", "vocaloid": "VOCALOID™",
    "game": "遊戲音樂", "namco": "南科原創", "variety": "綜藝", "classic": "古典",
}

# 難易度：中文標籤（含常見別名）-> 內部代碼
DIFF_MAP = {
    "簡單": "easy", "easy": "easy", "kantan": "easy",
    "普通": "normal", "normal": "normal", "futsuu": "normal",
    "困難": "hard", "hard": "hard", "muzukashii": "hard",
    "魔鬼(表)": "oni", "魔鬼（表）": "oni", "魔鬼表": "oni",
    "魔鬼": "oni", "oni": "oni", "鬼": "oni",
    "魔鬼(裏)": "ura", "魔鬼（裏）": "ura", "魔鬼裏": "ura",
    "裏": "ura", "ura": "ura", "裏鬼": "ura",
}
DIFF_LABEL = {  # 內部代碼 -> 顯示用中文
    "easy": "簡單", "normal": "普通", "hard": "困難",
    "oni": "魔鬼(表)", "ura": "魔鬼(裏)",
}
# 難易度排序權重（易 -> 難）
DIFF_ORDER = {"easy": 0, "normal": 1, "hard": 2, "oni": 3, "ura": 4}


# --------------------------------------------------------------------------- #
#  資料載入
# --------------------------------------------------------------------------- #

def _fetch_json(url: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "taiko-filter/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_songs(offline: Optional[str] = None, verbose: bool = True) -> list[dict]:
    """
    載入曲目資料，優先順序：
      1. --offline 指定的本地檔
      2. taiko.wiki 官方 API
      3. taiko-song-database (GitHub) 鏡像
    """
    if offline:
        if verbose:
            print(f"[i] 使用本地資料：{offline}", file=sys.stderr)
        with open(offline, "r", encoding="utf-8") as f:
            return json.load(f)

    for label, url in (("官方 API", API_ALL_SONGS), ("GitHub 鏡像", DB_MIRROR)):
        try:
            if verbose:
                print(f"[i] 嘗試從 {label} 取得資料：{url}", file=sys.stderr)
            data = _fetch_json(url)
            if isinstance(data, dict) and "data" in data:  # API 可能包一層
                data = data["data"]
            if verbose:
                print(f"[i] 成功載入 {len(data)} 首曲目（{label}）", file=sys.stderr)
            return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if verbose:
                print(f"[!] {label} 失敗：{exc}", file=sys.stderr)

    raise SystemExit("[x] 無法取得曲目資料，請檢查網路或改用 --offline 指定本地檔。")


# --------------------------------------------------------------------------- #
#  解析使用者輸入
# --------------------------------------------------------------------------- #

def parse_genres(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    codes = []
    for token in raw.split(","):
        key = token.strip().lower()
        # 中文不受 lower 影響；英文別名以小寫比對
        code = GENRE_MAP.get(token.strip()) or GENRE_MAP.get(key)
        if not code:
            raise SystemExit(f"[x] 未知的類型：'{token.strip()}'。"
                             f"可用：{'、'.join(GENRE_LABEL.values())}")
        codes.append(code)
    return list(dict.fromkeys(codes))  # 去重、保序


def parse_difficulties(raw: Optional[str]) -> list[str]:
    if not raw:
        return list(DIFF_ORDER.keys())  # 未指定 -> 全部難度
    codes = []
    for token in raw.split(","):
        key = token.strip().lower().replace(" ", "")
        code = DIFF_MAP.get(token.strip()) or DIFF_MAP.get(key)
        if not code:
            raise SystemExit(f"[x] 未知的難易度：'{token.strip()}'。"
                             f"可用：{'、'.join(DIFF_LABEL.values())}")
        codes.append(code)
    return list(dict.fromkeys(codes))


# --------------------------------------------------------------------------- #
#  篩選核心
# --------------------------------------------------------------------------- #

def build_rows(songs: list[dict],
               genres: list[str],
               difficulties: list[str],
               min_level: Optional[int],
               max_level: Optional[int],
               lang: str,
               include_deleted: bool) -> list[dict]:
    """
    產生「一首曲 × 一個難度」為單位的結果列。
    每列包含：songNo、title、romaji、genre、difficulty、level、url。
    """
    rows: list[dict] = []
    genre_set = set(genres)

    for s in songs:
        if not include_deleted and s.get("isDeleted"):
            continue
        song_genres = s.get("genre") or []
        # 類型篩選：曲目任一類型命中即可（未指定類型 -> 全收）
        if genre_set and not (genre_set & set(song_genres)):
            continue

        courses = s.get("courses") or {}
        for diff in difficulties:
            course = courses.get(diff)
            if not course:          # 該難度不存在（例如多數曲目沒有 ura）
                continue
            level = course.get("level")
            if level is None:
                continue
            if min_level is not None and level < min_level:
                continue
            if max_level is not None and level > max_level:
                continue

            song_no = s.get("songNo")
            url = SONG_PAGE.format(songNo=song_no)
            if lang:
                url += f"?lang={lang}"
            # 顯示用類型（取曲目與所選類型的交集，否則取全部）
            shown = [g for g in song_genres if not genre_set or g in genre_set]
            rows.append({
                "songNo": song_no,
                "title": s.get("title") or s.get("titleEn") or s.get("romaji") or "",
                "romaji": s.get("romaji") or "",
                "genres": shown or song_genres,
                "difficulty": diff,
                "level": level,
                "url": url,
            })

    # 依難度排序：先 level（星等），再難度階級，再曲名
    rows.sort(key=lambda r: (r["level"], DIFF_ORDER.get(r["difficulty"], 99),
                             r["title"]))
    return rows


# --------------------------------------------------------------------------- #
#  輸出
# --------------------------------------------------------------------------- #

def genre_label(codes: list[str]) -> str:
    return "、".join(GENRE_LABEL.get(c, c) for c in codes)


def output_table(rows: list[dict]) -> None:
    if not rows:
        print("（無符合條件的曲目）")
        return
    print(f"{'★':<3} {'難度':<8} {'類型':<12} {'曲名'}")
    print("-" * 78)
    for r in rows:
        stars = f"★{r['level']}"
        diff = DIFF_LABEL.get(r["difficulty"], r["difficulty"])
        gnr = "/".join(GENRE_LABEL.get(g, g) for g in r["genres"])
        print(f"{stars:<4}{diff:<9}{gnr:<13}{r['title']}")
        print(f"{'':<4}{'':<9}{'':<13}{r['url']}")
    print("-" * 78)
    print(f"共 {len(rows)} 筆")


def output_markdown(rows: list[dict]) -> str:
    lines = ["| ★ | 難度 | 類型 | 曲名 | 連結 |",
             "|---|------|------|------|------|"]
    for r in rows:
        diff = DIFF_LABEL.get(r["difficulty"], r["difficulty"])
        gnr = "/".join(GENRE_LABEL.get(g, g) for g in r["genres"])
        title = r["title"].replace("|", "\\|")
        lines.append(f"| ★{r['level']} | {diff} | {gnr} | {title} | "
                     f"[開啟]({r['url']}) |")
    lines.append(f"\n_共 {len(rows)} 筆_")
    return "\n".join(lines)


def output_csv(rows: list[dict], fp) -> None:
    w = csv.writer(fp)
    w.writerow(["songNo", "level", "difficulty", "difficulty_zh",
                "genres", "title", "romaji", "url"])
    for r in rows:
        w.writerow([r["songNo"], r["level"], r["difficulty"],
                    DIFF_LABEL.get(r["difficulty"], r["difficulty"]),
                    "/".join(r["genres"]), r["title"], r["romaji"], r["url"]])


def output_json(rows: list[dict], fp) -> None:
    json.dump(rows, fp, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="依類型與難易度篩選太鼓達人曲目，依難度排序並輸出 taiko.wiki 連結。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-g", "--genre",
                   help="類型，可用中文(流行音樂/動畫/兒童/VOCALOID™/遊戲音樂/"
                        "南科原創/綜藝/古典)或代碼，逗號分隔多選；不指定=全部類型")
    p.add_argument("-d", "--difficulty",
                   help="難易度：簡單/普通/困難/魔鬼(表)/魔鬼(裏) 或 "
                        "easy/normal/hard/oni/ura，逗號分隔多選；不指定=全部難度")
    p.add_argument("--level", type=int,
                   help="指定 ★ 星等（精確比對，等同 --min-level N --max-level N）")
    p.add_argument("--min-level", type=int, help="★ 星等下限")
    p.add_argument("--max-level", type=int, help="★ 星等上限")
    p.add_argument("--lang", default="zh-tw",
                   help="連結語系(en/ja/ko/zh-tw/zh-cn)，預設 zh-tw；空字串=不加")
    p.add_argument("--format", choices=["table", "md", "csv", "json"],
                   default="table", help="輸出格式，預設 table")
    p.add_argument("-o", "--output", help="輸出檔路徑，不指定則輸出到終端機")
    p.add_argument("--offline", help="改用本地 database.json（不連網）")
    p.add_argument("--include-deleted", action="store_true",
                   help="包含已下架曲目（預設排除）")
    p.add_argument("-q", "--quiet", action="store_true", help="不顯示進度訊息")
    args = p.parse_args(argv)

    min_level, max_level = args.min_level, args.max_level
    if args.level is not None:
        min_level = max_level = args.level

    genres = parse_genres(args.genre)
    difficulties = parse_difficulties(args.difficulty)
    lang = "" if args.lang.lower() in ("", "none") else args.lang

    songs = load_songs(offline=args.offline, verbose=not args.quiet)
    rows = build_rows(songs, genres, difficulties, min_level, max_level,
                      lang, args.include_deleted)

    if not args.quiet:
        cond = [f"類型={genre_label(genres) or '全部'}",
                f"難度={'、'.join(DIFF_LABEL.get(d, d) for d in difficulties)}"]
        if min_level is not None or max_level is not None:
            lo = min_level if min_level is not None else "-"
            hi = max_level if max_level is not None else "-"
            cond.append(f"★={lo}~{hi}")
        print(f"[i] 篩選條件：{'，'.join(cond)}", file=sys.stderr)

    # 寫出
    if args.format == "table":
        if args.output:
            import io
            buf = io.StringIO()
            _stdout = sys.stdout
            sys.stdout = buf
            output_table(rows)
            sys.stdout = _stdout
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(buf.getvalue())
            print(f"[i] 已寫出：{args.output}", file=sys.stderr)
        else:
            output_table(rows)
    elif args.format == "md":
        text = output_markdown(rows)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[i] 已寫出：{args.output}", file=sys.stderr)
        else:
            print(text)
    elif args.format == "csv":
        if args.output:
            with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
                output_csv(rows, f)
            print(f"[i] 已寫出：{args.output}", file=sys.stderr)
        else:
            output_csv(rows, sys.stdout)
    elif args.format == "json":
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                output_json(rows, f)
            print(f"[i] 已寫出：{args.output}", file=sys.stderr)
        else:
            output_json(rows, sys.stdout)
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
