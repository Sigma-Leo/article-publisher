const API = "https://article-publisher-02n9.onrender.com";
const state = { articles: [], selected: new Set(), current: -1, media: [], cookieMode: "add", paused: false };
const $ = id => document.getElementById(id);
const log = value => { $("log").textContent += `${new Date().toLocaleTimeString()} ${value}\n`; $("log").scrollTop = $("log").scrollHeight; };
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
async function api(path, options = {}) { const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options }); if (!response.ok) throw new Error(await response.text()); return response.json(); }

async function refresh() {
  state.articles = await api("/api/articles"); state.selected.clear(); state.current = state.articles.length ? 0 : -1; renderArticles(); if (state.current >= 0) selectArticle(state.current);
  const cookies = await api("/api/cookies"); $("cookie").innerHTML = cookies.map(item => `<option>${escapeHtml(item.name)}</option>`).join("");
  $("health").textContent = "已连接";
}
function renderArticles() { $("articles").innerHTML = state.articles.map((article, index) => `<div class="article ${index === state.current ? "active" : ""}" data-index="${index}"><input type="checkbox" ${state.selected.has(index) ? "checked" : ""}><span class="article-title">${escapeHtml(article.title || "无标题")}</span><span class="status">${escapeHtml(article._status || "待发布")}</span></div>`).join(""); }
function selectArticle(index) { state.current = index; const article = state.articles[index]; $("title").value = article.title || ""; $("content").value = article.content || ""; $("covers").value = JSON.stringify(article.extra?.pgcFeedCovers || [], null, 2); renderArticles(); }
async function saveCurrent() { if (state.current < 0) return true; const article = state.articles[state.current]; article.title = $("title").value; article.content = $("content").value; try { article.extra = article.extra || {}; article.extra.pgcFeedCovers = JSON.parse($("covers").value || "[]"); } catch (error) { log(`保存失败：封面 JSON 格式错误：${error.message}`); return false; } await api("/api/articles", { method: "PUT", body: JSON.stringify(state.articles) }); log("当前稿件已保存"); return true; }
function selectedIndexes() { return [...state.selected].sort((a, b) => a - b); }
function failureReason(result) { const body = result.response || {}; return body.prompts || body.message || body.msg || result.error || `HTTP ${result.status_code || "未知"}，业务状态 ${result.business_status ?? "未知"}`; }

function newArticle() { state.articles.push({ title: "新建稿件", content: "", extra: { pgcFeedCovers: [] }, aid: 0 }); state.current = state.articles.length - 1; renderArticles(); selectArticle(state.current); saveCurrent().catch(error => log(`保存失败：${error.message}`)); }
async function copyArticle() { if (state.current < 0) return; await saveCurrent(); const duplicate = structuredClone(state.articles[state.current]); duplicate.title = `${duplicate.title}【副本】`; state.articles.push(duplicate); state.current = state.articles.length - 1; renderArticles(); selectArticle(state.current); await api("/api/articles", { method: "PUT", body: JSON.stringify(state.articles) }); log("已复制当前稿件"); }
async function deleteArticle() { if (state.current < 0) return; const title = state.articles[state.current].title; if (!confirm(`确定删除稿件“${title}”？`)) return; state.articles.splice(state.current, 1); state.current = Math.min(state.current, state.articles.length - 1); await api("/api/articles", { method: "PUT", body: JSON.stringify(state.articles) }); renderArticles(); if (state.current >= 0) selectArticle(state.current); log("稿件已删除"); }
async function moveArticle(delta) { if (state.current < 0) return; const target = state.current + delta; if (target < 0 || target >= state.articles.length) return; [state.articles[state.current], state.articles[target]] = [state.articles[target], state.articles[state.current]]; state.current = target; await api("/api/articles", { method: "PUT", body: JSON.stringify(state.articles) }); renderArticles(); selectArticle(state.current); log("稿件顺序已更新"); }

