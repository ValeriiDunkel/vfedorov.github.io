# scrape.py
"""
Скрапер постов из публичной страницы Telegram-канала.
Загружает ВСЕ посты, сохраняет в posts.json.
Запускается через GitHub Actions (без прокси, серверный запрос).
"""

import json
import time
import re
import requests
from bs4 import BeautifulSoup

CHANNEL = "adv_vfedorov"
BASE_URL = f"https://t.me/s/{CHANNEL}"
OUTPUT = "posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def fetch_page(before=None):
    """Загрузить одну страницу постов."""
    url = BASE_URL
    if before:
        url += f"?before={before}"

    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_page(html):
    """Распарсить HTML-страницу t.me/s/ и вернуть список постов."""
    soup = BeautifulSoup(html, "lxml")
    wraps = soup.select(".tgme_widget_message_wrap")
    posts = []

    for wrap in wraps:
        bubble = wrap.select_one(".tgme_widget_message_bubble")
        if not bubble:
            continue

        msg_el = wrap.select_one(".tgme_widget_message")
        data_post = msg_el.get("data-post", "") if msg_el else ""
        post_id_str = data_post.split("/")[-1] if "/" in data_post else ""

        try:
            post_id = int(post_id_str)
        except (ValueError, TypeError):
            continue

        # Текст
        text_el = bubble.select_one(".tgme_widget_message_text")
        text = str(text_el) if text_el else ""
        # Убираем внешний тег div
        if text_el:
            text = text_el.decode_contents()

        # Дата
        time_el = bubble.select_one("time[datetime]")
        date = time_el["datetime"] if time_el else ""

        # Просмотры
        views_el = bubble.select_one(".tgme_widget_message_views")
        views = views_el.get_text(strip=True) if views_el else ""

        # Фото
        photo = ""
        photo_wrap = bubble.select_one(".tgme_widget_message_photo_wrap")
        if photo_wrap:
            style = photo_wrap.get("style", "")
            m = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
            if m:
                photo = m.group(1)

        # Видео
        video = ""
        video_el = bubble.select_one("video")
        if video_el:
            video = video_el.get("src", "")

        # Пропускаем пустые
        if not text and not photo and not video:
            continue

        posts.append({
            "id": post_id,
            "text": text.strip(),
            "date": date,
            "views": views,
            "photo": photo,
            "video": video,
        })

    return posts


def scrape_all():
    """Загрузить все посты канала, листая назад."""
    all_posts = []
    seen_ids = set()
    before = None

    print(f"Scraping @{CHANNEL}...")

    for attempt in range(500):  # safety limit
        print(f"  Page {attempt + 1}, before={before}, total={len(all_posts)}")

        try:
            html = fetch_page(before)
        except Exception as e:
            print(f"  Fetch error: {e}")
            break

        page_posts = parse_page(html)

        if not page_posts:
            print("  No posts found, stopping.")
            break

        added = 0
        for p in page_posts:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                all_posts.append(p)
                added += 1

        if added == 0:
            print("  No new posts, stopping.")
            break

        # Найти минимальный ID для следующей страницы
        min_id = min(p["id"] for p in page_posts)
        if min_id <= 1:
            print("  Reached beginning.")
            break

        before = min_id
        time.sleep(0.5)  # вежливая задержка

    # Сортировка: новые сверху
    all_posts.sort(key=lambda p: p["id"], reverse=True)
    return all_posts


def main():
    posts = scrape_all()
    print(f"\nTotal posts scraped: {len(posts)}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=None)

    print(f"Saved to {OUTPUT} ({len(posts)} posts)")


if __name__ == "__main__":
    main()