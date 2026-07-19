/*
 * count.js — 在 donderhiroba 頁面注入「統計鬼/裏數量」按鈕
 * ------------------------------------------------------------------
 * 與 content.js 相同原理：在已登入的 donderhiroba.jp 頁面內以同源
 * fetch 抓取 score_list.php?genre=1..8，解析每首歌每難度的冠色，
 * 但這支不是匯出標記，而是「計數」：
 *   - 分別統計「鬼(level=4)」與「裏(level=5)」譜面的數量
 *   - 依冠色細分：未遊玩 / 已玩未通關 / 銀冠(通關) / 金冠(FC) / 虹冠(全良)
 *   - 跨曲風出現的同一譜面會去重，並保留最高冠色
 *
 * 注意：donderhiroba 的成績頁「不含星等(★N)」資訊，
 *       因此本程式只能給「鬼/裏總數與各冠色數」，無法直接產生
 *       「★1..★10 分級難度表」。星等需另行對照 taiko.wiki 曲目資料
 *       （見說明檔第五節）。
 */
(function () {
  if (window.__donderCountInjected) return;
  window.__donderCountInjected = true;

  const LEVEL_LABEL = { "4": "鬼", "5": "裏" };

  // 冠色分類（由 crown_button_{crown}_..._640.png 檔名解析）
  //   none       未遊玩（該譜面存在但無成績）
  //   played     已遊玩但未通關
  //   silver     銀冠 = 通關
  //   gold       金冠 = 全連 (FC)
  //   donderfull 虹冠 = 全良
  const CROWN_ORDER = ["none", "played", "silver", "gold", "donderfull"];
  const CROWN_RANK = { none: 0, played: 1, silver: 2, gold: 3, donderfull: 4 };
  const CROWN_LABEL = {
    none: "未遊玩", played: "已玩未通關", silver: "銀冠(通關)",
    gold: "金冠(FC)", donderfull: "虹冠(全良)",
  };

  // ---------- 按鈕 ----------
  const btn = document.createElement("button");
  btn.textContent = "📊 統計鬼/裏數量";
  Object.assign(btn.style, {
    position: "fixed", right: "16px", bottom: "104px", zIndex: 2147483647,
    background: "#4169e1", color: "#fff", border: "none", borderRadius: "8px",
    padding: "10px 14px", fontSize: "14px", fontWeight: "bold",
    cursor: "pointer", boxShadow: "0 2px 8px rgba(0,0,0,.4)",
    fontFamily: "sans-serif",
  });
  document.body.appendChild(btn);

  // ---------- 結果面板 ----------
  const panel = document.createElement("div");
  Object.assign(panel.style, {
    position: "fixed", right: "16px", bottom: "148px", zIndex: 2147483647,
    background: "rgba(15,15,22,.96)", color: "#fff", padding: "14px 16px",
    borderRadius: "10px", fontSize: "13px", maxWidth: "min(92vw, 480px)",
    display: "none", fontFamily: "sans-serif", lineHeight: "1.5",
    boxShadow: "0 4px 18px rgba(0,0,0,.55)", maxHeight: "72vh", overflowY: "auto",
  });
  document.body.appendChild(panel);
  const show = (html) => { panel.style.display = "block"; panel.innerHTML = html; };

  async function fetchText(url) {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) throw new Error("HTTP " + res.status + " @ " + url);
    return await res.text();
  }

  const newTally = () =>
    Object.assign({ total: 0 }, ...CROWN_ORDER.map((c) => ({ [c]: 0 })));

  // 供下載使用
  let lastTally = null;
  let lastDetail = null; // Array<[songNo, level, crown]>

  async function run() {
    btn.disabled = true; btn.style.opacity = "0.6";
    try {
      // 1) 刷新成績快取（best-effort，失敗也能讀既有成績）
      show("刷新成績快取…");
      try {
        const top = await fetchText("https://donderhiroba.jp/mypage_top.php");
        const topDoc = new DOMParser().parseFromString(top, "text/html");
        const tcktEl = topDoc.querySelector("#_tckt");
        const tckt = (tcktEl?.textContent?.trim())
          || tcktEl?.getAttribute("value")?.trim();
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
      } catch (e) { /* 忽略 */ }

      // 2) 逐曲風抓成績，去重保留最高冠色
      const best = new Map(); // key "songNo|level" -> crown
      for (let genre = 1; genre <= 8; genre++) {
        show(`讀取成績（曲風 ${genre}/8）…`);
        const html = await fetchText(
          `https://donderhiroba.jp/score_list.php?genre=${genre}`);
        const doc = new DOMParser().parseFromString(html, "text/html");
        doc.querySelectorAll('a[href*="score_detail.php"]').forEach((a) => {
          const href = a.getAttribute("href") || "";
          const sn = href.match(/song_no=(\d+)/);
          const lv = href.match(/level=(\d+)/);
          if (!sn || !lv) return;
          if (lv[1] !== "4" && lv[1] !== "5") return; // 只算鬼/裏
          let crown = "none";
          a.querySelectorAll("img").forEach((img) => {
            const cm = (img.getAttribute("src") || "")
              .match(/crown_button_([a-z]+)_/);
            if (cm && CROWN_RANK[cm[1]] !== undefined) crown = cm[1];
          });
          const key = `${sn[1]}|${lv[1]}`;
          const prev = best.get(key);
          if (prev === undefined || CROWN_RANK[crown] > CROWN_RANK[prev]) {
            best.set(key, crown);
          }
        });
      }

      // 3) 統計
      const tally = { "4": newTally(), "5": newTally() };
      const detail = [];
      best.forEach((crown, key) => {
        const [sn, lv] = key.split("|");
        tally[lv].total++;
        tally[lv][crown]++;
        detail.push([sn, lv, crown]);
      });
      lastTally = tally;
      lastDetail = detail;

      renderResult(tally);
    } catch (e) {
      show("失敗：" + e.message + "（請確認已登入 donderhiroba 並選好卡片）");
    } finally {
      btn.disabled = false; btn.style.opacity = "1";
    }
  }

  function renderResult(tally) {
    const cleared = (t) => t.silver + t.gold + t.donderfull;      // 通關以上
    const pct = (n, d) => (d ? (100 * n / d).toFixed(1) + "%" : "—");

    const cell = (v, align = "right") =>
      `<td style="padding:3px 8px;text-align:${align}">${v}</td>`;
    const head = (v, align = "right") =>
      `<th style="padding:3px 8px;text-align:${align};border-bottom:1px solid #555">${v}</th>`;

    const row = (lv) => {
      const t = tally[lv];
      return `<tr>
        ${cell(`<b>${LEVEL_LABEL[lv]}</b>`, "left")}
        ${cell(t.total)}${cell(t.none)}${cell(t.played)}
        ${cell(t.silver)}${cell(t.gold)}${cell(t.donderfull)}
        ${cell(`${cleared(t)}<br><span style="opacity:.6">${pct(cleared(t), t.total)}</span>`)}
      </tr>`;
    };

    show(`
      <div style="font-weight:bold;font-size:15px;margin-bottom:8px">🥁 鬼 / 裏 譜面統計</div>
      <table style="border-collapse:collapse;font-size:12px;width:100%">
        <tr>
          ${head("難度", "left")}${head("總數")}${head("未遊玩")}${head("未通關")}
          ${head("銀冠")}${head("金冠")}${head("虹冠")}${head("通關率")}
        </tr>
        ${row("4")}
        ${row("5")}
      </table>
      <div style="margin-top:8px;font-size:11px;opacity:.82">
        銀冠=通關、金冠=全連(FC)、虹冠=全良。「未遊玩」=該譜面存在但無成績；
        「通關率」=（銀+金+虹）÷ 總數。
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button data-act="csv"  style="cursor:pointer;background:#2e8b57;color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px">⬇ 明細 CSV</button>
        <button data-act="json" style="cursor:pointer;background:#8a6d1f;color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px">⬇ 統計 JSON</button>
        <button data-act="close" style="cursor:pointer;background:#555;color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px">關閉</button>
      </div>
    `);

    panel.querySelectorAll("button[data-act]").forEach((b) => {
      b.addEventListener("click", () => {
        const act = b.getAttribute("data-act");
        if (act === "close") { panel.style.display = "none"; return; }
        if (act === "csv") downloadCSV();
        if (act === "json") downloadJSON();
      });
    });
  }

  function download(name, text, type) {
    const blob = new Blob([text], { type });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function downloadCSV() {
    if (!lastDetail) return;
    const rows = [["song_no", "difficulty", "crown", "crown_label"]];
    lastDetail
      .sort((a, b) => (a[1] - b[1]) || (a[0] - b[0]))
      .forEach(([sn, lv, crown]) => {
        rows.push([sn, LEVEL_LABEL[lv], crown, CROWN_LABEL[crown]]);
      });
    const csv = "\uFEFF" + rows.map((r) => r.join(",")).join("\n"); // BOM 供 Excel
    download("oni_ura_detail.csv", csv, "text/csv;charset=utf-8");
  }

  function downloadJSON() {
    if (!lastTally) return;
    const out = {};
    ["4", "5"].forEach((lv) => {
      const t = lastTally[lv];
      out[LEVEL_LABEL[lv]] = {
        總數: t.total, 未遊玩: t.none, 已玩未通關: t.played,
        銀冠通關: t.silver, 金冠FC: t.gold, 虹冠全良: t.donderfull,
        通關以上: t.silver + t.gold + t.donderfull,
      };
    });
    download("oni_ura_summary.json", JSON.stringify(out, null, 2),
      "application/json");
  }

  btn.addEventListener("click", run);
})();
