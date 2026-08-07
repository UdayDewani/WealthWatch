const WS_URL = `ws://${location.host}/ws`;

let ws = null;
let currentMarketData = null;
let currentStockIndex = 'nifty50';
let activePage = 'dashboard';

// Tab switching
function navigate(pageId) {
  activePage = pageId;
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.getAttribute('data-page') === pageId) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  document.querySelectorAll('.page').forEach(page => {
    if (page.id === `page-${pageId}`) {
      page.classList.add('active');
    } else {
      page.classList.remove('active');
    }
  });
}

// Index switching for stocks table
function switchStockIndex(idxType) {
  currentStockIndex = idxType;
  const btn50 = document.getElementById('btnNifty50');
  const btnBank = document.getElementById('btnNiftyBank');
  const countSpan = document.getElementById('stocksCount');

  if (idxType === 'nifty50') {
    btn50.style.background = 'var(--card-bg)';
    btn50.style.color = 'var(--primary)';
    btn50.style.boxShadow = 'var(--shadow)';
    
    btnBank.style.background = 'transparent';
    btnBank.style.color = 'var(--text-secondary)';
    btnBank.style.boxShadow = 'none';
    
    countSpan.textContent = '50 Stocks';
  } else {
    btnBank.style.background = 'var(--card-bg)';
    btnBank.style.color = 'var(--primary)';
    btnBank.style.boxShadow = 'var(--shadow)';
    
    btn50.style.background = 'transparent';
    btn50.style.color = 'var(--text-secondary)';
    btn50.style.boxShadow = 'none';
    
    countSpan.textContent = '12 Stocks';
  }

  if (currentMarketData) {
    renderStocksTable(currentMarketData);
  }
}

// ---------------------------------------------------------------------------
// Auth banner helpers
// ---------------------------------------------------------------------------
function showAuthBanner(authUrl, message) {
  let banner = document.getElementById('authBanner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'authBanner';
    banner.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:9999',
      'background:#dc2626', 'color:#fff', 'padding:12px 24px',
      'display:flex', 'align-items:center', 'justify-content:space-between',
      'font-size:14px', 'font-weight:500', 'gap:16px', 'box-shadow:0 2px 12px rgba(0,0,0,.2)'
    ].join(';');
    document.body.appendChild(banner);
  }
  banner.innerHTML = `
    <span>⚠️ ${message || 'Upstox session expired. Live data paused.'}</span>
    <div style="display:flex;gap:12px;align-items:center;">
      <a href="${authUrl}" style="background:#fff;color:#dc2626;padding:6px 16px;border-radius:6px;font-weight:700;text-decoration:none;font-size:13px;">Re-Authorize Upstox →</a>
      <button onclick="document.getElementById('authBanner').style.display='none'" style="background:none;border:1px solid rgba(255,255,255,.4);color:#fff;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px;">Dismiss</button>
    </div>
  `;
  banner.style.display = 'flex';
}

function hideAuthBanner() {
  const banner = document.getElementById('authBanner');
  if (banner) banner.style.display = 'none';
}

