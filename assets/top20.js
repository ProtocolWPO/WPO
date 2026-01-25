(() => {
  const $body = document.getElementById("top20-body");
  const $updated = document.getElementById("top20-updated");
  const $q = document.getElementById("top20-q");
  const $count = document.getElementById("top20-count");
  const $loading = document.getElementById("top20-loading");

  if (!$body || !$updated || !$q || !$count || !$loading) return;

  let raw = [];
  let sortKey = "rank";
  let sortDir = "asc";

  const fmtPrice = new Intl.NumberFormat("en-US", { maximumFractionDigits: 8 });
const fmtUSD = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });

  function compact(n){
    n = Number(n);
    if (!isFinite(n)) return "—";
    return fmtUSD.format(n);
  }

  function pct(n){
    n = Number(n);
    if (!isFinite(n)) return "—";
    return (n * 100).toFixed(2) + "%";
  }

  function showLoading(on){
    $loading.style.display = on ? "block" : "none";
  }

  function barWidth(item){
    const r = Math.min(Number(item.vol_mcap_ratio || 0), 2); // cap 200%
    return Math.max(6, Math.round((r / 2) * 100)); // 6% min
  }

  function render(){
    const q = ($q.value || "").trim().toLowerCase();

    const view = raw
      .filter(x => !q || (x.symbol||"").toLowerCase().includes(q) || (x.name||"").toLowerCase().includes(q))
      .sort((a,b) => {
        const dir = sortDir === "asc" ? 1 : -1;
        if (sortKey === "coin"){
          return ((a.symbol||"").toLowerCase()).localeCompare(((b.symbol||"").toLowerCase())) * dir;
        }
        return (Number(a[sortKey]) - Number(b[sortKey])) * dir;
      });

    $count.textContent = `${view.length} coins shown`;

    $body.innerHTML = view.map(x => `
      <tr>
        <td>${x.rank ?? "—"}</td>
        <td>
          <div class="top20CoinCell">
            <span class="top20Badge">${x.symbol || "—"}</span>
            <div class="top20CoinName">
              <b>${x.symbol || "—"}</b>
              <span>${x.name || ""}</span>
            </div>
          </div>
        </td>
        <td class="top20NumCell">${compact(x.volume_24h)}</td>
        <td class="top20NumCell">${compact(x.market_cap)}</td>
        <td class="top20NumCell">${Number(x.price) ? fmtPrice.format(Number(x.price)) : "—"}</td>
        <td class="top20NumCell top20VM">${pct(x.vol_mcap_ratio)}</td>
        <td>
          <div class="top20ActivityBar" title="Activity indicator">
            <i style="width:${barWidth(x)}%"></i>
          </div>
        </td>
      </tr>
    `).join("");
  }

  async function load(){
    try{
      showLoading(true);
      const res = await fetch("./data/top20.json?v=" + Date.now());
      const data = await res.json();

      raw = (data.items || []).map((x,i) => ({
        rank: x.rank ?? (i + 1),
        symbol: x.symbol,
        name: x.name,
        price: x.price,
        volume_24h: x.volume_24h,
        market_cap: x.market_cap,
        vol_mcap_ratio: x.vol_mcap_ratio
      }));

      $updated.textContent = `Updated (UTC): ${data.updated_utc || "—"}`;
      render();
    } catch (e) {
      console.error(e);
      $updated.textContent = "Failed to load data (top20.json not found)";
    } finally {
      showLoading(false);
    }
  }

  // sorting
  document.querySelectorAll(".wpo-top20__table thead th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.getAttribute("data-sort");
      if (!key) return;

      if (sortKey === key) {
        sortDir = (sortDir === "asc" ? "desc" : "asc");
      } else {
        sortKey = key;
        sortDir = (key === "rank" ? "asc" : "desc");
      }
      render();
    });
  });

  $q.addEventListener("input", render);

  load();
})();
