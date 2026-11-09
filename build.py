#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""今日旧闻 — 静态站点构建脚本（零第三方依赖，仅标准库）。

用法:
    python build.py                # 从 data/current.json 构建到 dist/
    python build.py --issue 1926-11-10   # 指定 data/issues/<date>.json 构建

约定:
    data/current.json        当前在生产上的一期（每日任务只替换这个文件）
    data/issues/<日期>.json  按期归档，便于回滚与追溯
    assets/styles.css        页面样式（构建时内联）
    assets/app.js            页面交互（构建时内联）
    templates/page.html      页面骨架（只做占位符替换）

产物:
    dist/index.html          站点首页（自包含，可离线打开）
    dist/robots.txt
    dist/sitemap.xml
    dist/data/current.json   实际发布的数据快照，便于线上核对
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

MAX_FALLBACK = 10

CN_DIGITS = "〇一二三四五六七八九"


def cn_num(value: int) -> str:
    """0–99 的中文数字写法，用于「十七则」「十则」这类版面用语。"""
    if value < 0 or value > 99:
        raise ValueError("cn_num 仅支持 0-99")
    if value < 10:
        return CN_DIGITS[value]
    if value == 10:
        return "十"
    tens, ones = divmod(value, 10)
    head = "十" if tens == 1 else CN_DIGITS[tens] + "十"
    return head if ones == 0 else head + CN_DIGITS[ones]


def iso_to_cn_date(iso_date: str) -> str:
    d = dt.date.fromisoformat(iso_date)
    return f"{d.year} 年 {d.month} 月 {d.day} 日"


WEEKDAYS = "一二三四五六日"


def weekday_cn(iso_date: str) -> str:
    d = dt.date.fromisoformat(iso_date)
    return "星期" + WEEKDAYS[d.weekday()]


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def fail(message: str) -> None:
    print(f"[build] 失败：{message}", file=sys.stderr)
    raise SystemExit(1)


def normalize_issue(issue: dict, config: dict) -> tuple[dict, list[str]]:
    """校验并规范化一期数据；返回 (规范化结果, 警告列表)。"""
    warnings: list[str] = []
    max_items = int(config.get("maxItemsPerSection", MAX_FALLBACK))

    for key in ("issueNo", "targetDate", "sections"):
        if key not in issue:
            fail(f"data 缺少必填字段 {key}")
    if not isinstance(issue["sections"], list) or not issue["sections"]:
        fail("sections 必须是非空数组")

    dt.date.fromisoformat(issue["targetDate"])

    issue.setdefault("todayDate", dt.date.today().isoformat())
    issue.setdefault("targetWeek", weekday_cn(issue["targetDate"]))
    issue.setdefault("todayWeek", weekday_cn(issue["todayDate"]))
    issue.setdefault("eraText", "")
    issue.setdefault("lead", "")
    issue.setdefault("colophon", [])
    issue.setdefault("aside", None)
    issue.setdefault("updatedAt", dt.datetime.now().astimezone().isoformat(timespec="seconds"))

    seen_keys: set[str] = set()
    for section in issue["sections"]:
        for key in ("key", "name", "items"):
            if key not in section:
                fail(f"section 缺少必填字段 {key}")
        if section["key"] in seen_keys:
            fail(f"section key 重复：{section['key']}")
        seen_keys.add(section["key"])

        items = section.get("items") or []
        if not isinstance(items, list):
            fail(f"{section['name']} 的 items 必须是数组")
        if len(items) > max_items:
            warnings.append(
                f"{section['name']} 提交 {len(items)} 条，超出每版上限 {max_items}，已截断"
            )
            items = items[:max_items]
        if len(items) == 0:
            warnings.append(f"{section['name']} 当前没有条目，按实际条数展示（0 条）")

        for index, item in enumerate(items, start=1):
            for key in ("title", "summary", "source", "dateText", "place"):
                if not str(item.get(key, "")).strip():
                    fail(f"{section['name']} 第 {index} 条缺少 {key}")
            item.setdefault("isoDate", issue["targetDate"])
            item.setdefault("rank", index)
            item["rank"] = index
            item.setdefault("lead", index == 1)
            # 汇总字段若被误写成多行，压成单行，避免版面出现空行
            item["title"] = " ".join(item["title"].split())
            item["summary"] = " ".join(item["summary"].split())
            item["source"] = " ".join(item["source"].split())

        section["items"] = items
        section.setdefault("note", None)
        section.setdefault("kicker", "")

    issue["_warnings"] = warnings
    return issue, warnings


