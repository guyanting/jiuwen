(function () {
  "use strict";

  var docEl = document.documentElement;
  docEl.classList.add("js");

  var body = document.body;
  var CN_DIGITS = "〇一二三四五六七八九";
  var WEEKDAYS = "一二三四五六日";
  var MAX_ITEMS = parseInt(body.getAttribute("data-max-items"), 10) || 10;

  /* ---------- 小工具 ---------- */

  function cnNum(value) {
    if (value < 0 || value > 99) return String(value);
    if (value < 10) return CN_DIGITS.charAt(value);
    if (value === 10) return "十";
    var tens = Math.floor(value / 10);
    var ones = value % 10;
    var head = tens === 1 ? "十" : CN_DIGITS.charAt(tens) + "十";
    return ones === 0 ? head : head + CN_DIGITS.charAt(ones);
  }

  function pad3(value) {
    var n = parseInt(value, 10);
    if (isNaN(n)) return "000";
    return ("00" + n).slice(-3);
  }

  function cnDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    if (!m) return "";
    return parseInt(m[1], 10) + " 年 " + parseInt(m[2], 10) + " 月 " + parseInt(m[3], 10) + " 日";
  }

  function weekCn(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    if (!m) return "";
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    var idx = (d.getUTCDay() + 6) % 7; /* 周一 = 0 */
    return "星期" + WEEKDAYS.charAt(idx);
  }

  function dots(iso) {
    return String(iso || "").replace(/-/g, ".");
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = String(text);
    return node;
  }

  /* ---------- 渲染：条目 / 版块 / 页签 ---------- */

  function renderItem(item, index) {
    var isLead = typeof item.lead === "boolean" ? item.lead : index === 0;
    var li = el("li", isLead ? "item item--lead" : "item");

    var no = el("div", "item__no", ("0" + (index + 1)).slice(-2));
    no.setAttribute("aria-hidden", "true");

    var wrap = el("div", "item__body");
    var top = el("div", "item__top");
    var dateBits = [];
    if (item.dateText) dateBits.push(item.dateText);
    if (item.place) dateBits.push(item.place);
    top.appendChild(el("span", "item__date", dateBits.join(" · ")));
    if (isLead) top.appendChild(el("span", "tag", "头条"));

    wrap.appendChild(top);
    wrap.appendChild(el("h3", "item__title", item.title || ""));
    wrap.appendChild(el("p", "item__sum", item.summary || ""));

    var details = el("details", "src");
    details.appendChild(el("summary", null, "资料来源"));
    details.appendChild(el("p", null, item.source || ""));
    wrap.appendChild(details);

    li.appendChild(no);
    li.appendChild(wrap);
    return li;
  }

  function renderSection(section, items) {
    var node = el("section", "section");
    node.id = "panel-" + section.key;
    node.setAttribute("role", "tabpanel");
    node.setAttribute("aria-labelledby", "tab-" + section.key);

    var head = el("div", "section__head");
    if (section.kicker) {
      var kicker = el("span", "section__kicker", section.kicker);
      kicker.setAttribute("aria-hidden", "true");
      head.appendChild(kicker);
    }
    head.appendChild(el("h2", "section__title", section.name));
    head.appendChild(
      el("span", "section__meta", items.length ? "按重要性排序 · " + cnNum(items.length) + "则" : "暂无条目")
    );
    node.appendChild(head);

    if (section.note) node.appendChild(el("p", "section__note", section.note));

    var list = el("ol", "items");
    if (items.length) {
      items.forEach(function (item, index) {
        list.appendChild(renderItem(item, index));
      });
    } else {
      var empty = el("li", "item");
      var dash = el("div", "item__no", "—");
      dash.setAttribute("aria-hidden", "true");
      var emptyBody = el("div", "item__body");
      emptyBody.appendChild(el("p", "item__sum", "本期本版暂无可核实条目。"));
      empty.appendChild(dash);
      empty.appendChild(emptyBody);
      list.appendChild(empty);
    }
    node.appendChild(list);
    return node;
  }

  function renderTab(section, selected) {
    var tab = el("button", "tab");
    tab.type = "button";
    tab.id = "tab-" + section.key;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", selected ? "true" : "false");
    tab.setAttribute("aria-controls", "panel-" + section.key);
    tab.setAttribute("data-view", section.key);
    tab.setAttribute("tabindex", selected ? "0" : "-1");
    tab.appendChild(document.createTextNode(section.name + " "));
    tab.appendChild(el("span", "tab__count", ("0" + section.items.length).slice(-2)));
    return tab;
  }

  /* ---------- 页签交互 ---------- */

  var tabList = document.getElementById("tabs");
  var content = document.getElementById("content");
  var currentView = null;

  function tabs() {
    return tabList ? Array.prototype.slice.call(tabList.querySelectorAll(".tab")) : [];
  }

  function select(view) {
    var list = tabs();
    currentView = view;
    list.forEach(function (tab) {
      var on = tab.getAttribute("data-view") === view;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.setAttribute("tabindex", on ? "0" : "-1");
      var panel = document.getElementById(tab.getAttribute("aria-controls"));
      if (!panel) return;
      if (on) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
    });
  }

  if (tabList) {
    tabList.addEventListener("click", function (event) {
      var tab = event.target.closest ? event.target.closest(".tab") : null;
      if (!tab || !tabList.contains(tab)) return;
      if (tab.getAttribute("aria-selected") === "true") return;
      select(tab.getAttribute("data-view"));
    });

    tabList.addEventListener("keydown", function (event) {
      var key = event.key;
      if (key !== "ArrowRight" && key !== "ArrowLeft" && key !== "Home" && key !== "End") return;
      var list = tabs();
      if (!list.length) return;
      var index = list.indexOf(document.activeElement);
      if (index < 0) index = 0;
      event.preventDefault();
      var next = index;
      if (key === "ArrowRight") next = (index + 1) % list.length;
      if (key === "ArrowLeft") next = (index - 1 + list.length) % list.length;
      if (key === "Home") next = 0;
      if (key === "End") next = list.length - 1;
      list[next].focus();
      select(list[next].getAttribute("data-view"));
    });
  }

  /* ---------- 阅读进度与回到顶部 ---------- */

  var progress = document.getElementById("progress");
  var toTop = document.getElementById("toTop");
  var ticking = false;

  function onScroll() {
    var max = docEl.scrollHeight - window.innerHeight;
    var ratio = max > 0 ? Math.min(1, Math.max(0, window.pageYOffset / max)) : 0;
    if (progress) progress.style.width = (ratio * 100).toFixed(2) + "%";
    if (toTop) {
      if (window.pageYOffset > 420) toTop.classList.add("is-on");
      else toTop.classList.remove("is-on");
    }
    ticking = false;
  }

  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(onScroll);
  }, { passive: true });

  window.addEventListener("resize", onScroll, { passive: true });

  if (toTop) {
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ---------- 运行期刷新：新一期已发布则就地替换 ---------- */

  var interacted = false;

  function markInteracted() {
    interacted = true;
  }

  ["click", "touchstart", "wheel", "keydown"].forEach(function (type) {
    window.addEventListener(type, markInteracted, { passive: true, once: true });
  });

  function normalize(data) {
    if (!data || !Array.isArray(data.sections) || !data.sections.length) return null;
    var sections = [];
    for (var i = 0; i < data.sections.length; i += 1) {
      var raw = data.sections[i];
      if (!raw || !raw.key || !raw.name || !Array.isArray(raw.items)) return null;
      var items = raw.items.slice(0, MAX_ITEMS).filter(function (item) {
        return item && String(item.title || "").trim() && String(item.summary || "").trim();
      });
      sections.push({
        key: String(raw.key),
        name: String(raw.name),
        kicker: raw.kicker ? String(raw.kicker) : "",
        note: raw.note ? String(raw.note) : "",
        items: items
      });
    }
    return { issueNo: data.issueNo, targetDate: data.targetDate, sections: sections };
  }

  function apply(data) {
    var issueText = pad3(data.issueNo);
    var total = data.sections.reduce(function (sum, section) {
      return sum + section.items.length;
    }, 0);

    var metaIssue = document.getElementById("metaIssue");
    var metaEra = document.getElementById("metaEra");
    var metaTotal = document.getElementById("metaTotal");
    var dateText = document.getElementById("dateText");
    var dateWeek = document.getElementById("dateWeek");
    var todayText = document.getElementById("todayText");
    var leadText = document.getElementById("leadText");
    var colophon = document.getElementById("colophon");
    var footLeft = document.getElementById("footLeft");
    var footRight = document.getElementById("footRight");

    if (metaIssue) metaIssue.textContent = "第 " + issueText + " 期";
    if (metaEra) metaEra.textContent = data.eraText || "";
    if (metaTotal) metaTotal.textContent = "全页" + cnNum(total) + "则";
    if (dateText) dateText.textContent = data.targetDateText || cnDate(data.targetDate);
    if (dateWeek) dateWeek.textContent = data.targetWeek || weekCn(data.targetDate);
    if (todayText) todayText.textContent = data.todayDateText || cnDate(data.todayDate);
    if (leadText) leadText.textContent = data.lead || "";

    if (tabList) {
      while (tabList.firstChild) tabList.removeChild(tabList.firstChild);
      data.sections.forEach(function (section, index) {
        tabList.appendChild(renderTab(section, index === 0));
      });
    }

    if (content) {
      while (content.firstChild) content.removeChild(content.firstChild);
      data.sections.forEach(function (section) {
        content.appendChild(renderSection(section, section.items));
      });
    }

    if (colophon) {
      while (colophon.firstChild) colophon.removeChild(colophon.firstChild);
      (data.colophon || []).forEach(function (line) {
        colophon.appendChild(el("li", null, line));
      });
    }

    if (footLeft) footLeft.textContent = (body.getAttribute("data-site-name") || "") + " · 第 " + issueText + " 期";
    if (footRight) footRight.textContent = dots(data.targetDate) + " / " + dots(data.todayDate);

    var titleParts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(data.targetDate || ""));
    if (titleParts) {
      document.title =
        (body.getAttribute("data-site-name") || "") + " · " + parseInt(titleParts[1], 10) + "年" +
        parseInt(titleParts[2], 10) + "月" + parseInt(titleParts[3], 10) + "日（第 " + issueText + " 期）";
    }

    body.setAttribute("data-issue-no", issueText);
    body.setAttribute("data-updated-at", data.updatedAt || "");
  }

  function refreshFromJson() {
    if (!window.fetch) return;
    var stamp = Date.now();
    fetch("data/current.json?ts=" + stamp, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (payload) {
        var data = normalize(payload);
        if (!data) return;
        var sameIssue = pad3(data.issueNo) === body.getAttribute("data-issue-no");
        var sameStamp = String(payload.updatedAt || "") === String(body.getAttribute("data-updated-at") || "");
        if (sameIssue && sameStamp) return;
        /* 用户已开始阅读时不做整体替换，避免内容在其眼皮下改写；下次访问即取最新 */
        if (interacted) return;
        apply(data);
        select(currentView);
        onScroll();
      })
      .catch(function () {
        /* 取不到 JSON 时保留构建期内嵌内容，页面照常可读 */
      });
  }

  /* ---------- 启动 ---------- */

  onScroll();

  var list = tabs();
  var active = list.filter(function (tab) {
    return tab.getAttribute("aria-selected") === "true";
  })[0] || list[0];
  if (active) select(active.getAttribute("data-view"));

  refreshFromJson();
})();