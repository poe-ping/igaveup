import csv
import sqlite3
import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TARGET = 3000
MAX_PAGES = 2000
BASE_URL = "https://github.com/orgs/google/repositories?page={}"

KNOWN_LANGS = {
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go", "Rust",
    "Kotlin", "Swift", "Dart", "Ruby", "PHP", "Shell", "HTML", "CSS", "Jupyter Notebook",
    "Objective-C", "Starlark", "Scala", "Lua", "Haskell", "Nix", "Vue", "SCSS",
    "Dockerfile", "TeX", "Makefile", "Perl", "R", "Julia", "Elixir", "OCaml",
    "Closure Templates", "Smarty", "Svelte", "CMake", "Assembly", "Zig", "MLIR",
}
STAR_RE = re.compile(r"^\d[\d,\.]*[kKmM]?$")
SKIP_WORDS = {"Public", "Private", "Archived", "Fork", "Forked", "Star", "Starred"}

debug_saved = False


def save_debug(item):
    """Save one repo block so selectors can be checked by hand."""
    global debug_saved
    if not debug_saved:
        with open("debug_block.html", "w", encoding="utf-8") as f:
            f.write(item.prettify())
        debug_saved = True
        print("  -> debug_block.html を保存した (言語が取れなかったブロック)")


def extract_language_stars(item):
    language, stars = "N/A", "0"

    lang_tag = item.find(attrs={"itemprop": "programmingLanguage"})
    if lang_tag and lang_tag.text.strip():
        language = lang_tag.text.strip()

    star_tag = item.find("a", href=lambda h: h and "stargazers" in h)
    if star_tag and star_tag.text.strip():
        stars = star_tag.text.strip()

    if language == "N/A" or stars == "0":
        lines = [t for t in item.get_text("\n", strip=True).split("\n") if t]

        star_idx = None
        for i, t in enumerate(lines):
            if STAR_RE.match(t):
                star_idx = i
                break

        if stars == "0" and star_idx is not None:
            stars = lines[star_idx]

        if language == "N/A":
            for t in lines:
                if t in KNOWN_LANGS:
                    language = t
                    break
            if language == "N/A" and star_idx:
                prev = lines[star_idx - 1]
                if (
                    not STAR_RE.match(prev)
                    and prev not in SKIP_WORDS
                    and len(prev) <= 25
                ):
                    language = prev

    return language, stars


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    results, seen = [], set()

    for a in soup.select("a[href^='/google/']"):
        parts = a.get("href", "").strip("/").split("/")
        if len(parts) != 2:          
            continue
        name = a.text.strip()
        if not name or name in seen:
            continue
        seen.add(name)

        item = a.find_parent("li") or a.find_parent("article")
        if item is None:
            node = a
            for _ in range(8):
                node = node.parent
                if node is None:
                    break
                if node.name == "div" and re.search(r"\bUpdated\b|\bstar", node.get_text(), re.I):
                    item = node
                    break

        language, stars = "N/A", "0"
        if item is not None:
            language, stars = extract_language_stars(item)
            if language == "N/A":
                save_debug(item)
        results.append((name, language, stars))

    return results


def main():
    con = sqlite3.connect("github_google.db")
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            language TEXT,
            stars TEXT
        )
        """
    )
    con.commit()

    cur.execute("SELECT COUNT(*) FROM repositories")
    total = cur.fetchone()[0]
    print(f"DBにすでに {total} 件ある")

    page_no = 1
    empty_streak = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pw_page = browser.new_page()

        try:
            while total < TARGET and page_no <= MAX_PAGES:
                print(f"page {page_no} をgetしている")
                pw_page.goto(BASE_URL.format(page_no))
                try:
                    pw_page.wait_for_selector("a[href^='/google/']", timeout=15000)
                except Exception:
                    print("リポジトリが見つからない。終了")
                    break
                pw_page.wait_for_timeout(2000)   # 言語・スターの描画待ち

                items = parse(pw_page.content())
                new_count = 0
                for name, language, stars in items:
                    if total >= TARGET:
                        break
                    cur.execute(
                        "INSERT OR IGNORE INTO repositories (name, language, stars) "
                        "VALUES (?, ?, ?)",
                        (name, language, stars),
                    )
                    new_count += cur.rowcount
                    total += cur.rowcount
                con.commit()
                print(f"page {page_no}: 取得 {len(items)} 件 / 新規 {new_count} 件 / 累計 {total} 件")

                if new_count == 0:
                    empty_streak += 1
                    if empty_streak >= 3:
                        print("新しいデータが3ページ続けて無いので終了")
                        break
                else:
                    empty_streak = 0

                page_no += 1
                time.sleep(1)  

        except KeyboardInterrupt:
            print("Ctrl+C で停止")

        finally:
            browser.close()
            print("Data is saved")

            cur.execute("SELECT id, name, language, stars FROM repositories")
            rows = cur.fetchall()

            with open("google_repos.csv", "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "name", "language", "stars"])
                writer.writerows(rows)
            print(f"google_repos.csv に {len(rows)} 件保存した")

            print(f"データベースの内容 ({len(rows)} 件)")
            print(f"{'ID':<5} | {'リポジトリ名':<35} | {'言語':<18} | {'スター数':<8}")
            print("-" * 76)
            for row in rows:
                print(f"{row[0]:<5} | {row[1]:<35} | {row[2]:<18} | {row[3]:<8}")

            con.close()


if __name__ == "__main__":
    main()