function openCookieDialog(mode) { state.cookieMode = mode; const selected = $("cookie").value; $("cookieDialogTitle").textContent = mode === "edit" ? "编辑 Cookie 账号" : "新增 Cookie 账号"; $("cookieName").value = mode === "edit" ? selected : ""; $("cookieValue").value = ""; $("cookieValue").placeholder = mode === "edit" ? "请输入新的 Cookie 字符串（不会回显旧值）" : "粘贴浏览器中的 Cookie"; $("cookieDialog").showModal(); $("cookieName").focus(); }
async function saveCookie() { const name = $("cookieName").value.trim(); const cookie = $("cookieValue").value.trim(); if (!name || !cookie) return alert("账号名称和 Cookie 不能为空"); const oldName = state.cookieMode === "edit" ? $("cookie").value : null; const button = $("saveCookie"); button.disabled = true; try { await api(state.cookieMode === "edit" ? `/api/cookies/${encodeURIComponent(oldName)}` : "/api/cookies", { method: state.cookieMode === "edit" ? "PUT" : "POST", body: JSON.stringify({ name, cookie }) }); $("cookieDialog").close(); await refresh(); $("cookie").value = name; log(`${state.cookieMode === "edit" ? "已更新" : "已新增"} Cookie 账号：${name}`); } catch (error) { alert(`保存 Cookie 失败：${error.message}`); } finally { button.disabled = false; } }
async function deleteCookie() { const name = $("cookie").value; if (!name || !confirm(`确定删除 Cookie 账号“${name}”？`)) return; try { await api(`/api/cookies/${encodeURIComponent(name)}`, { method: "DELETE" }); await refresh(); log(`已删除 Cookie 账号：${name}`); } catch (error) { alert(`删除 Cookie 失败：${error.message}`); } }

function renderMedia() { $("mediaGrid").innerHTML = state.media.map((image, index) => `<div class="media-card" data-media="${index}"><img src="${escapeHtml(image.preview_url || image.url)}" loading="lazy"><label><input type="checkbox">选择图片</label><small>${image.width || "?"} × ${image.height || "?"}</small></div>`).join(""); }
async function loadMedia() { const name = $("cookie").value; if (!name) return alert("请先选择 Cookie"); const data = await api(`/api/media?cookie_name=${encodeURIComponent(name)}&page=1&page_size=100`); state.media = data.images; renderMedia(); log(`已加载 ${state.media.length} 张图片`); }
function useMedia() { const selected = [...document.querySelectorAll(".media-card input:checked")].map(input => state.media[Number(input.closest(".media-card").dataset.media)]); if (!selected.length) return alert("请选择图片"); $("covers").value = JSON.stringify(selected, null, 2); $("mediaDialog").close(); }
function previewCovers() { try { const items = JSON.parse($("covers").value || "[]"); const win = window.open("", "_blank"); win.document.write(`<title>配图预览</title><style>body{font-family:sans-serif;background:#edf4fb;display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:20px}img{width:100%;background:white;aspect-ratio:4/3;object-fit:contain}</style>${items.map(item => `<img src="${escapeHtml(item.preview_url || item.url)}">`).join("")}`); } catch (error) { log(`预览失败：封面 JSON 格式错误：${error.message}`); } }
function showCoverHoverPreview() {
  const panel = $("coverHoverPreview");
  try {
    const items = JSON.parse($("covers").value || "[]").filter(item => item && item.url);
    panel.innerHTML = items.length ? items.map(item => `<img src="${escapeHtml(item.preview_url || item.url)}" alt="配图预览">`).join("") : `<span class="preview-empty">当前没有可预览的配图</span>`;
  } catch (error) {
    panel.innerHTML = `<span class="preview-empty">封面 JSON 格式错误</span>`;
  }
  panel.classList.add("visible");
}
function hideCoverHoverPreview() { $("coverHoverPreview").classList.remove("visible"); }

