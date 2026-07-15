/*
 * content.js — 在 donderhiroba 頁面注入「匯出成績」按鈕
 * ------------------------------------------------------------------
 * 因為在已登入的 donderhiroba.jp 頁面執行，fetch 為同源且自動帶上
 * 登入 cookie，不需要解密任何 cookie、也沒有 CORS 問題。
 *
 * 抓取流程（沿用 donder-hiroba-plus 的做法）：
 *   1. mypage_top.php 取 _tckt → POST ajax/update_score.php 刷新成績快取
 *   2. 逐一抓 score_list.php?genre=1..8，解析每首歌每難度的冠色
 *   3. 冠色映射為 taiko_filter 標記：虹冠(全良)→perfect、金冠(全連)→fc
 *   4. 下載為 marks.json（格式：{"songNo|difficulty": {"status": "..."}}）
 */
(function () {
  if (window.__donderExportInjected) return;
  window.__donderExportInjected = true;

  const LEVEL_TO_DIFF = { "1": "easy", "2": "normal", "3": "hard",
                          "4": "oni", "5": "ura" };
  // 只匯出「全良」「全連(FC)」；銀冠(通關)在 taiko_filter 沒有對應狀態，略過
  const CROWN_TO_MARK = { donderfull: "perfect", gold: "fc" };

  const btn = document.createElement("button");
  btn.textContent = "⬇ 匯出成績 marks.json";
  Object.assign(btn.style, {
    position: "fixed", right: "16px", bottom: "16px", zIndex: 2147483647,
    background: "#2e8b57", color: "#fff", border: "none", borderRadius: "8px",
    padding: "10px 14px", fontSize: "14px", fontWeight: "bold",
    cursor: "pointer", boxShadow: "0 2px 8px rgba(0,0,0,.4)",
    fontFamily: "sans-serif",
  });
  document.body.appendChild(btn);

  const status = document.createElement("div");
  Object.assign(status.style, {
    position: "fixed", right: "16px", bottom: "58px", zIndex: 2147483647,
    background: "rgba(0,0,0,.82)", color: "#fff", padding: "6px 10px",
    borderRadius: "6px", fontSize: "12px", maxWidth: "340px",
    display: "none", fontFamily: "sans-serif", lineHeight: "1.4",
  });
  document.body.appendChild(status);
  const setStatus = (t) => { status.style.display = "block"; status.textContent = t; };

  async function fetchText(url) {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) throw new Error("HTTP " + res.status + " @ " + url);
    return await res.text();
  }

  async function run() {
    btn.disabled = true;
    btn.style.opacity = "0.6";
    try {
      // 1) 刷新成績快取（best-effort）
      setStatus("刷新成績快取…");
      try {
        const top = await fetchText("https://donderhiroba.jp/mypage_top.php");
        const tckt = new DOMParser().parseFromString(top, "text/html")
          .querySelector("#_tckt")?.textContent?.trim();
        if (tckt) {
          await fetch("https://donderhiroba.jp/ajax/update_score.php", {
            method: "POST", credentials: "include",
            headers: {
              "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
              "x-requested-with": "XMLHttpRequest",
            },
            body: "_tckt=" + encodeURIComponent(tckt),
          });
        }
      } catch (e) { /* 忽略：即使沒刷新，仍可讀既有成績 */ }

      // 2) 逐曲風抓成績並解析
      const marks = {};
      let scanned = 0, applied = 0;
      for (let genre = 1; genre <= 8; genre++) {
        setStatus(`讀取成績（曲風 ${genre}/8）…`);
        const html = await fetchText(
          `https://donderhiroba.jp/score_list.php?genre=${genre}`);
        const doc = new DOMParser().parseFromString(html, "text/html");
        const anchors = doc.querySelectorAll('a[href*="score_detail.php"]');
        anchors.forEach((a) => {
          const href = a.getAttribute("href") || "";
          const sn = href.match(/song_no=(\d+)/);
          const lv = href.match(/level=(\d+)/);
          if (!sn || !lv) return;
          let crown = null;
          a.querySelectorAll("img").forEach((img) => {
            if (crown) return;
            const cm = (img.getAttribute("src") || "")
              .match(/crown_button_([a-z]+)_\d+_640/);
            if (cm) crown = cm[1];
          });
          if (!crown) return;
          scanned++;
          const st = CROWN_TO_MARK[crown];
          const diff = LEVEL_TO_DIFF[lv[1]];
          if (!st || !diff) return;
          marks[`${sn[1]}|${diff}`] = { status: st };
          applied++;
        });
      }

      // 3) 下載 marks.json
      const blob = new Blob([JSON.stringify(marks, null, 2)],
        { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "marks.json";
      link.click();
      URL.revokeObjectURL(link.href);

      setStatus(`完成：掃描 ${scanned} 筆記錄，匯出 ${applied} 個標記`
        + `（全良/FC）到 marks.json。`);
    } catch (e) {
      setStatus("失敗：" + e.message + "（請確認已登入 donderhiroba）");
    } finally {
      btn.disabled = false;
      btn.style.opacity = "1";
    }
  }

  btn.addEventListener("click", run);
})();
