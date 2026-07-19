/*
 * background.js — service worker
 * ------------------------------------------------------------------
 * 從 taiko.wiki 取得曲目星等資料並快取。
 * 之所以放在 background（而非 content script）：對 taiko.wiki 的跨來源
 * 請求需要擴充的 host_permissions 才能免除 CORS；content script 直接
 * fetch 會被 CORS 擋下。background 取回後再回傳給 content script。
 *
 * 資料來源與 donder-hiroba-plus 相同：
 *   https://taiko.wiki/api/song?after=0   （after=0 代表取全部）
 * 每首歌的 songNo 即 donderhiroba 的 song_no；
 * 星等在 courses.oni.level / courses.ura.level（部分快照放在 oni_ura）。
 */
const SONG_API = "https://taiko.wiki/api/song?after=0";
const CACHE_KEY = "songLevels";
const CACHE_TS = "songLevelsTs";
const ONE_DAY = 24 * 60 * 60 * 1000;

async function buildLevelMap() {
  const res = await fetch(SONG_API);
  if (!res.ok) throw new Error("taiko.wiki HTTP " + res.status);
  const arr = await res.json();
  if (!Array.isArray(arr)) throw new Error("taiko.wiki 回傳格式非陣列");

  const map = {};
  for (const s of arr) {
    if (!s || s.songNo == null || !s.courses) continue;
    const c = s.courses;
    const oni = c.oni?.level ?? null;
    // 相容兩種快照：新版 courses.ura、舊版 courses.oni_ura
    const ura = c.ura?.level ?? c.oni_ura?.level ?? null;
    if (oni == null && ura == null) continue;
    map[String(s.songNo)] = {
      oni, ura,
      title: s.title ?? null,
      deleted: s.isDeleted ? 1 : 0,
    };
  }
  return map;
}

async function getSongLevels(forceRefresh) {
  const now = Date.now();
  if (!forceRefresh) {
    const c = await chrome.storage.local.get([CACHE_KEY, CACHE_TS]);
    if (c[CACHE_KEY] && c[CACHE_TS] && now - c[CACHE_TS] < ONE_DAY) {
      return { map: c[CACHE_KEY], cached: true, ts: c[CACHE_TS] };
    }
  }
  const map = await buildLevelMap();
  await chrome.storage.local.set({ [CACHE_KEY]: map, [CACHE_TS]: now });
  return { map, cached: false, ts: now };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "GET_SONG_LEVELS") {
    getSongLevels(!!msg.forceRefresh)
      .then((r) => sendResponse({ ok: true, ...r }))
      .catch((e) => sendResponse({ ok: false, error: String(e.message || e) }));
    return true; // 保持通道開啟以便非同步 sendResponse
  }
});