const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
async function publish() {
  const indexes = selectedIndexes();
  if (!indexes.length) return alert("请先选择稿件");
  if (!$("cookie").value) return alert("请先选择 Cookie");
  const minInterval = Number($("minInterval").value);
  const maxInterval = Number($("maxInterval").value);
  if (!Number.isFinite(minInterval) || !Number.isFinite(maxInterval) || minInterval < 0 || minInterval > maxInterval) return alert("请确认发布间隔有效，且最小值不大于最大值");
  const button = $("publish");
  button.disabled = true;
  $("pause").disabled = false;
  button.textContent = "发布中...";
  state.paused = false;
  log(`开始发布 ${indexes.length} 篇稿件`);
  try {
    if (!await saveCurrent()) return;
    for (let position = 0; position < indexes.length; position += 1) {
      if (state.paused) { log("已暂停，后续稿件未发送"); break; }
      const index = indexes[position];
      const article = state.articles[index];
      article._status = "发布中";
      renderArticles();
      log(`【${position + 1}/${indexes.length}】${article.title || index}：正在发布`);
      try {
        const data = await api("/api/publish", { method: "POST", body: JSON.stringify({ indexes: [index], cookie_name: $("cookie").value, min_interval: 0, max_interval: 0 }) });
        const result = data.results[0] || { success: false, error: "接口未返回结果" };
        article._status = result.success ? "发布成功" : "发布失败";
        log(result.success ? `${article.title || index}：发布成功` : `${article.title || index}：发布失败，原因：${failureReason(result)}`);
      } catch (error) {
        article._status = "发布失败";
        log(`${article.title || index}：发布请求失败，原因：${error.message}`);
      }
      renderArticles();
      if (position < indexes.length - 1 && !state.paused) {
        const interval = (minInterval + Math.random() * (maxInterval - minInterval)) * 1000;
        log(`下一篇文章将在 ${(interval / 1000).toFixed(1)} 秒后发布`);
        await wait(interval);
      }
    }
  } finally {
    button.disabled = false;
    $("pause").disabled = true;
    button.textContent = "发布选中";
    log("发布任务结束");
  }
}
function pausePublish() { state.paused = true; $("pause").disabled = true; log("已发送暂停请求；当前接口请求完成后停止后续发布"); }

$("articles").addEventListener("click", event => { const row = event.target.closest(".article"); if (!row) return; const index = Number(row.dataset.index); if (event.target.type === "checkbox") { event.target.checked ? state.selected.add(index) : state.selected.delete(index); } else selectArticle(index); });
$("selectAll").onclick = () => { const select = state.selected.size !== state.articles.length; state.articles.forEach((_, index) => select ? state.selected.add(index) : state.selected.delete(index)); renderArticles(); };
$("refresh").onclick = () => refresh().catch(error => log(`刷新失败：${error.message}`)); $("save").onclick = () => saveCurrent().catch(error => log(`保存失败：${error.message}`)); $("publish").onclick = publish; $("pause").onclick = pausePublish;
$("newArticle").onclick = newArticle; $("copyArticle").onclick = () => copyArticle().catch(error => log(`复制失败：${error.message}`)); $("deleteArticle").onclick = () => deleteArticle().catch(error => log(`删除失败：${error.message}`)); $("moveUp").onclick = () => moveArticle(-1).catch(error => log(`排序失败：${error.message}`)); $("moveDown").onclick = () => moveArticle(1).catch(error => log(`排序失败：${error.message}`));
$("addCookie").onclick = () => openCookieDialog("add"); $("editCookie").onclick = () => openCookieDialog("edit"); $("deleteCookie").onclick = deleteCookie; $("saveCookie").onclick = saveCookie;
$("media").onclick = () => { $("mediaDialog").showModal(); loadMedia().catch(error => log(`图库加载失败：${error.message}`)); }; $("loadMedia").onclick = () => loadMedia().catch(error => log(`图库加载失败：${error.message}`)); $("useMedia").onclick = useMedia; $("preview").onclick = previewCovers;
$("preview").addEventListener("mouseenter", showCoverHoverPreview); $("preview").addEventListener("mouseleave", () => setTimeout(() => { if (!$('coverHoverPreview').matches(':hover')) hideCoverHoverPreview(); }, 120)); $("coverHoverPreview").addEventListener("mouseleave", hideCoverHoverPreview);
$("content").addEventListener("paste", event => { event.preventDefault(); const text = (event.clipboardData || window.clipboardData).getData("text"); const value = text.includes("<br/>") ? text : text.replace(/\r\n|\r|\n/g, "<br/>\n"); document.execCommand("insertText", false, value); });
document.querySelectorAll("[data-close]").forEach(element => element.onclick = () => $("mediaDialog").close()); document.querySelectorAll("[data-cookie-close]").forEach(element => element.onclick = () => $("cookieDialog").close());
window.addEventListener("keydown", event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); saveCurrent().catch(error => log(`保存失败：${error.message}`)); } if (event.key === "F5") { event.preventDefault(); refresh().catch(error => log(`刷新失败：${error.message}`)); } });
refresh().catch(error => { $("health").textContent = "连接失败"; log(error.message); });
