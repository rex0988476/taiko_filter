#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_donder_cookie.py — 獨立取得 donderhiroba Cookie 的小工具
============================================================
讀取瀏覽器中 donderhiroba 的登入 Cookie，讀到後自動複製到剪貼簿，
再回到 taiko_gui.py 的「匯入 donderhiroba 成績」對話框按 Ctrl+V 貼上即可。

讀取方式（自動嘗試，前者失敗才換後者）：
  1. rookiepy      —— 能處理 Chrome/Edge 新版 App-Bound Encryption，通常免管理員
  2. browser_cookie3 —— 舊版加密；Chrome/Edge 新版可能需系統管理員權限

使用前請先在該瀏覽器登入 https://donderhiroba.jp 。
本工具僅讀取你自己的 Cookie 並複製到剪貼簿，不寫入任何檔案。

執行：  python get_donder_cookie.py
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

DOMAIN = "donderhiroba.jp"
BROWSERS = ["chrome", "edge", "firefox", "brave", "opera", "chromium", "vivaldi"]

if sys.platform.startswith("win"):
    UI_FONT = "Microsoft JhengHei"
elif sys.platform == "darwin":
    UI_FONT = "PingFang TC"
else:
    UI_FONT = "Noto Sans CJK TC"


# --------------------------------------------------------------------------- #
#  Cookie 讀取後端
# --------------------------------------------------------------------------- #

def read_with_rookiepy(browser):
    import rookiepy
    fn = getattr(rookiepy, browser, None)
    if fn is None:
        raise RuntimeError(f"rookiepy 不支援瀏覽器：{browser}")
    cookies = fn([DOMAIN])
    return [(c["name"], c["value"]) for c in cookies]


def read_with_bc3(browser):
    com_inited = False
    try:
        import pythoncom
        pythoncom.CoInitialize()
        com_inited = True
    except Exception:
        pass
    try:
        import browser_cookie3
        fn = getattr(browser_cookie3, browser, None)
        if fn is None:
            raise RuntimeError(f"browser_cookie3 不支援瀏覽器：{browser}")
        cj = fn(domain_name=DOMAIN)
        return [(c.name, c.value) for c in cj]
    finally:
        if com_inited:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass


def _module_available(name):
    import importlib.util
    return importlib.util.find_spec(name) is not None


# --------------------------------------------------------------------------- #
#  GUI
# --------------------------------------------------------------------------- #

class CookieTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("取得 donderhiroba Cookie")
        self.configure(bg="#141414")
        self.geometry("620x460")
        self.minsize(560, 420)

        pad = dict(padx=12, pady=4)

        info = (
            "1. 先用瀏覽器登入 https://donderhiroba.jp 。\n"
            "2. 選擇該瀏覽器，按「讀取 Cookie」。\n"
            "3. 讀到後會自動複製到剪貼簿；回 taiko_gui 的匯入視窗按 Ctrl+V 貼上。\n\n"
            "優先使用 rookiepy（支援 Chrome 新版加密，通常免管理員）；\n"
            "沒有時退回 browser_cookie3。本工具不寫入任何檔案。"
        )
        tk.Label(self, text=info, bg="#141414", fg="#dddddd", justify="left",
                 font=(UI_FONT, 9), anchor="w").pack(fill="x", **pad)

        row = tk.Frame(self, bg="#141414"); row.pack(fill="x", **pad)
        tk.Label(row, text="瀏覽器", bg="#141414", fg="#bbbbbb",
                 font=(UI_FONT, 10)).pack(side="left")
        self.browser_var = tk.StringVar(value="chrome")
        ttk.Combobox(row, textvariable=self.browser_var, width=10,
                     state="readonly", values=BROWSERS).pack(side="left", padx=6)
        self.read_btn = tk.Button(row, text="🍪 讀取 Cookie", command=self._read,
                                  bg="#2e8b57", fg="white",
                                  font=(UI_FONT, 10, "bold"), relief="flat",
                                  padx=14, pady=4, cursor="hand2")
        self.read_btn.pack(side="left", padx=8)
        tk.Button(row, text="複製", command=self._copy, bg="#3a5f8a", fg="white",
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(side="left")

        self.status = tk.Label(self, text="請選擇瀏覽器後按「讀取 Cookie」。",
                               bg="#141414", fg="#9fe0a0", font=(UI_FONT, 9),
                               anchor="w", justify="left", wraplength=590)
        self.status.pack(fill="x", **pad)

        self.cookie_txt = tk.Text(self, height=8, bg="#1e1e1e", fg="#e6e6e6",
                                  insertbackground="#e6e6e6", relief="flat",
                                  wrap="word", font=(UI_FONT, 9))
        self.cookie_txt.pack(fill="both", expand=True, padx=12, pady=(4, 10))

    # ------------------------------------------------------------ 狀態
    def _set_status(self, text, err=False):
        self.status.config(text=text, fg="#ff8a80" if err else "#9fe0a0")

    def _copy(self):
        text = self.cookie_txt.get("1.0", "end").strip()
        if not text:
            self._set_status("目前沒有可複製的 Cookie。", err=True)
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("已複製到剪貼簿。回匯入視窗按 Ctrl+V 貼上即可。")

    # ------------------------------------------------------------ 讀取
    def _read(self):
        browser = self.browser_var.get()
        # 確認至少有一種後端可用
        if not (_module_available("rookiepy") or _module_available("browser_cookie3")):
            if not messagebox.askyesno(
                    "需要安裝套件",
                    "讀取需要 rookiepy（建議）或 browser_cookie3。\n"
                    "要現在自動安裝 rookiepy 嗎？"):
                return
            self._install_then_read("rookiepy", browser)
            return
        self.read_btn.config(state="disabled")
        self._set_status(f"從 {browser} 讀取 donderhiroba Cookie 中…")
        threading.Thread(target=self._worker, args=(browser,),
                         daemon=True).start()

    def _install_then_read(self, package, browser):
        self._set_status(f"安裝 {package} 中…（可能需數十秒）")

        def install():
            import subprocess
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install",
                                       package])
                self.after(0, lambda: (self.read_btn.config(state="disabled"),
                                       self._set_status(f"從 {browser} 讀取中…"),
                                       threading.Thread(
                                           target=self._worker, args=(browser,),
                                           daemon=True).start()))
            except Exception as exc:
                self.after(0, lambda e=exc:
                           self._set_status(f"安裝失敗：{e}", err=True))

        threading.Thread(target=install, daemon=True).start()

    def _worker(self, browser):
        errors = []
        for reader in (read_with_rookiepy, read_with_bc3):
            try:
                pairs = reader(browser)
                if pairs:
                    self.after(0, lambda p=pairs, r=reader.__name__:
                               self._done(p, r))
                    return
                errors.append(f"{reader.__name__}: 沒有找到 Cookie")
            except ImportError:
                errors.append(f"{reader.__name__}: 未安裝")
            except Exception as exc:
                errors.append(f"{reader.__name__}: {exc}")

        msg = " ／ ".join(errors)
        self.after(0, lambda m=msg: self._fail(m))

    def _done(self, pairs, backend):
        cookie = "; ".join(f"{n}={v}" for n, v in pairs)
        self.cookie_txt.delete("1.0", "end")
        self.cookie_txt.insert("1.0", cookie)
        self.clipboard_clear()
        self.clipboard_append(cookie)
        self.read_btn.config(state="normal")
        self._set_status(f"成功（{backend}）：讀到 {len(pairs)} 個 Cookie，"
                         "已自動複製到剪貼簿。回匯入視窗按 Ctrl+V 貼上。")

    def _fail(self, msg):
        self.read_btn.config(state="normal")
        low = msg.lower()
        if "admin" in low or "key for cookie" in low:
            self._set_status(
                "Chrome/Edge 新版加密讀取失敗。可改用 Firefox、以系統管理員"
                "重新啟動本工具，或安裝 rookiepy 後再試。詳情：" + msg, err=True)
            if sys.platform.startswith("win") and messagebox.askyesno(
                    "需要系統管理員權限？",
                    "Chrome/Edge 新版 Cookie 加密可能需要系統管理員權限。\n"
                    "要以系統管理員重新啟動本工具嗎？\n"
                    "（或按「否」，改用 Firefox）"):
                self._restart_as_admin()
        else:
            self._set_status(f"讀取失敗：{msg}", err=True)

    def _restart_as_admin(self):
        if not sys.platform.startswith("win"):
            messagebox.showinfo("不支援", "此功能僅限 Windows。")
            return
        try:
            import ctypes
            params = " ".join(f'"{a}"' for a in sys.argv)
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1)
            if rc > 32:
                self.destroy()
            else:
                messagebox.showerror("無法提權", "使用者已取消或提權失敗。")
        except Exception as exc:
            messagebox.showerror("無法提權", str(exc))


if __name__ == "__main__":
    CookieTool().mainloop()