function connectWebSocket() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    const dot = document.getElementById('liveDot');
    const label = document.getElementById('liveLabel');
    if (dot) dot.className = 'live-dot active';
    if (label) label.textContent = 'LIVE';
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // --- Auth required state ---
    if (data.auth_required) {
      const dot = document.getElementById('liveDot');
      const label = document.getElementById('liveLabel');
      if (dot) { dot.className = 'live-dot'; dot.style.background = '#f59e0b'; }
      if (label) label.textContent = 'AUTH REQUIRED';
      showAuthBanner(data.auth_url, data.message);
      // Show friendly message in the stocks table
      const tbody = document.getElementById('stocksBody');
      if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:32px;color:#64748b;">
        ⚠️ Live data paused — <a href="${data.auth_url}" style="color:#2563eb;font-weight:600;">click here to re-authorize Upstox</a>
      </td></tr>`;
      return;
    }

    // --- Live data received — clear auth banner ---
    hideAuthBanner();
    currentMarketData = data;
    updateDashboard(data);
  };

  ws.onclose = () => {
    const dot = document.getElementById('liveDot');
    const label = document.getElementById('liveLabel');
    if (dot) { dot.className = 'live-dot inactive'; dot.style.background = ''; }
    if (label) label.textContent = 'OFFLINE';
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function updateDashboard(data) {
  const now = new Date().toLocaleTimeString();
  const updateTime = document.getElementById("updateTime");
  if (updateTime) updateTime.textContent = `Updated at ${now}`;

  // Update indices
  const indices = data.indices || {
    nifty: data.nifty,
    sensex: data.sensex
  };
  
  if (indices.nifty) updateIndexCard("nifty", indices.nifty);
  if (indices.sensex) updateIndexCard("sensex", indices.sensex);
  if (indices.niftybank) updateIndexCard("niftybank", indices.niftybank);
  if (indices.niftyit) updateIndexCard("niftyit", indices.niftyit);

  // Update Overall Summary Card
  const summaryText = document.getElementById("summaryText");
  const summaryBadge = document.getElementById("summaryBadge");
  
  if (data.analysis && data.analysis.summary) {
    if (summaryText) summaryText.textContent = data.analysis.summary;
    if (summaryBadge) {
      summaryBadge.textContent = "ANALYZED";
      summaryBadge.className = "badge bullish";
    }
  } else if (data.summary) {
    if (summaryText) summaryText.textContent = data.summary;
  }

  if (data.news) updateNews(data.news);
  
  if (data.analysis) {
    applyAnalysis("nifty", data.analysis.nifty);
    applyAnalysis("sensex", data.analysis.sensex);
    applyAnalysis("niftybank", data.analysis.niftybank);
    applyAnalysis("niftyit", data.analysis.niftyit);
    
    if (data.analysis.recommendations) {
      updateRecommendations(data.analysis.recommendations);
    }
  }

  renderStocksTable(data);
}

function updateIndexCard(prefix, data) {
  const priceEl = document.getElementById(`${prefix}Price`);
  const changeEl = document.getElementById(`${prefix}Change`);
  
  if (priceEl && data.price != null) {
    priceEl.textContent = formatPrice(data.price);
  }
  if (changeEl && data.change != null) {
    const sign = data.change >= 0 ? "+" : "";
    const cls = data.change >= 0 ? "pos" : "neg";
    changeEl.innerHTML =
      `<span class="change ${cls}">${sign}${data.change.toFixed(2)} (${sign}${data.change_pct?.toFixed(2) || "0.00"}%)</span>`;
  }
}

function applyAnalysis(prefix, analysis) {
  if (!analysis) return;
  const condition = analysis.condition || "neutral";
  const badge = document.getElementById(`${prefix}Badge`);

  if (badge) {
    badge.textContent = condition.toUpperCase();
    badge.className = `badge ${condition}`;
  }
}

function updateNews(news) {
  if (!news || news.length === 0) return;
  // Vanilla index.html doesn't have a newsContainer on dashboard, 
  // but if we ever add one, this prevents errors.
  const container = document.getElementById("newsContainer");
  if (container) {
    container.innerHTML = news.map(n =>
      `<div class="news-item">
        <a href="${n.link || "#"}" target="_blank">
          ${n.title}
        </a>
        <span class="text-secondary small">${n.publisher || ""}</span>
      </div>`
    ).join("");
  }
}

function renderStocksTable(data) {
  const tbody = document.getElementById("stocksBody");
  if (!tbody) return;

  const stockList = data.stocks ? data.stocks[currentStockIndex] : [];
  if (!stockList || stockList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state" style="text-align:center;">Loading constituent stock quotes...</td></tr>`;
    return;
  }

  tbody.innerHTML = stockList.map(s => {
    const changeColor = s.change_pct >= 0 ? 'var(--green)' : 'var(--red)';
    const changeSign = s.change_pct >= 0 ? '+' : '';
    const volStr = s.volume >= 1e7 ? (s.volume / 1e7).toFixed(1) + 'Cr' : s.volume >= 1e5 ? (s.volume / 1e5).toFixed(1) + 'L' : s.volume.toLocaleString();
    return `
      <tr>
        <td class="rank">${s.rank}</td>
        <td>
          <div class="stock-info">
            <div class="stock-logo">${s.symbol.slice(0, 2)}</div>
            <div>
              <div class="stock-name">${s.name}</div>
              <div class="stock-symbol">${s.symbol}</div>
            </div>
          </div>
        </td>
        <td style="text-align:right; font-weight:600;">${formatPrice(s.price)}</td>
        <td style="text-align:right; color:${changeColor}; font-weight:600;">
          ${changeSign}${s.change_pct.toFixed(2)}%
        </td>
        <td style="text-align:right; color:var(--text-secondary);">${volStr}</td>
      </tr>
    `;
  }).join("");
}

