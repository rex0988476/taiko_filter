/*
 * stars.js — 在 donderhiroba 頁面注入「鬼/裏 星等難度表」按鈕
 * ------------------------------------------------------------------
 * 流程：
 *   1. 同 count.js：同源抓 score_list.php?genre=1..8，取得每個
 *      song_no|難度(4鬼/5裏) 的冠色（跨曲風去重、保留最高冠）。
 *   2. 向 background 索取 taiko.wiki 的曲目星等（song_no → {oni,ura}）。
 *   3. 以 song_no 對照，把每張譜面歸入「★N × 冠色」的格子，
 *      分別產生「鬼」與「裏」兩張 ★1..★10 難度表。
 *   4. 可下載完整矩陣 CSV。
 *
 * 註：分母採用「你成績頁實際存在的譜面」（即該卡片可玩曲目），
 *     而非 taiko.wiki 全曲，避免把你所在區域/版本沒有的曲目算進去。
 *     成績頁有、taiko.wiki 無對照者，歸入「★?」並單獨標示。
 */
(function () {
  if (window.__donderStarsInjected) return;
  window.__donderStarsInjected = true;

  const DIFFS = [
    { key: "oni", lv: "4", label: "鬼" },
    { key: "ura", lv: "5", label: "裏" },
  ];
  const CROWN_ORDER = ["none", "played", "silver", "gold", "donderfull"];
  const CROWN_RANK = { none: 0, played: 1, silver: 2, gold: 3, donderfull: 4 };
  const STARS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "?"];

  // ---------- 按鈕（放右上，避免與匯出/統計按鈕重疊）----------
  const btn = document.createElement("button");
  btn.textContent = "🎯 鬼/裏 星等難度表";
  Object.assign(btn.style, {
    position: "fixed", top: "16px", right: "16px", zIndex: 2147483647,
    background: "#b8860b", color: "#fff", border: "none", borderRadius: "8px",
    padding: "10px 14px", fontSize: "14px", fontWeight: "bold",
    cursor: "pointer", boxShadow: "0 2px 8px rgba(0,0,0,.4)",
    fontFamily: "sans-serif",
  });
  document.body.appendChild(btn);

  const panel = document.createElement("div");
  Object.assign(panel.style, {
    position: "fixed", top: "60px", right: "16px", zIndex: 2147483647,
    background: "rgba(15,15,22,.97)", color: "#fff", padding: "14px 16px",
    borderRadius: "10px", fontSize: "13px", maxWidth: "min(94vw, 620px)",
    display: "none", fontFamily: "sans-serif", lineHeight: "1.5",
    boxShadow: "0 4px 20px rgba(0,0,0,.6)", maxHeight: "86vh", overflowY: "auto",
  });
  document.body.appendChild(panel);
  const show = (html) => { panel.style.display = "block"; panel.innerHTML = html; };
  const setMsg = (t) => show(`<div style="font-size:13px">${t}</div>`);

  async function fetchText(url) {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) throw new Error("HTTP " + res.status + " @ " + url);
    return await res.text();
  }

  let lastMatrix = null; // { oni:{star:cell}, ura:{star:cell} }
  let lastMeta = null;

  const newCell = () =>
    Object.assign({ total: 0 }, ...CROWN_ORDER.map((c) => ({ [c]: 0 })));

  async function run(forceRefresh) {
    btn.disabled = true; btn.style.opacity = "0.6";
    try {
      // 1) 刷新成績快取（best-effort）
      setMsg("刷新成績快取…");
      try {
        const top = await fetchText("https://donderhiroba.jp/mypage_top.php");
        const el = new DOMParser().parseFromString(top, "text/html")
          .querySelector("#_tckt");
        const tckt = el?.textContent?.trim() || el?.getAttribute("value")?.trim();
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

      // 2) 抓成績頁，取每個 song_no|level 的最高冠色
      const best = new Map(); // "songNo|lv" -> crown
      for (let genre = 1; genre <= 8; genre++) {
        setMsg(`讀取成績（曲風 ${genre}/8）…`);
        const html = await fetchText(
          `https://donderhiroba.jp/score_list.php?genre=${genre}`);
        const doc = new DOMParser().parseFromString(html, "text/html");
        doc.querySelectorAll('a[href*="score_detail.php"]').forEach((a) => {
          const href = a.getAttribute("href") || "";
          const sn = href.match(/song_no=(\d+)/);
          const lv = href.match(/level=(\d+)/);
          if (!sn || !lv) return;
          if (lv[1] !== "4" && lv[1] !== "5") return;
          let crown = "none";
          a.querySelectorAll("img").forEach((img) => {
            const cm = (img.getAttribute("src") || "").match(/crown_button_([a-z]+)_/);
            if (cm && CROWN_RANK[cm[1]] !== undefined) crown = cm[1];
          });
          const key = `${sn[1]}|${lv[1]}`;
          const prev = best.get(key);
          if (prev === undefined || CROWN_RANK[crown] > CROWN_RANK[prev]) {
            best.set(key, crown);
          }
        });
      }

      // 3) 取 taiko.wiki 星等
      setMsg("取得 taiko.wiki 星等資料…");
      const resp = await chrome.runtime.sendMessage({
        type: "GET_SONG_LEVELS", forceRefresh: !!forceRefresh,
      });
      if (!resp || !resp.ok) {
        throw new Error("取得星等失敗：" + (resp?.error || "background 無回應")
          + "（請確認 manifest 已含 background 與 taiko.wiki 權限）");
      }
      const levels = resp.map;

      // 4) 建矩陣
      const matrix = { oni: {}, ura: {} };
      STARS.forEach((s) => { matrix.oni[s] = newCell(); matrix.ura[s] = newCell(); });
      let unmatched = 0;
      best.forEach((crown, key) => {
        const [sn, lv] = key.split("|");
        const d = lv === "4" ? "oni" : "ura";
        const star = levels[sn] ? levels[sn][d] : null;
        const bucket = star ? String(star) : "?";
        const cell = matrix[d][bucket] || (matrix[d][bucket] = newCell());
        cell[crown]++; cell.total++;
        if (!star) unmatched++;
      });

      lastMatrix = matrix;
      lastMeta = {
        cached: resp.cached, ts: resp.ts, unmatched,
        songCount: Object.keys(levels).length,
      };
      render(matrix, lastMeta);
    } catch (e) {
      setMsg("失敗：" + e.message);
    } finally {
      btn.disabled = false; btn.style.opacity = "1";
    }
  }

  function render(matrix, meta) {
    const cleared = (c) => c.silver + c.gold + c.donderfull;
    const pct = (n, d) => (d ? (100 * n / d).toFixed(0) + "%" : "—");
    const cell = (v, a = "right") => `<td style="padding:2px 7px;text-align:${a}">${v}</td>`;
    const head = (v, a = "right") =>
      `<th style="padding:2px 7px;text-align:${a};border-bottom:1px solid #555;white-space:nowrap">${v}</th>`;

    function table(d) {
      const rowsHtml = STARS
        .filter((s) => matrix[d][s].total > 0)
        .map((s) => {
          const c = matrix[d][s];
          const label = s === "?" ? "★?" : "★" + s;
          return `<tr>
            ${cell(`<b>${label}</b>`, "left")}
            ${cell(c.total)}${cell(c.none)}${cell(c.played)}
            ${cell(c.silver)}${cell(c.gold)}${cell(c.donderfull)}
            ${cell(pct(cleared(c), c.total))}</tr>`;
        }).join("");
      // 合計列
      const sum = newCell();
      STARS.forEach((s) => CROWN_ORDER.concat("total").forEach((k) => (sum[k] += matrix[d][s][k])));
      const sumRow = `<tr style="border-top:1px solid #555;font-weight:bold">
        ${cell("合計", "left")}${cell(sum.total)}${cell(sum.none)}${cell(sum.played)}
        ${cell(sum.silver)}${cell(sum.gold)}${cell(sum.donderfull)}${cell(pct(cleared(sum), sum.total))}</tr>`;

      const label = d === "oni" ? "鬼" : "裏";
      return `<div style="font-weight:bold;margin:10px 0 4px">${label} 難度表</div>
        <table style="border-collapse:collapse;font-size:12px;width:100%">
          <tr>${head("難度", "left")}${head("總數")}${head("未玩")}${head("未通")}
            ${head("銀")}${head("金")}${head("虹")}${head("通關率")}</tr>
          ${rowsHtml || `<tr>${cell("（無資料）", "left")}</tr>`}
          ${sumRow}
        </table>`;
    }

    const when = meta.ts ? new Date(meta.ts).toLocaleString() : "—";
    show(`
      <div style="font-weight:bold;font-size:15px;margin-bottom:2px">🥁 鬼 / 裏 星等難度表</div>
      <div style="font-size:11px;opacity:.75;margin-bottom:4px">
        星等來源 taiko.wiki（${meta.cached ? "快取" : "剛更新"}，${when}，收錄 ${meta.songCount} 曲）
        ${meta.unmatched ? `・未對照 ${meta.unmatched} 張歸入 ★?` : ""}
      </div>
      ${table("oni")}
      ${table("ura")}
      <div style="margin-top:8px;font-size:11px;opacity:.82">
        銀=通關、金=全連(FC)、虹=全良、未通=已玩未通關、未玩=有譜面無成績。
        通關率=（銀+金+虹）÷總數。分母為你成績頁實際存在的譜面。
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
        <button data-act="csv"     style="cursor:pointer;background:#2e8b57;color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px">⬇ 難度表 CSV</button>
        <button data-act="refresh" style="cursor:pointer;background:#4169e1;color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px">↻ 重新抓星等</button>
        <button data-act="close"   style="cursor:pointer;background:#555;color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px">關閉</button>
      </div>
    `);

    panel.querySelectorAll("button[data-act]").forEach((b) =>
      b.addEventListener("click", () => {
        const act = b.getAttribute("data-act");
        if (act === "close") panel.style.display = "none";
        else if (act === "csv") downloadCSV();
        else if (act === "refresh") run(true);
      }));
  }

  function downloadCSV() {
    if (!lastMatrix) return;
    const rows = [["difficulty", "star", "total", "none_未玩", "played_未通",
      "silver_銀", "gold_金", "donderfull_虹", "cleared_通關以上"]];
    DIFFS.forEach(({ key, label }) => {
      STARS.forEach((s) => {
        const c = lastMatrix[key][s];
        if (!c || c.total === 0) return;
        rows.push([label, s === "?" ? "?" : s, c.total, c.none, c.played,
          c.silver, c.gold, c.donderfull, c.silver + c.gold + c.donderfull]);
      });
    });
    const csv = "\uFEFF" + rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "oni_ura_starchart.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  btn.addEventListener("click", () => run(false));
})();
