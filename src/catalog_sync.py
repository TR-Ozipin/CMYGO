import csv
import json
import logging
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

def save_favorites_to_csv(favorites_data: list[dict], output_dir: Path) -> Path:
    """Save favorites data as Comike_Info CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"Comike_Info_{timestamp}.csv"
    output_path = output_dir / filename

    fieldnames = ["摊位", "社团", "作者", "备注", "合并", "社团详情", "颜色"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(favorites_data)

    logger.info("Exported CSV: %s (%d rows)", output_path, len(favorites_data))
    return output_path


def save_favorites_to_db(
    favorites_data: list[dict], db_path: Path, event_name: str
) -> None:
    """Save favorites data to SQLite database."""
    from src.database import init_db, get_connection

    init_db(db_path)

    with get_connection(db_path) as conn:
        count = 0
        for row in favorites_data:
            booth = (row.get("摊位") or "").strip() or None
            circle_name = (row.get("社团") or "").strip()
            if not circle_name:
                continue

            author = (row.get("作者") or "").strip() or None
            notes = (row.get("备注") or "").strip() or None
            merged = (row.get("合并") or "").strip() or None
            detail_url = (row.get("社团详情") or "").strip() or None
            color = (row.get("颜色") or "").strip() or None

            conn.execute(
                """
                INSERT OR IGNORE INTO comike_info (
                    event_name, booth, circle_name, author, notes,
                    merged, detail_url, color
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_name,
                    booth,
                    circle_name,
                    author,
                    notes,
                    merged,
                    detail_url,
                    color,
                ),
            )
            count += 1

        conn.commit()
        logger.info("Saved %d rows to database: %s", count, db_path.name)

async def extract_favorites_from_page(page):
    """
    从当前页面提取收藏社团信息
    优先从页面中的 JSON 数据提取（更准确），回退到 DOM 解析
    """
    favorites = []
    
    # 等待页面加载完成
    try:
        await page.wait_for_selector('table.md-infotable, #TheModel', timeout=10000)
    except PlaywrightTimeout:
        logger.warning("页面加载超时，可能没有收藏或页面结构变动")
        return favorites
    
    logger.info("正在提取社团信息...")
    
    # 方法1: 尝试提取页面中的 JSON 数据（最稳定）
    try:
        json_element = await page.query_selector('#TheModel')
        if json_element:
            json_text = await json_element.inner_text()
            data = json.loads(json_text)
            circles = data.get('Circles', [])
            
            if circles:
                logger.info("从 JSON 数据中提取到 %d 个社团", len(circles))
                for circle in circles:
                    # 提取推特链接
                    twitter_url = circle.get('TwitterUrl', '')
                    pixiv_url = circle.get('PixivUrl', '')
                    link_list = []
                    if twitter_url:
                        link_list.append(twitter_url)
                    if pixiv_url:
                        link_list.append(pixiv_url)

                    # 构造数据
                    data_row = {
                        '摊位': circle.get('HaichiStr', '').replace('曜日', '').strip(),
                        '社团': circle.get('Name', ''),
                        '作者': circle.get('Author', ''),
                        '备注': ' '.join(link_list),
                        '合并': '',  # 后续计算
                        '社团详情': f"https://webcatalog-free.circle.ms/Circle/{circle.get('Id', '')}" if circle.get('Id') else '',
                        '颜色': f"color-{circle.get('Favorite', {}).get('Color', 0)}" if circle.get('Favorite', {}).get('Color', 0) > 0 else ''
                    }
                    
                    # 计算合并字段
                    if data_row['摊位'] and data_row['社团']:
                        data_row['合并'] = f"{data_row['摊位']} {data_row['社团']}"
                    
                    favorites.append(data_row)
                
                return favorites
    except Exception as e:
        logger.warning("JSON 提取失败: %s，回退到 DOM 解析", e)
    
    # 方法2: DOM 解析（回退方案）
    circle_rows = await page.query_selector_all('tr.webcatalog-circle-list-detail')
    
    if not circle_rows:
        logger.warning("未找到社团行，可能需要调整选择器")
        return favorites
    
    for row in circle_rows:
        try:
            # 摊位信息
            space_elem = await row.query_selector('td.infotable-space span')
            space = await space_elem.inner_text() if space_elem else ''
            space = space.strip()
            
            # 社团名
            circle_name_elem = await row.query_selector('td.infotable-circlename a')
            circle_name = await circle_name_elem.inner_text() if circle_name_elem else ''
            circle_name = circle_name.strip()
            detail_url = await circle_name_elem.get_attribute('href') if circle_name_elem else ''
            
            # 类型
            genre_elem = await row.query_selector('td.infotable-genre')
            genre = await genre_elem.inner_text() if genre_elem else ''
            genre = genre.strip()
            
            # 构造数据
            data = {
                '摊位': space,
                '社团': circle_name,
                '作者': '',  # DOM 中没有直接的作者字段
                '备注': genre,  # 暂用类型作为备注
                '合并': f"{space} {circle_name}" if space and circle_name else '',
                '社团详情': f"https://webcatalog-free.circle.ms{detail_url}" if detail_url else '',
                '颜色': ''
            }
            
            favorites.append(data)
            
        except Exception as e:
            logger.warning("提取社团信息失败: %s", e)
            continue
    
    logger.info("从 DOM 提取到 %d 个社团", len(favorites))
    return favorites