function updateRecommendations(recs) {
  const grid = document.getElementById("recGrid");
  if (!grid || !recs || recs.length === 0) return;

  grid.innerHTML = recs.map(r => {
    const barColor = r.confidence >= 85 ? 'var(--green)' : r.confidence >= 70 ? '#eab308' : 'var(--primary)';
    return `
      <div class="rec-card">
        <div class="top">
          <div>
            <div class="stock">${r.stock}</div>
            <div style="font-size:12px; color:var(--text-secondary);">${r.symbol}</div>
          </div>
          <span class="action ${r.action}">${r.action.toUpperCase()}</span>
        </div>
        <div class="reason">${r.reason}</div>
        <div>
          <div class="confidence-label">
            <span>AI Confidence</span>
            <span>${r.confidence}%</span>
          </div>
          <div class="confidence-bar">
            <div class="fill" style="width: ${r.confidence}%; background: ${barColor};"></div>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

// Drawer for explanations
function openDrawerFor(indexId) {
  const overlay = document.getElementById("drawerOverlay");
  const drawer = document.getElementById("drawer");
  const title = document.getElementById("drawerTitle");
  const content = document.getElementById("drawerContent");

  if (!overlay || !drawer) return;

  const analysis = currentMarketData && currentMarketData.analysis ? currentMarketData.analysis[indexId] : null;
  const condition = analysis ? analysis.condition.toUpperCase() : "NEUTRAL";
  const reasoning = analysis ? analysis.reasoning : "Market consolidation observed.";

  title.textContent = `${indexId.toUpperCase().replace("NIFTY", "NIFTY ")} — ${condition} Outlook`;
  
  content.innerHTML = `
    <div style="background:var(--nav-bg); border-radius:8px; padding:16px; margin-bottom:20px; border-left:4px solid var(--primary); font-size:13px;">
      <strong style="display:block; margin-bottom:4px; color:var(--text);">AI Analysis Summary</strong>
      <span style="color:var(--text-secondary); line-height:1.6;">${reasoning}</span>
    </div>
    <div style="font-size:14px; margin-bottom:8px; font-weight:600;">Standard Indices Factors:</div>
    <div class="explanation-item">
      <span class="dot pos"></span>
      <div class="text">
        <div class="label">Valuation Multiples</div>
        <div class="desc">Current indices levels support standard long term growth projection.</div>
      </div>
    </div>
    <div class="explanation-item">
      <span class="dot pos"></span>
      <div class="text">
        <div class="label">Institutional Support</div>
        <div class="desc">Strong retail and institutional backing limits major downside risk.</div>
      </div>
    </div>
  `;

  overlay.classList.add("open");
  drawer.classList.add("open");
}

function closeDrawer() {
  const overlay = document.getElementById("drawerOverlay");
  const drawer = document.getElementById("drawer");
  if (overlay) overlay.classList.remove("open");
  if (drawer) drawer.classList.remove("open");
}

function formatPrice(val) {
  return val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

connectWebSocket();

// Fetch initial data
fetch("/api/market/overview")
  .then(r => r.json())
  .then(data => {
    currentMarketData = data;
    updateDashboard(data);
  })
  .catch(() => {});
