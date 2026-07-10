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

        tk.Button(cframe, text="🔍 篩選", command=self.search,
                  bg="#e15b5b", fg="white", font=(UI_FONT, 11, "bold"),
                  relief="flat", padx=18, pady=4, cursor="hand2").grid(
            row=0, column=9, padx=16)
        tk.Button(cframe, text="清除選取", command=self._clear_selection,
                  bg="#444", fg="white", relief="flat", padx=10, pady=4,
                  cursor="hand2").grid(row=0, column=10)

        # 結果表格
        tframe = tk.Frame(self, bg="#141414"); tframe.pack(fill="both", expand=True,
                                                           padx=10, pady=(6, 2))
        cols = ("star", "diff", "genre", "title")
        self.tree = ttk.Treeview(tframe, columns=cols, show="headings",
                                 selectmode="browse")
        for c, txt, w, anc in (("star", "★", 60, "center"),
                               ("diff", "難度", 90, "center"),
                               ("genre", "類型", 150, "center"),
                               ("title", "曲名（雙擊開啟 taiko.wiki）", 560, "w")):
            self.tree.heading(c, text=txt,
                              command=lambda cc=c: self._sort_by(cc))
            self.tree.column(c, width=w, anchor=anc)
        vsb = ttk.Scrollbar(tframe, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.tag_configure("odd", background="#232323")
        self.tree.tag_configure("even", background="#1b1b1b")

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
        genres = [c for c, v in self.genre_vars.items() if v.get()]
        diffs = [c for c, v in self.diff_vars.items() if v.get()]
        if not diffs:  # 未選難度 = 全部難度（與 CLI 一致）
            diffs = list(tf.DIFF_ORDER.keys())
        lo, hi = self.min_var.get(), self.max_var.get()
        lang = self.lang_var.get()

        self.rows = tf.build_rows(self.songs, genres, diffs, lo, hi, lang,
                                  include_deleted=False)
        self._populate()

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            diff = tf.DIFF_LABEL.get(r["difficulty"], r["difficulty"])
            gnr = "/".join(tf.GENRE_LABEL.get(g, g) for g in r["genres"])
            tag = "odd" if i % 2 else "even"
            self.tree.insert("", "end", iid=str(i),
                             values=(f"★{r['level']}", diff, gnr, r["title"]),
                             tags=(tag,))
        self._set_status(f"符合條件共 {len(self.rows)} 筆。雙擊任一列可開啟 taiko.wiki。")

    def _sort_by(self, col):
        key = {"star": lambda r: (r["level"], tf.DIFF_ORDER[r["difficulty"]]),
               "diff": lambda r: tf.DIFF_ORDER[r["difficulty"]],
               "genre": lambda r: r["genres"][0] if r["genres"] else "",
               "title": lambda r: r["title"]}[col]
        self.rows.sort(key=key)
        self._populate()

    # ----------------------------------------------------- 開啟 / 匯出
    def _open_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.rows[int(sel[0])]
        webbrowser.open(r["url"])

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
