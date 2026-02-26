import { jget, fmt2, accountLabel } from "./js/api.js";
import { setActiveNav } from "./js/ui.js";

const now = new Date();
let currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
let currentView = "daily";
let monthlyTrendCache = {};
const accountDisplayNameByCode = {};

function formatAmount(amount) {
  return `¥${fmt2(amount || 0)}`;
}

function showError(msg) {
  const el = document.getElementById("err");
  if (!el) return;
  el.textContent = msg;
  el.style.display = "block";
}

function clearError() {
  const el = document.getElementById("err");
  if (!el) return;
  el.textContent = "";
  el.style.display = "none";
}

function showAddTxMessage(msg, type) {
  const el = document.getElementById("addTxMsg");
  if (!el) return;
  el.textContent = msg;
  el.style.color = type === "success" ? "#3fb950" : "#f85149";
  setTimeout(() => {
    el.textContent = "";
  }, 3000);
}

function accountDisplayName(accountCode, backendName) {
  const mapped = accountLabel(accountCode);
  if (mapped && mapped !== accountCode) return mapped;
  if (backendName && String(backendName).trim() && String(backendName).trim() !== accountCode) return String(backendName).trim();
  if (accountCode && accountDisplayNameByCode[accountCode]) return accountDisplayNameByCode[accountCode];
  return accountCode || "-";
}

function updateFiltersFromUI() {
  const view = document.getElementById("viewMode")?.value || "operating";
  const includeLarge = (document.getElementById("includeLarge")?.value || "exclude") === "include";
  const threshold = Number(document.getElementById("largeThreshold")?.value || 5000);
  return {
    view,
    includeLarge,
    largeThreshold: Number.isFinite(threshold) && threshold >= 0 ? threshold : 5000,
  };
}

function buildFilterQuery() {
  const f = updateFiltersFromUI();
  const params = new URLSearchParams();
  params.set("view", f.view);
  params.set("include_large", String(f.includeLarge));
  params.set("large_threshold", String(f.largeThreshold));
  return params.toString();
}

function mergeAccountRowsByDisplayName(rows) {
  const merged = new Map();
  (rows || []).forEach((row) => {
    const name = accountDisplayName(row.account_code, row.account_name);
    if (!merged.has(name)) {
      merged.set(name, {
        account_name: name,
        income_cny: 0,
        expense_cny: 0,
        monthly_net_flow_cny: 0,
        account_asset_cny: 0,
      });
    }
    const b = merged.get(name);
    b.income_cny += Number(row.income_cny || 0);
    b.expense_cny += Number(row.expense_cny || 0);
    b.monthly_net_flow_cny += Number(row.monthly_net_flow_cny || 0);
    b.account_asset_cny += Number(row.account_asset_cny || 0);
  });
  return Array.from(merged.values()).sort((a, b) => Math.abs(b.account_asset_cny) - Math.abs(a.account_asset_cny));
}

function renderLargeSummary(stats) {
  const el = document.getElementById("largeSummary");
  if (!el) return;
  const f = stats?.filters;
  if (!f) {
    el.textContent = "";
    return;
  }
  const parts = [
    `口径: ${f.view === "operating" ? "经营口径" : "全量口径"}`,
    `大额阈值: ${formatAmount(f.large_threshold_cny || 0)}`,
  ];
  if (!f.include_large) {
    parts.push(`排除大额: ${f.excluded_large_count || 0} 笔`);
    parts.push(`排除金额: ${formatAmount(f.excluded_large_amount_cny || 0)}`);
  }
  if (f.view === "operating") {
    parts.push(`排除内部划转: ${f.excluded_transfer_count || 0} 笔`);
  }
  el.textContent = parts.join(" | ");
}

function renderAccountDistChart(rows) {
  const canvas = document.getElementById("accountDistChart");
  if (!canvas) return;
  if (window.__accountDistChart) {
    window.__accountDistChart.destroy();
    window.__accountDistChart = null;
  }
  const dataRows = (rows || []).filter((r) => Number(r.account_asset_cny || 0) > 0);
  if (!dataRows.length) return;

  const labels = dataRows.map((r) => r.account_name);
  const values = dataRows.map((r) => Number(r.account_asset_cny || 0));
  const colors = ["#58a6ff", "#3fb950", "#f2cc60", "#f78166", "#bc8cff", "#79c0ff", "#ffa657", "#7ee787", "#d2a8ff"];

  window.__accountDistChart = new Chart(canvas, {
    type: "pie",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors.slice(0, values.length), borderColor: "#0b0e11", borderWidth: 2 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#e1e4e8", font: { size: 11 } } },
      },
    },
  });
}