def render_items(section: dict) -> str:
    rows = []
    for item in section["items"]:
        lead_cls = " item--lead" if item.get("lead") else ""
        rank_tag = '<span class="tag">头条</span>' if item.get("lead") else ""
        rows.append(
            f"""        <li class="item{lead_cls}">
          <div class="item__no" aria-hidden="true">{item['rank']:02d}</div>
          <div class="item__body">
            <div class="item__top">
              <span class="item__date">{escape(item['dateText'])} · {escape(item['place'])}</span>{rank_tag}
            </div>
            <h3 class="item__title">{escape(item['title'])}</h3>
            <p class="item__sum">{escape(item['summary'])}</p>
            <details class="src">
              <summary>资料来源</summary>
              <p>{escape(item['source'])}</p>
            </details>
          </div>
        </li>"""
        )
    return "\n".join(rows)


def render_sections(issue: dict) -> str:
    blocks = []
    last = len(issue["sections"]) - 1
    for idx, section in enumerate(issue["sections"]):
        count = len(section["items"])
        meta = f"按重要性排序 · {cn_num(count)}则" if count else "暂无条目"
        kicker = (
            f'        <span class="section__kicker" aria-hidden="true">{escape(section["kicker"])}</span>\n'
            if section.get("kicker")
            else ""
        )
        note = (
            f'      <p class="section__note">{escape(section["note"])}</p>\n'
            if section.get("note")
            else ""
        )
        aside = ""
        if idx == last and issue.get("aside"):
            aside = (
                f'\n      <p class="aside"><b>{escape(issue["aside"].get("label", "附 记"))}</b>'
                f'　{escape(issue["aside"].get("text", ""))}</p>'
            )
        items = render_items(section) if count else (
            '        <li class="item"><div class="item__no" aria-hidden="true">—</div>'
            '<div class="item__body"><p class="item__sum">本期本版暂无可核实条目。</p></div></li>'
        )
        blocks.append(
            f"""    <section class="section" id="panel-{section['key']}" role="tabpanel" aria-labelledby="tab-{section['key']}">
      <div class="section__head">
{kicker}        <h2 class="section__title">{escape(section['name'])}</h2>
        <span class="section__meta">{meta}</span>
      </div>
{note}      <ol class="items">
{items}
      </ol>{aside}
    </section>"""
        )
    return "\n\n".join(blocks)


def render_tabs(issue: dict) -> str:
    tabs = []
    for index, section in enumerate(issue["sections"]):
        selected = "true" if index == 0 else "false"
        tabs.append(
            f'      <button class="tab" id="tab-{section["key"]}" role="tab" '
            f'aria-selected="{selected}" aria-controls="panel-{section["key"]}" '
            f'data-view="{section["key"]}">\n'
            f'        {escape(section["name"])} '
            f'<span class="tab__count">{len(section["items"]):02d}</span>\n'
            f'      </button>'
        )
    return "\n".join(tabs)


def favicon_data_uri() -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="6" fill="#efe7d6"/>'
        '<rect x="7" y="9" width="50" height="46" fill="none" stroke="#221d19" stroke-width="3"/>'
        '<path d="M13 19h38M13 27h38M13 36h38M13 45h22" stroke="#9c2b22" stroke-width="3" stroke-linecap="square"/>'
        "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64," + encoded