async def run_catalog_sync(config):
    """Run Circle.ms favorites sync."""
    from src.utils import get_path

    output_dir = get_path(config, "paths.comike_info_dir")
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = get_path(config, "paths.database")
    event_name = config.get("event_name", "C107")
    
    # 浏览器数据目录 (存放 Cookie 和登录状态)
    browser_data_dir = Path.cwd() / "browser_data"
    browser_data_dir.mkdir(exist_ok=True)
    
    # Browser configuration
    browser_config = config.get("browser", {})
    headless = browser_config.get("headless", False)
    channel = browser_config.get("channel", "chrome")
    
    logger.info("启动浏览器... (headless=%s, channel=%s)", headless, channel)
    
    async with async_playwright() as p:
        # 使用持久化上下文，保存登录状态
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(browser_data_dir),
            headless=headless,
            channel=channel,
            args=[
                '--disable-blink-features=AutomationControlled',  # 反检测
            ]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # 访问收藏页面
        logger.info("访问 Circle.ms 收藏页面...")
        favorite_url = "https://webcatalog.circle.ms/Favorite/List"
        
        try:
            await page.goto(favorite_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            logger.error("页面加载失败: %s", e)
            await context.close()
            return
        
        # 检查是否需要登录
        if "Login" in page.url or "login" in page.url.lower():
            logger.info("检测到需要登录，请在浏览器窗口中手动登录...")
            logger.info("登录完成后，脚本将自动继续...")
            
            # 等待用户登录（监测 URL 变化）
            try:
                await page.wait_for_url("**/Favorite/**", timeout=120000)  # 等待最多2分钟
                logger.info("登录成功！")
            except PlaywrightTimeout:
                logger.error("登录超时，脚本退出")
                await context.close()
                return
        
        # 收集所有收藏
        all_favorites = []
        page_num = 1
        
        while True:
            logger.info("正在处理第 %d 页...", page_num)
            
            # 提取当前页数据
            favorites = await extract_favorites_from_page(page)
            all_favorites.extend(favorites)
            
            # 检查是否有下一页（根据实际 HTML，分页信息在 m-pagination 中）
            # 从 HTML 看，这个账号只有1个收藏，所以没有下一页按钮
            # 一般情况下，检查分页标签
            pagination = await page.query_selector('.m-pagination-label')
            if pagination:
                pagination_text = await pagination.inner_text()
                logger.debug("分页信息: %s", pagination_text)
                # 解析类似 "1 件中 1 件目 - 1 件目" 的文本
                # 如果当前已是最后一页，则退出
            
            # 尝试查找"下一页"按钮
            # 支持多种语言/符号: 日语"次へ", 英语"Next", 箭头"›"/"»", 常见 CSS class
            next_selectors = [
                'a[href*="page="]:has-text("次へ")',
                'a[href*="page="]:has-text("Next")',
                'a[href*="page="]:has-text("›")',
                'a[href*="page="]:has-text("»")',
                'a.next',
                'a[aria-label="Next"]',
                'button.next',
            ]
            next_link = None
            for selector in next_selectors:
                next_link = await page.query_selector(selector)
                if next_link:
                    break
            
            if next_link and not await next_link.is_disabled():
                logger.info("跳转到下一页...")
                await next_link.click()
                await page.wait_for_timeout(2000)  # 等待页面加载
                page_num += 1
            else:
                logger.info("已到达最后一页")
                break
            
            # 安全机制：最多翻100页（避免死循环）
            if page_num > 100:
                logger.warning("已达到最大页数限制")
                break
        
        logger.info("共收集到 %d 个收藏社团", len(all_favorites))
        
        # Save to CSV and database
        if all_favorites:
            save_favorites_to_csv(all_favorites, output_dir)
            if db_path:
                save_favorites_to_db(all_favorites, db_path, event_name)
        else:
            logger.warning("No data extracted, check page selectors")
        
        # 关闭浏览器
        logger.info("关闭浏览器...")
        await context.close()

async def run_catalog_sync_debug(config):
    """
    调试模式：打开收藏页面，并打印页面结构以便分析
    """
    
    browser_data_dir = Path.cwd() / "browser_data"
    browser_data_dir.mkdir(exist_ok=True)
    
    logger.debug("启动调试模式...")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(browser_data_dir),
            headless=False,
            channel="chrome"
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://webcatalog.circle.ms/Favorite/List", wait_until="networkidle")
        
        logger.debug("当前页面 URL: %s", page.url)
        logger.debug("页面标题: %s", await page.title())
        logger.debug("请在浏览器中检查页面结构")
        logger.debug("按 Ctrl+C 退出")
        
        try:
            await page.wait_for_timeout(300000)  # 等待 5 分钟
        except KeyboardInterrupt:
            logger.debug("用户中断")
        
        await context.close()