function renderAccountPivot(pivotResp) {
  const tbody = document.querySelector("#accountPivotTable tbody");
  const note = document.getElementById("accountPivotNote");
  if (!tbody || !note) return;
  tbody.innerHTML = "";

  const mergedRows = mergeAccountRowsByDisplayName(pivotResp?.rows || []);
  const nonEmptyRows = mergedRows.filter(
    (r) =>
      Math.abs(Number(r.account_asset_cny || 0)) > 0.000001 ||
      Math.abs(Number(r.income_cny || 0)) > 0.000001 ||
      Math.abs(Number(r.expense_cny || 0)) > 0.000001 ||
      Math.abs(Number(r.monthly_net_flow_cny || 0)) > 0.000001,
  );
  const displayRows = nonEmptyRows.length ? nonEmptyRows : mergedRows;
  if (!displayRows.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#6e7681;padding:20px;">暂无账户数据</td></tr>';
    note.textContent = "";
    renderAccountDistChart([]);
    return;
  }

  displayRows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.account_name}</td>
      <td class="num amount-income">${formatAmount(r.income_cny)}</td>
      <td class="num amount-expense">${formatAmount(r.expense_cny)}</td>
      <td class="num ${r.account_asset_cny >= 0 ? "amount-income" : "amount-expense"}">${formatAmount(r.account_asset_cny)}</td>
    `;
    tbody.appendChild(tr);
  });

  const totalIncome = displayRows.reduce((s, r) => s + r.income_cny, 0);
  const totalExpense = displayRows.reduce((s, r) => s + r.expense_cny, 0);
  const totalNet = displayRows.reduce((s, r) => s + r.monthly_net_flow_cny, 0);
  const totalAsset = displayRows.reduce((s, r) => s + r.account_asset_cny, 0);
  note.textContent = `账户数: ${displayRows.length} | 月收入: ${formatAmount(totalIncome)} | 月支出: ${formatAmount(totalExpense)} | 月净流: ${formatAmount(totalNet)} | 账户资产: ${formatAmount(totalAsset)} | 资产快照: ${pivotResp?.holdings_as_of || "-"}`;
  renderAccountDistChart(displayRows);
}

function renderCategoryChart(categories) {
  const canvas = document.getElementById("categoryChart");
  if (!canvas) return;
  if (window.__categoryChart) {
    window.__categoryChart.destroy();
    window.__categoryChart = null;
  }

  if (!categories?.length) return;

  const colors = ["#f85149", "#58a6ff", "#d29922", "#3fb950", "#bc8cff", "#6e7681", "#1f6feb", "#da3633"];
  window.__categoryChart = new Chart(canvas, {
    type: "pie",
    data: {
      labels: categories.map((c) => c.category),
      datasets: [{ data: categories.map((c) => Number(c.amount || 0)), backgroundColor: colors.slice(0, categories.length), borderColor: "#0b0e11", borderWidth: 2 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "right", labels: { color: "#e1e4e8", font: { size: 12 } } } },
    },
  });
}

async function renderDailyChart() {
  const dailyData = await jget(`/api/transactions/daily/${currentMonth}?${buildFilterQuery()}`);
  const canvas = document.getElementById("trendChart");
  if (!canvas) return;
  if (window.__trendChart) window.__trendChart.destroy();
  if (!dailyData?.length) return;

  window.__trendChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: dailyData.map((d) => d.day),
      datasets: [
        { label: "收入", data: dailyData.map((d) => Number(d.income || 0)), borderColor: "#3fb950", backgroundColor: "rgba(63, 185, 80, 0.08)", fill: true, tension: 0.3 },
        { label: "支出", data: dailyData.map((d) => Number(d.expense || 0)), borderColor: "#f85149", backgroundColor: "rgba(248, 81, 73, 0.08)", fill: true, tension: 0.3 },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

function getYearMonths(monthValue) {
  const year = monthValue.split("-")[0];
  return Array.from({ length: 12 }, (_, i) => `${year}-${String(i + 1).padStart(2, "0")}`);
}

async function renderMonthlyChart() {
  const months = getYearMonths(currentMonth);
  const cacheKey = `${months[0].slice(0, 4)}|${buildFilterQuery()}`;
  let rows = monthlyTrendCache[cacheKey];
  if (!rows) {
    rows = await Promise.all(
      months.map((m) =>
        jget(`/api/transactions/monthly/${m}?${buildFilterQuery()}`).catch(() => ({
          total_income: 0,
          total_expense: 0,
          net: 0,
        })),
      ),
    );
    monthlyTrendCache[cacheKey] = rows;
  }

  const canvas = document.getElementById("trendChart");
  if (!canvas) return;
  if (window.__trendChart) window.__trendChart.destroy();
  window.__trendChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: months,
      datasets: [
        { label: "收入", data: rows.map((r) => Number(r.total_income || 0)), borderColor: "#3fb950", backgroundColor: "rgba(63, 185, 80, 0.08)", fill: true, tension: 0.3 },
        { label: "支出", data: rows.map((r) => Number(r.total_expense || 0)), borderColor: "#f85149", backgroundColor: "rgba(248, 81, 73, 0.08)", fill: true, tension: 0.3 },
        { label: "结余", data: rows.map((r) => Number(r.net || 0)), borderColor: "#58a6ff", fill: false, tension: 0.3, borderDash: [5, 5] },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

async function loadRecentTransactions() {
  const resp = await jget("/api/transactions/recent?limit=30&include_transfers=true");
  const rows = resp.transactions || [];
  const tbody = document.querySelector("#transactionTable tbody");
  const note = document.getElementById("txNote");
  if (!tbody || !note) return;
  tbody.innerHTML = "";
  if (!rows.length) {
    note.textContent = "";
    return;
  }
  rows.forEach((tx) => {
    const tr = document.createElement("tr");
    const amt = Number(tx.amount_cny != null ? tx.amount_cny : tx.amount);
    const amountClass = amt >= 0 ? "amount-income" : "amount-expense";
    const amountText = amt >= 0 ? `+${formatAmount(amt)}` : `-${formatAmount(Math.abs(amt))}`;
    const acctName = accountDisplayName(tx.account_code, tx.account_name);
    tr.innerHTML = `<td>${tx.date}</td><td>${tx.category || "-"}</td><td>${tx.description || "-"}</td><td>${tx.currency || "CNY"}</td><td>${acctName}</td><td style="text-align:right" class="${amountClass}">${amountText}</td>`;
    tbody.appendChild(tr);
  });
  note.textContent = `共 ${rows.length} 条记录`;
}

async function loadAccounts() {
  const resp = await jget("/api/accounts");
  const accounts = resp.accounts || [];
  Object.keys(accountDisplayNameByCode).forEach((k) => delete accountDisplayNameByCode[k]);
  accounts.forEach((a) => {
    const mapped = accountLabel(a.account_code);
    accountDisplayNameByCode[a.account_code] =
      mapped && mapped !== a.account_code ? mapped : a.display_name || a.account_code;
  });

  const uniqueAccounts = [];
  const seenNames = new Set();
  accounts.forEach((a) => {
    const name = accountDisplayName(a.account_code, a.display_name);
    if (seenNames.has(name)) return;
    seenNames.add(name);
    uniqueAccounts.push(a);
  });

  const opts = uniqueAccounts.map((a) => `<option value="${a.account_code}">${accountDisplayName(a.account_code, a.display_name)}</option>`).join("");
  ["txAccount", "transferFromAccount", "transferToAccount"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = opts;
  });
}

async function loadMonthData() {
  clearError();
  try {
    const [stats, pivot] = await Promise.all([
      jget(`/api/transactions/monthly/${currentMonth}?${buildFilterQuery()}`),
      jget(`/api/transactions/account-pivot/${currentMonth}?${buildFilterQuery()}`),
    ]);

    document.getElementById("kpiIncome").textContent = formatAmount(Number(stats.total_income || 0));
    document.getElementById("kpiExpense").textContent = formatAmount(Number(stats.total_expense || 0));
    const net = Number(stats.net || 0);
    const netEl = document.getElementById("kpiNet");
    netEl.textContent = formatAmount(net);
    netEl.className = `kpi-value net ${net >= 0 ? "positive" : "negative"}`;

    renderLargeSummary(stats);
    renderAccountPivot(pivot);
    renderCategoryChart(stats.by_category || []);
    if (currentView === "daily") await renderDailyChart();
    else await renderMonthlyChart();
    await loadRecentTransactions();
  } catch (err) {
    showError(`加载失败: ${err.message || err}`);
  }
}

function resetCaches() {
  monthlyTrendCache = {};
}

function changeMonth(delta) {
  const [y, m] = currentMonth.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  currentMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  document.getElementById("currentMonth").textContent = currentMonth;
  resetCaches();
  loadMonthData();
}

function switchView(view) {
  currentView = view;
  document.getElementById("tabDaily").classList.toggle("active", view === "daily");
  document.getElementById("tabMonthly").classList.toggle("active", view === "monthly");
  loadMonthData();
}

async function addTransaction() {
  const amount = Number(document.getElementById("txAmount").value);
  const type = document.getElementById("txType").value;
  const currency = document.getElementById("txCurrency").value;
  const account = document.getElementById("txAccount").value;
  const category = document.getElementById("txCategory").value.trim();
  const description = document.getElementById("txDescription").value.trim();
  if (!amount || amount <= 0) return showAddTxMessage("请输入有效金额", "error");
  if (!category) return showAddTxMessage("请输入分类", "error");

  const body = {
    date: new Date().toISOString().split("T")[0],
    amount: type === "expense" ? -Math.abs(amount) : Math.abs(amount),
    currency,
    account_code: account,
    category,
    description: description || null,
    source: "manual",
  };
  try {
    const resp = await fetch("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    showAddTxMessage("添加成功", "success");
    document.getElementById("txAmount").value = "";
    document.getElementById("txCategory").value = "";
    document.getElementById("txDescription").value = "";
    resetCaches();
    await loadMonthData();
  } catch (err) {
    showAddTxMessage(`添加失败: ${err.message || err}`, "error");
  }
}

async function addTransfer() {
  const fromAmount = Number(document.getElementById("transferFromAmount").value);
  const fromCurrency = document.getElementById("transferFromCurrency").value;
  const toAmountRaw = document.getElementById("transferToAmount").value;
  const toAmount = toAmountRaw ? Number(toAmountRaw) : fromAmount;
  const toCurrency = document.getElementById("transferToCurrency").value || fromCurrency;
  const from = document.getElementById("transferFromAccount").value;
  const to = document.getElementById("transferToAccount").value;
  const description = document.getElementById("transferDescription").value.trim();

  if (!fromAmount || fromAmount <= 0) return showAddTxMessage("请输入有效划出金额", "error");
  if (!toAmount || toAmount <= 0) return showAddTxMessage("请输入有效划入金额", "error");
  if (!from || !to || from === to) return showAddTxMessage("请选择不同的转出/转入账户", "error");

  const body = {
    date: new Date().toISOString().split("T")[0],
    from_amount: fromAmount,
    from_currency: fromCurrency,
    to_amount: toAmount,
    to_currency: toCurrency,
    from_account_code: from,
    to_account_code: to,
    description: description || null,
    source: "manual",
  };
  try {
    const resp = await fetch("/api/transactions/transfer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
    showAddTxMessage("内部划转已记录", "success");
    document.getElementById("transferFromAmount").value = "";
    document.getElementById("transferToAmount").value = "";
    document.getElementById("transferDescription").value = "";
    resetCaches();
    await loadMonthData();
  } catch (err) {
    showAddTxMessage(`划转失败: ${err.message || err}`, "error");
  }
}

async function main() {
  setActiveNav();
  document.getElementById("currentMonth").textContent = currentMonth;
  await loadAccounts();

  document.getElementById("prevMonth").addEventListener("click", () => changeMonth(-1));
  document.getElementById("nextMonth").addEventListener("click", () => changeMonth(1));
  document.getElementById("tabDaily").addEventListener("click", () => switchView("daily"));
  document.getElementById("tabMonthly").addEventListener("click", () => switchView("monthly"));
  document.getElementById("viewMode").addEventListener("change", () => {
    resetCaches();
    loadMonthData();
  });
  document.getElementById("includeLarge").addEventListener("change", () => {
    resetCaches();
    loadMonthData();
  });
  document.getElementById("largeThreshold").addEventListener("change", () => {
    resetCaches();
    loadMonthData();
  });
  document.getElementById("btnAddTransaction").addEventListener("click", addTransaction);
  document.getElementById("btnAddTransfer").addEventListener("click", addTransfer);

  await loadMonthData();
}

main().catch((err) => showError(`初始化失败: ${String(err)}`));