def main() -> None:
    issue_arg = None
    args = sys.argv[1:]
    if "--issue" in args:
        pos = args.index("--issue")
        if pos + 1 >= len(args):
            fail("--issue 需要日期参数，例如 --issue 1926-11-10")
        issue_arg = args[pos + 1]

    config = read_json(ROOT / "site.config.json")
    data_path = ROOT / "data" / "issues" / f"{issue_arg}.json" if issue_arg else ROOT / "data" / "current.json"
    if not data_path.exists():
        fail(f"找不到数据文件 {data_path}")

    issue, warnings = normalize_issue(read_json(data_path), config)

    sections = issue["sections"]
    total = sum(len(s["items"]) for s in sections)
    issue_no_text = f"{int(issue['issueNo']):03d}"
    site_name = config["siteName"]
    site_url_raw = (config.get("siteUrl") or "").strip()
    placeholder = (
        not site_url_raw
        or "example.com" in site_url_raw
        or "yourdomain" in site_url_raw
        or "localhost" in site_url_raw
        or "127.0.0.1" in site_url_raw
    )
    site_url = "" if placeholder else site_url_raw.rstrip("/")
    canonical = site_url + "/" if site_url else ""
    if placeholder:
        warnings.append(
            "siteUrl 未配置为正式域名，已跳过 canonical / og:url / sitemap.xml；"
            "上线前请在 site.config.json 填入正式域名后重新构建"
        )
    target_iso = issue["targetDate"]
    target_date_text = issue.get("targetDateText") or iso_to_cn_date(target_iso)
    today_date_text = issue.get("todayDateText") or iso_to_cn_date(issue["todayDate"])

    target_day = dt.date.fromisoformat(target_iso)
    title = f"{site_name} · {target_day.year}年{target_day.month}月{target_day.day}日（第 {issue_no_text} 期）"

    section_bits = "、".join(f"{s['name']} {len(s['items'])} 则" for s in sections)
    description = (
        f"{issue.get('description') or config['description']}"
        f"本期为第 {issue_no_text} 期，{section_bits}，共 {total} 则。"
    )

    jsonld = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "description": description,
        "inLanguage": config.get("lang", "zh-CN"),
        "datePublished": issue["todayDate"],
        "dateModified": issue["updatedAt"],
        "isPartOf": {"@type": "WebSite", "name": site_name},
    }
    if canonical:
        jsonld["url"] = canonical
        jsonld["isPartOf"]["url"] = canonical

    styles = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    script = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "page.html").read_text(encoding="utf-8")

    colophon = "\n".join(
        f'      <li>{escape(line)}</li>' for line in issue.get("colophon", [])
    )
    foot_left = f"{site_name} · 第 {issue_no_text} 期"

    replacements = {
        "{{LANG}}": config.get("lang", "zh-CN"),
        "{{THEME_COLOR}}": config.get("themeColor", "#efe7d6"),
        "{{TITLE}}": escape(title),
        "{{DESCRIPTION}}": escape(description),
        "{{SITE_NAME}}": escape(site_name),
        "{{LOCALE}}": config.get("locale", "zh_CN"),
        "{{CANONICAL}}": canonical,
        "{{SEO_CANONICAL}}": (
            f'<link rel="canonical" href="{canonical}">' if canonical else ""
        ),
        "{{SEO_OG_URL}}": (
            f'<meta property="og:url" content="{canonical}">' if canonical else ""
        ),
        "{{FAVICON}}": favicon_data_uri(),
        "{{STYLES}}": styles,
        "{{SCRIPT}}": script,
        "{{JSONLD}}": json.dumps(jsonld, ensure_ascii=False, indent=2),
        "{{ISSUE_NO_TEXT}}": issue_no_text,
        "{{UPDATED_AT}}": escape(issue["updatedAt"]),
        "{{MAX_ITEMS}}": str(int(config.get("maxItemsPerSection", MAX_FALLBACK))),
        "{{ERA_TEXT}}": escape(issue.get("eraText", "")),
        "{{TOTAL_COUNT_TEXT}}": f"{cn_num(total)}则",
        "{{TARGET_DATE_TEXT}}": escape(target_date_text),
        "{{TARGET_WEEK}}": escape(issue["targetWeek"]),
        "{{TODAY_DATE_TEXT}}": escape(today_date_text),
        "{{LEAD_TEXT}}": escape(issue.get("lead", "")),
        "{{TABS}}": render_tabs(issue),
        "{{SECTIONS}}": render_sections(issue),
        "{{COLOPHON}}": colophon,
        "{{FOOT_LEFT}}": escape(foot_left),
        "{{FOOT_RIGHT}}": f"{target_iso.replace('-', '.')} / {issue['todayDate'].replace('-', '.')}",
        "{{OG_IMAGE}}": (canonical + "og-image.png") if canonical else "og-image.png",
    }

    html = template
    for token, value in replacements.items():
        html = html.replace(token, value)

    leftover = [t for t in replacements if t in html]
    if leftover or "{{" in html:
        fail(f"模板仍有未替换占位符：{leftover or '未知占位符'}")

    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "index.html").write_text(html, encoding="utf-8", newline="\n")

    og_src = ROOT / "assets" / "og-image.png"
    if og_src.exists():
        (DIST / "og-image.png").write_bytes(og_src.read_bytes())

    robots_txt = "User-agent: *\nAllow: /\n"
    if canonical:
        robots_txt += "\nSitemap: " + canonical + "sitemap.xml\n"
    (DIST / "robots.txt").write_text(robots_txt, encoding="utf-8", newline="\n")

    sitemap_path = DIST / "sitemap.xml"
    if canonical:
        sitemap_path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{canonical}</loc><lastmod>{issue['todayDate']}</lastmod>"
            "<changefreq>daily</changefreq><priority>1.0</priority></url>\n"
            "</urlset>\n",
            encoding="utf-8",
            newline="\n",
        )
    elif sitemap_path.exists():
        sitemap_path.unlink()

    snapshot_dir = DIST / "data"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {k: v for k, v in issue.items() if not k.startswith("_")}
    (snapshot_dir / "current.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )

    archive_path = ROOT / "data" / "issues" / f"{target_iso}.json"
    if data_path.resolve() != archive_path.resolve() and not archive_path.exists():
        archive_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )

    for warning in warnings:
        print(f"[build] 警告：{warning}")
    for section in sections:
        print(f"[build] {section['name']}: {len(section['items'])} 条")
    print(f"[build] 第 {issue_no_text} 期 · {target_iso} · 共 {total} 则")
    print(f"[build] 输出 {DIST / 'index.html'} ({len(html.encode('utf-8')) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()