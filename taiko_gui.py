r"""
taiko_gui.py — 太鼓の達人曲目篩選器（圖形介面）
================================================
以 Tkinter（Python 標準庫）將 taiko_filter 的篩選引擎包成桌面 GUI：

  * 依「類型」「難易度」以彩色切換鈕多選（仿 taiko.wiki 介面）
  * 以 ★ 星等雙滑桿設定範圍
  * 結果以表格顯示，雙擊列可用瀏覽器開啟 taiko.wiki 曲目頁
  * 一鍵匯出 CSV / JSON / Markdown

需與 taiko_filter.py 置於同一資料夾。資料來源沿用引擎的
「官方 API → GitHub 鏡像 → 本地 database.json」容錯鏈。

執行：  python taiko_gui.py
需求：  Python 3.9+（Tkinter 為標準庫，Windows/macOS 內建；
        部分 Linux 需 `sudo apt install python3-tk`）
"""

import os
import sys
import csv
import io
import json
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- 匯入篩選引擎（與本檔同資料夾）--------------------------------------- #
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import taiko_filter as tf
except ImportError:
    tk.Tk().withdraw()
    messagebox.showerror("缺少檔案",
                         "找不到 taiko_filter.py，請將它與本程式放在同一資料夾。")
    raise SystemExit(1)

# --- 仿 taiko.wiki 的按鈕配色 -------------------------------------------- #
GENRE_COLORS = {
    "pops": "#3bb8b0", "anime": "#e58ec4", "kids": "#e2b23c",
    "vocaloid": "#b7bce0", "game": "#9b7fdc", "namco": "#e15b5b",
    "variety": "#7cbf5a", "classic": "#c9a227",
}
DIFF_COLORS = {
    "easy": "#e8462b", "normal": "#5f8f3a", "hard": "#2f6f63",
    "oni": "#d61e8c", "ura": "#7a3ff0",
}
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "database.json")
# 標記檔（JSON；本地 GUI 與 GitHub Pages 網頁皆可讀寫）
MARKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "marks.json")
# 播放清單檔（JSON；本地 GUI 專用）
PLAYLISTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "playlists.json")
# 標記狀態顯示文字（near = 快全良，會另附剩餘「可」數）
MARK_LABEL = {"fc": "FC", "perfect": "全良", "near": "快全良"}
MARK_FG = {"fc": "#7ec4ff", "perfect": "#ffd54a", "near": "#ffb066"}

# 難度 -> donderhiroba 的 level 參數（與官方 song_no 搭配開啟曲目頁）
DONDER_LEVEL = {"easy": 1, "normal": 2, "hard": 3, "oni": 4, "ura": 5}

# 依作業系統挑選可正確顯示中日文的字型（找不到時 Tk 會自動退回預設）
if sys.platform.startswith("win"):
    UI_FONT = "Microsoft JhengHei"
elif sys.platform == "darwin":
    UI_FONT = "PingFang TC"
else:
    UI_FONT = "Noto Sans CJK TC"


class ToggleButton(tk.Checkbutton):
    """看起來像彩色實心切換鈕的 Checkbutton（選取時保持按下狀態）。"""
    def __init__(self, master, text, color, variable):
        dark = "#1d1d1d"
        super().__init__(
            master, text=text, variable=variable, indicatoron=False,
            font=(UI_FONT, 11, "bold"),
            width=10, padx=6, pady=6, bd=0, relief="flat",
            fg="#dddddd", bg=dark, activebackground=color,
            selectcolor=color, activeforeground="white",
            cursor="hand2", offrelief="flat", overrelief="raised",
        )
        self._color = color
        self.configure(command=self._refresh)
        self._var = variable
        self._refresh()

    def _refresh(self):
        if self._var.get():
            self.configure(bg=self._color, fg="white")
        else:
            self.configure(bg="#2b2b2b", fg="#cfcfcf")


class TaikoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("太鼓達人曲目篩選器 — taiko.wiki")
        self.geometry("980x680")
        self.minsize(860, 600)
        self.configure(bg="#141414")

        self.songs = None            # 載入後的曲目清單
        self.rows = []               # 目前篩選結果
        self.genre_vars = {}
        self.diff_vars = {}
        self.lang_var = tk.StringVar(value="zh-tw")
        self.marks = {}              # {"songNo|difficulty": {...}}
        self._load_marks()
        self.playlists = {}          # {"清單名稱": ["songNo|difficulty", ...]}
        self.current_playlist = None # None = 「全部」（篩選）模式
        self._song_index = None      # songNo -> song，供播放清單重建列用
        self._load_playlists()

        self._build_style()
        self._build_widgets()
        self._load_async()           # 啟動時背景載入資料

    # ---------------------------------------------------------------- 樣式
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview",
                        background="#1e1e1e", fieldbackground="#1e1e1e",
                        foreground="#e6e6e6", rowheight=26,
                        font=(UI_FONT, 10))
        style.configure("Treeview.Heading",
                        background="#333333", foreground="#ffffff",
                        font=(UI_FONT, 10, "bold"))
        style.map("Treeview", background=[("selected", "#3a5f8a")])

    # -------------------------------------------------------------- 版面
    def _build_widgets(self):
        pad = dict(padx=10, pady=4)

        # 類型區
        gframe = tk.LabelFrame(self, text="  類型  ", bg="#141414", fg="#ffffff",
                               font=(UI_FONT, 12, "bold"), bd=0)
        gframe.pack(fill="x", **pad)
        grow = tk.Frame(gframe, bg="#141414"); grow.pack(fill="x")
        for i, (code, label) in enumerate(tf.GENRE_LABEL.items()):
            var = tk.BooleanVar(value=False)
            self.genre_vars[code] = var
            btn = ToggleButton(grow, label, GENRE_COLORS.get(code, "#555"), var)
            btn.grid(row=0, column=i, padx=3, pady=4, sticky="ew")
            grow.columnconfigure(i, weight=1)

        # 難易度區
        dframe = tk.LabelFrame(self, text="  難易度  ", bg="#141414", fg="#ffffff",
                               font=(UI_FONT, 12, "bold"), bd=0)
        dframe.pack(fill="x", **pad)
        drow = tk.Frame(dframe, bg="#141414"); drow.pack(fill="x")
        for i, (code, label) in enumerate(tf.DIFF_LABEL.items()):
            var = tk.BooleanVar(value=False)
            self.diff_vars[code] = var
            btn = ToggleButton(drow, label, DIFF_COLORS.get(code, "#555"), var)
            btn.grid(row=0, column=i, padx=3, pady=4, sticky="w")

        # ★ 星等 + 語系 + 查詢
        cframe = tk.Frame(self, bg="#141414"); cframe.pack(fill="x", **pad)

        tk.Label(cframe, text="★ 星等", bg="#141414", fg="#ffd54a",
                 font=(UI_FONT, 11, "bold")).grid(row=0, column=0,
                                                               padx=(0, 6))
        self.min_var = tk.IntVar(value=1)
        self.max_var = tk.IntVar(value=10)
        self.min_lbl = tk.Label(cframe, text="★1", width=4, bg="#141414",
                                fg="#ffffff", font=(UI_FONT, 10))
        self.max_lbl = tk.Label(cframe, text="★10", width=4, bg="#141414",
                                fg="#ffffff", font=(UI_FONT, 10))
        s_min = ttk.Scale(cframe, from_=1, to=10, variable=self.min_var,
                          orient="horizontal", length=180,
                          command=lambda e: self._on_scale("min"))
        s_max = ttk.Scale(cframe, from_=1, to=10, variable=self.max_var,
                          orient="horizontal", length=180,
                          command=lambda e: self._on_scale("max"))
        tk.Label(cframe, text="下限", bg="#141414", fg="#bbbbbb").grid(row=0, column=1)
        s_min.grid(row=0, column=2); self.min_lbl.grid(row=0, column=3)
        tk.Label(cframe, text="上限", bg="#141414", fg="#bbbbbb").grid(row=0, column=4)
        s_max.grid(row=0, column=5); self.max_lbl.grid(row=0, column=6)

        tk.Label(cframe, text="連結語系", bg="#141414", fg="#bbbbbb").grid(
            row=0, column=7, padx=(20, 4))
        ttk.Combobox(cframe, textvariable=self.lang_var, width=7, state="readonly",
                     values=["zh-tw", "zh-cn", "ja", "en", "ko"]).grid(row=0, column=8)

        tk.Label(cframe, text="搜尋曲名", bg="#141414", fg="#bbbbbb").grid(
            row=0, column=9, padx=(20, 4))
        self.query_var = tk.StringVar()
        q_entry = tk.Entry(cframe, textvariable=self.query_var, width=16,
                           bg="#1e1e1e", fg="#e6e6e6", insertbackground="#e6e6e6",
                           relief="flat")
        q_entry.grid(row=0, column=10, ipady=3)
        q_entry.bind("<Return>", lambda e: self.search())

        tk.Button(cframe, text="🔍 篩選", command=self.search,
                  bg="#e15b5b", fg="white", font=(UI_FONT, 11, "bold"),
                  relief="flat", padx=18, pady=4, cursor="hand2").grid(
            row=0, column=11, padx=16)
        tk.Button(cframe, text="清除選取", command=self._clear_selection,
                  bg="#444", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2").grid(row=0, column=12)

        # 播放清單工具列（介於星等列與標記列之間）
        pframe = tk.LabelFrame(self, text="  播放清單（不受篩選影響）  ",
                               bg="#141414", fg="#ffffff",
                               font=(UI_FONT, 11, "bold"), bd=0)
        pframe.pack(fill="x", **pad)
        prow = tk.Frame(pframe, bg="#141414"); prow.pack(fill="x")

        tk.Label(prow, text="檢視", bg="#141414", fg="#bbbbbb").pack(
            side="left", padx=(0, 4))
        self.mode_var = tk.StringVar(value="全部")
        self.mode_combo = ttk.Combobox(prow, textvariable=self.mode_var, width=16,
                                       state="readonly", values=["全部"])
        self.mode_combo.pack(side="left")
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        tk.Label(prow, text="新增清單", bg="#141414", fg="#bbbbbb").pack(
            side="left", padx=(16, 4))
        self.new_pl_var = tk.StringVar()
        ent = tk.Entry(prow, textvariable=self.new_pl_var, width=14,
                       bg="#1e1e1e", fg="#e6e6e6", insertbackground="#e6e6e6",
                       relief="flat")
        ent.pack(side="left", ipady=3)
        ent.bind("<Return>", lambda e: self._add_playlist())
        tk.Button(prow, text="＋", command=self._add_playlist,
                  bg="#2e8b57", fg="white", font=(UI_FONT, 11, "bold"),
                  relief="flat", padx=10, pady=2, cursor="hand2").pack(
            side="left", padx=(4, 0))

        tk.Label(prow, text="管理", bg="#141414", fg="#bbbbbb").pack(
            side="left", padx=(16, 4))
        self.del_pl_var = tk.StringVar()
        self.del_combo = ttk.Combobox(prow, textvariable=self.del_pl_var, width=14,
                                      state="readonly", values=[])
        self.del_combo.pack(side="left")
        tk.Button(prow, text="刪除清單", command=self._delete_playlist,
                  bg="#a33", fg="white", relief="flat", padx=10, pady=2,
                  cursor="hand2").pack(side="left", padx=(4, 0))

        prow2 = tk.Frame(pframe, bg="#141414"); prow2.pack(fill="x", pady=(4, 0))
        tk.Label(prow2, text="目標清單", bg="#141414", fg="#bbbbbb").pack(
            side="left", padx=(0, 4))
        self.target_pl_var = tk.StringVar()
        self.target_combo = ttk.Combobox(prow2, textvariable=self.target_pl_var,
                                         width=16, state="readonly", values=[])
        self.target_combo.pack(side="left")
        tk.Button(prow2, text="加入所選曲目到清單", command=self._add_to_playlist,
                  bg="#3a5f8a", fg="white", relief="flat", padx=12, pady=3,
                  cursor="hand2").pack(side="left", padx=8)
        tk.Button(prow2, text="從目前清單移除所選曲目",
                  command=self._remove_from_playlist,
                  bg="#8a5a3a", fg="white", relief="flat", padx=12, pady=3,
                  cursor="hand2").pack(side="left")

        # 標記工具列
        mframe = tk.LabelFrame(self, text="  標記（先點選下方一列 → 選狀態 → 套用）  ",
                               bg="#141414", fg="#ffffff",
                               font=(UI_FONT, 11, "bold"), bd=0)
        mframe.pack(fill="x", **pad)
        mrow = tk.Frame(mframe, bg="#141414"); mrow.pack(fill="x")

        self.mark_status_var = tk.StringVar(value="none")
        for text, val in (("未標記", "none"), ("FC", "fc"),
                          ("全良", "perfect"), ("快全良", "near")):
            tk.Radiobutton(mrow, text=text, value=val,
                           variable=self.mark_status_var,
                           command=self._on_mark_mode,
                           bg="#141414", fg="#e6e6e6", selectcolor="#2b2b2b",
                           activebackground="#141414", activeforeground="#fff",
                           font=(UI_FONT, 10)).pack(side="left", padx=4)

        tk.Label(mrow, text="剩餘「可」", bg="#141414", fg="#bbbbbb").pack(
            side="left", padx=(12, 4))
        self.remaining_var = tk.IntVar(value=0)
        self.remaining_spin = tk.Spinbox(mrow, from_=0, to=999, width=5,
                                         textvariable=self.remaining_var,
                                         state="disabled")
        self.remaining_spin.pack(side="left")

        tk.Button(mrow, text="套用到選取列", command=self._apply_mark,
                  bg="#6a5acd", fg="white", relief="flat", padx=12, pady=3,
                  cursor="hand2").pack(side="left", padx=12)
        tk.Button(mrow, text="💾 儲存標記", command=self._save_marks,
                  bg="#2e8b57", fg="white", font=(UI_FONT, 10, "bold"),
                  relief="flat", padx=12, pady=3, cursor="hand2").pack(side="left")

        # 結果表格
        tframe = tk.Frame(self, bg="#141414"); tframe.pack(fill="both", expand=True,
                                                           padx=10, pady=(6, 2))
        cols = ("star", "diff", "genre", "title", "mark")
        self.tree = ttk.Treeview(tframe, columns=cols, show="headings",
                                 selectmode="browse")
        for c, txt, w, anc in (("star", "★", 60, "center"),
                               ("diff", "難度", 90, "center"),
                               ("genre", "類型", 150, "center"),
                               ("title", "曲名（雙擊開啟 taiko.wiki）", 470, "w"),
                               ("mark", "標記", 110, "center")):
            self.tree.heading(c, text=txt,
                              command=lambda cc=c: self._sort_by(cc))
            self.tree.column(c, width=w, anchor=anc)
        vsb = ttk.Scrollbar(tframe, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self.tree.tag_configure("odd", background="#232323")
        self.tree.tag_configure("even", background="#1b1b1b")
        # 依標記狀態的整列底色（全良：藍、FC：金、快全良：綠）
        self.tree.tag_configure("mark_perfect", background="#2f6fed",
                                foreground="#ffffff")
        self.tree.tag_configure("mark_fc", background="#d4af37",
                                foreground="#1a1a1a")
        self.tree.tag_configure("mark_near", background="#2e8b57",
                                foreground="#ffffff")

        # 底部：狀態列 + 匯出
        bframe = tk.Frame(self, bg="#141414"); bframe.pack(fill="x", padx=10,
                                                          pady=(0, 8))
        self.status = tk.Label(bframe, text="載入資料中…", anchor="w",
                               bg="#141414", fg="#9fe0a0",
                               font=(UI_FONT, 10))
        self.status.pack(side="left", fill="x", expand=True)
        for txt, fmt in (("匯出 CSV", "csv"), ("匯出 JSON", "json"),
                         ("匯出 Markdown", "md")):
            tk.Button(bframe, text=txt, command=lambda f=fmt: self._export(f),
                      bg="#3a5f8a", fg="white", relief="flat", padx=10, pady=3,
                      cursor="hand2").pack(side="right", padx=4)
        tk.Button(bframe, text="開啟選取曲目", command=self._open_selected,
                  bg="#2f6f63", fg="white", relief="flat", padx=10, pady=3,
                  cursor="hand2").pack(side="right", padx=4)
        tk.Button(bframe, text="🔗 donderhiroba", command=self._open_donder,
                  bg="#b06a2f", fg="white", relief="flat", padx=10, pady=3,
                  cursor="hand2").pack(side="right", padx=4)

        self._refresh_playlist_combos()

    # ------------------------------------------------------------- 事件
    def _on_scale(self, which):
        lo, hi = self.min_var.get(), self.max_var.get()
        if which == "min" and lo > hi:
            self.max_var.set(lo)
        if which == "max" and hi < lo:
            self.min_var.set(hi)
        self.min_lbl.config(text=f"★{self.min_var.get()}")
        self.max_lbl.config(text=f"★{self.max_var.get()}")

    def _clear_selection(self):
        for v in self.genre_vars.values(): v.set(False)
        for v in self.diff_vars.values(): v.set(False)
        for w in self.winfo_children():
            self._refresh_toggles(w)
        self.min_var.set(1); self.max_var.set(10)
        self.query_var.set("")
        self._on_scale("min")

    def _refresh_toggles(self, widget):
        if isinstance(widget, ToggleButton):
            widget._refresh()
        for c in widget.winfo_children():
            self._refresh_toggles(c)

    # --------------------------------------------------------- 資料載入
    def _load_async(self):
        def worker():
            try:
                offline = DEFAULT_DB if os.path.exists(DEFAULT_DB) else None
                # 先嘗試線上；失敗（或無網路）則用同資料夾快照
                try:
                    songs = tf.load_songs(offline=None, verbose=False)
                    src = "官方 API / 線上鏡像"
                except SystemExit:
                    if not offline:
                        raise
                    songs = tf.load_songs(offline=offline, verbose=False)
                    src = "本地 database.json"
                self.songs = songs
                self.after(0, lambda: self._set_status(
                    f"已載入 {len(songs)} 首曲目（{src}）。請選擇條件後按「篩選」。"))
            except Exception as exc:
                self.after(0, lambda: self._set_status(
                    f"資料載入失敗：{exc}", err=True))
        threading.Thread(target=worker, daemon=True).start()

    def _set_status(self, text, err=False):
        self.status.config(text=text, fg="#ff8a80" if err else "#9fe0a0")

    # ------------------------------------------------------------- 篩選
    def search(self):
        if self.songs is None:
            messagebox.showinfo("請稍候", "資料尚未載入完成。")
            return
        # 篩選一律回到「全部」模式（播放清單不受篩選影響）
        if self.current_playlist is not None:
            self.current_playlist = None
            self.mode_var.set("全部")
        genres = [c for c, v in self.genre_vars.items() if v.get()]
        diffs = [c for c, v in self.diff_vars.items() if v.get()]
        if not diffs:  # 未選難度 = 全部難度（與 CLI 一致）
            diffs = list(tf.DIFF_ORDER.keys())
        lo, hi = self.min_var.get(), self.max_var.get()
        lang = self.lang_var.get()

        self.rows = tf.build_rows(self.songs, genres, diffs, lo, hi, lang,
                                  include_deleted=False)
        query = self.query_var.get().strip().lower()
        if query:
            self.rows = [r for r in self.rows if query in (r["title"] or "").lower()]
        self._populate()

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            diff = tf.DIFF_LABEL.get(r["difficulty"], r["difficulty"])
            gnr = "/".join(tf.GENRE_LABEL.get(g, g) for g in r["genres"])
            self.tree.insert("", "end", iid=str(i),
                             values=(f"★{r['level']}", diff, gnr, r["title"],
                                     self._mark_text(r)),
                             tags=(self._row_tag(r, i),))
        self._set_status(f"符合條件共 {len(self.rows)} 筆。雙擊任一列可開啟 taiko.wiki。")

    def _sort_by(self, col):
        key = {"star": lambda r: (r["level"], tf.DIFF_ORDER[r["difficulty"]]),
               "diff": lambda r: tf.DIFF_ORDER[r["difficulty"]],
               "genre": lambda r: r["genres"][0] if r["genres"] else "",
               "title": lambda r: r["title"],
               "mark": lambda r: self._mark_sort_key(r)}[col]
        self.rows.sort(key=key)
        self._populate()

    # ------------------------------------------------------------- 標記
    @staticmethod
    def _mark_key(r):
        return f"{r['songNo']}|{r['difficulty']}"

    def _row_tag(self, r, i):
        m = self.marks.get(self._mark_key(r))
        if m and m.get("status") in ("perfect", "fc", "near"):
            return "mark_" + m["status"]
        return "odd" if i % 2 else "even"

    def _mark_text(self, r):
        m = self.marks.get(self._mark_key(r))
        if not m:
            return ""
        st = m.get("status")
        if st == "near":
            return f"快全良(可{m.get('remaining', '?')})"
        return MARK_LABEL.get(st, "")

    def _mark_sort_key(self, r):
        # 排序權重：未標記 < 快全良 < 全良 < FC；快全良再依剩餘可數（少者較前）
        order = {"": 0, "near": 1, "perfect": 2, "fc": 3}
        m = self.marks.get(self._mark_key(r))
        st = m.get("status") if m else ""
        rem = m.get("remaining", 0) if (m and m.get("status") == "near") else 0
        return (order.get(st, 0), rem)

    def _on_mark_mode(self):
        state = "normal" if self.mark_status_var.get() == "near" else "disabled"
        self.remaining_spin.config(state=state)

    def _on_row_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.rows[int(sel[0])]
        m = self.marks.get(self._mark_key(r))
        if not m:
            self.mark_status_var.set("none")
            self.remaining_var.set(0)
        else:
            self.mark_status_var.set(m.get("status", "none"))
            self.remaining_var.set(m.get("remaining", 0)
                                   if m.get("status") == "near" else 0)
        self._on_mark_mode()

    def _apply_mark(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先在下方表格點選一列，再套用標記。")
            return
        r = self.rows[int(sel[0])]
        key = self._mark_key(r)
        st = self.mark_status_var.get()
        if st == "none":
            self.marks.pop(key, None)
        elif st == "near":
            try:
                n = int(self.remaining_var.get())
            except (ValueError, tk.TclError):
                messagebox.showwarning("輸入錯誤", "請輸入剩餘『可』的數量（整數）。")
                return
            if n < 0:
                messagebox.showwarning("輸入錯誤", "剩餘『可』的數量不可為負。")
                return
            self.marks[key] = {"status": "near", "remaining": n}
        else:
            self.marks[key] = {"status": st}
        self.tree.set(sel[0], "mark", self._mark_text(r))
        self.tree.item(sel[0], tags=(self._row_tag(r, int(sel[0])),))
        shown = self._mark_text(r) or "未標記"
        self._set_status(f"已標記：{r['title']}（"
                         f"{tf.DIFF_LABEL.get(r['difficulty'], r['difficulty'])}）"
                         f"→ {shown}　（記得按「💾 儲存標記」寫入檔案）")

    def _load_marks(self):
        if os.path.exists(MARKS_FILE):
            try:
                with open(MARKS_FILE, "r", encoding="utf-8") as f:
                    self.marks = json.load(f)
            except (OSError, ValueError):
                self.marks = {}

    def _save_marks(self):
        try:
            with open(MARKS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.marks, f, ensure_ascii=False, indent=2)
            self._set_status(f"已儲存 {len(self.marks)} 筆標記至 marks.json"
                             "（推送後線上即可查看）。")
        except OSError as exc:
            messagebox.showerror("儲存失敗", str(exc))

    # ------------------------------------------------------------- 播放清單
    def _load_playlists(self):
        if os.path.exists(PLAYLISTS_FILE):
            try:
                with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.playlists = {k: list(v) for k, v in data.items()}
            except (OSError, ValueError):
                self.playlists = {}

    def _save_playlists(self):
        try:
            with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.playlists, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            messagebox.showerror("儲存失敗", str(exc))

    def _refresh_playlist_combos(self):
        names = list(self.playlists.keys())
        self.mode_combo["values"] = ["全部"] + names
        self.del_combo["values"] = names
        self.target_combo["values"] = names
        if self.mode_var.get() not in (["全部"] + names):
            self.mode_var.set("全部")
        if self.del_pl_var.get() not in names:
            self.del_pl_var.set("")
        if self.target_pl_var.get() not in names:
            self.target_pl_var.set("")

    def _rows_from_keys(self, keys):
        """由 songNo|difficulty 清單重建結果列（保留清單順序）。"""
        if not self.songs:
            return []
        if self._song_index is None:
            self._song_index = {str(s.get("songNo")): s for s in self.songs}
        lang = self.lang_var.get()
        rows = []
        for key in keys:
            if "|" not in key:
                continue
            song_no, diff = key.split("|", 1)
            s = self._song_index.get(str(song_no))
            if not s:
                continue
            course = (s.get("courses") or {}).get(diff)
            if not course:
                continue
            level = course.get("level")
            if level is None:
                continue
            url = tf.SONG_PAGE.format(songNo=song_no)
            if lang:
                url += f"?lang={lang}"
            rows.append({
                "songNo": str(song_no),
                "title": s.get("title") or s.get("titleEn") or s.get("romaji") or "",
                "romaji": s.get("romaji") or "",
                "genres": s.get("genre") or [],
                "difficulty": diff,
                "level": level,
                "url": url,
            })
        return rows

    def _on_mode_change(self, event=None):
        sel = self.mode_var.get()
        self.current_playlist = None if sel == "全部" else sel
        if self.current_playlist is None:
            self.search()
        else:
            if self.songs is None:
                messagebox.showinfo("請稍候", "資料尚未載入完成。")
                return
            self.rows = self._rows_from_keys(
                self.playlists.get(self.current_playlist, []))
            self._populate()
            self._set_status(
                f"播放清單「{self.current_playlist}」：共 {len(self.rows)} 首"
                "（不受篩選影響；可選一列後按「從目前清單移除所選曲目」）。")

    def _add_playlist(self):
        name = self.new_pl_var.get().strip()
        if not name:
            messagebox.showinfo("請輸入名稱", "請先輸入播放清單名稱。")
            return
        if name == "全部" or name in self.playlists:
            messagebox.showwarning("名稱重複", "已存在同名清單或使用保留字「全部」。")
            return
        self.playlists[name] = []
        self._save_playlists()
        self._refresh_playlist_combos()
        self.new_pl_var.set("")
        self.target_pl_var.set(name)
        self._set_status(f"已新增播放清單：{name}")

    def _delete_playlist(self):
        name = self.del_pl_var.get()
        if not name or name not in self.playlists:
            messagebox.showinfo("未選擇", "請在「管理」下拉選單選擇要刪除的清單。")
            return
        if not messagebox.askyesno("確認刪除", f"確定刪除播放清單「{name}」？"):
            return
        self.playlists.pop(name, None)
        self._save_playlists()
        back_to_all = (self.current_playlist == name)
        if back_to_all:
            self.current_playlist = None
            self.mode_var.set("全部")
        self._refresh_playlist_combos()
        if back_to_all:
            self.search()
        self._set_status(f"已刪除播放清單：{name}")

    def _add_to_playlist(self):
        target = self.target_pl_var.get()
        if not target or target not in self.playlists:
            messagebox.showinfo("未選擇清單", "請先在「目標清單」下拉選單選擇要加入的清單。")
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先在下方表格點選要加入的曲目。")
            return
        r = self.rows[int(sel[0])]
        key = self._mark_key(r)
        lst = self.playlists[target]
        if key in lst:
            self._set_status(f"「{r['title']}」已在清單「{target}」中。")
            return
        lst.append(key)
        self._save_playlists()
        self._set_status(
            f"已加入「{r['title']}（"
            f"{tf.DIFF_LABEL.get(r['difficulty'], r['difficulty'])}）"
            f"」到清單「{target}」。")

    def _remove_from_playlist(self):
        if self.current_playlist is None:
            messagebox.showinfo("非清單檢視",
                                "請先在「檢視」選擇某個播放清單，才能從中移除曲目。")
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先點選要移除的曲目。")
            return
        r = self.rows[int(sel[0])]
        key = self._mark_key(r)
        lst = self.playlists.get(self.current_playlist, [])
        if key not in lst:
            return
        lst.remove(key)
        self._save_playlists()
        self.rows = self._rows_from_keys(lst)
        self._populate()
        self._set_status(
            f"已從清單「{self.current_playlist}」移除「{r['title']}」。")

    # ----------------------------------------------------- 開啟 / 匯出
    def _open_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.rows[int(sel[0])]
        webbrowser.open(r["url"])

    def _open_donder(self, event=None):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("未選取", "請先點選一列。")
            return
        r = self.rows[int(sel[0])]
        song_no = str(r["songNo"])
        if not song_no.isdigit():
            messagebox.showinfo("無法對應",
                                "這首曲目沒有 donderhiroba 對應編號（非數字 songNo）。")
            return
        lv = DONDER_LEVEL.get(r["difficulty"])
        if not lv:
            return
        url = (f"https://donderhiroba.jp/score_detail.php"
               f"?song_no={song_no}&level={lv}")
        webbrowser.open(url)

    def _export(self, fmt):
        if not self.rows:
            messagebox.showinfo("無資料", "請先篩選出結果再匯出。")
            return
        ext = {"csv": ".csv", "json": ".json", "md": ".md"}[fmt]
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(fmt.upper(), f"*{ext}"), ("所有檔案", "*.*")],
            initialfile=f"taiko_result{ext}")
        if not path:
            return
        try:
            if fmt == "csv":
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    tf.output_csv(self.rows, f)
            elif fmt == "json":
                with open(path, "w", encoding="utf-8") as f:
                    tf.output_json(self.rows, f)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(tf.output_markdown(self.rows))
            self._set_status(f"已匯出 {len(self.rows)} 筆至：{path}")
        except OSError as exc:
            messagebox.showerror("匯出失敗", str(exc))


if __name__ == "__main__":
    TaikoGUI().mainloop()
