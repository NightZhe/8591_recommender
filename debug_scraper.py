import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="zh-TW",
        )
        page = await ctx.new_page()
        url = "https://rent.591.com.tw/list?kind=1&region=1&page=1"
        print(f"[debug] opening {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        html = await page.content()

        # 存下來分析
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[debug] HTML saved ({len(html)} chars)")

        # 試各種 selector
        selectors = [
            ".item-info-wrap",
            ".list-item",
            "article.item",
            ".house-list-item",
            "[class*='list'] [class*='item']",
            ".rent-list-item",
            "li.clearfix",
            ".vue-recycle-scroller__item-view",
            "[class*='house']",
        ]
        for sel in selectors:
            count = await page.locator(sel).count()
            if count > 0:
                print(f"[debug] FOUND selector='{sel}' count={count}")

        # 印出 body 前 3000 字看結構
        body_text = await page.locator("body").inner_html()
        print("\n[debug] body HTML snippet:")
        print(body_text[:3000])

        await browser.close()

asyncio.run(main())
