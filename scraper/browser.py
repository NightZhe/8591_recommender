from playwright.async_api import async_playwright, Browser, BrowserContext
import asyncio
import os


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser: Browser = None

    async def start(self):
        self._playwright = await async_playwright().start()
        launch_kwargs = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage", "--ignore-certificate-errors"],
        }
        # Allow overriding the chromium executable (e.g. when browser build version
        # doesn't match the pip package, set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH).
        exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if exe:
            launch_kwargs["executable_path"] = exe
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_context(self) -> BrowserContext:
        return await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-TW",
            viewport={"width": 1280, "height": 800},
        )

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
