import csv
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

def save_favorites_to_csv(favorites_data, output_dir):
    """
    将收藏数据保存为 Comike_Info CSV 格式
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"Comike_Info_{timestamp}.csv"
    output_path = output_dir / filename
    
    # CSV 列名，与现有格式保持一致
    fieldnames = ['摊位', '社团', '作者', '备注', '合并', '社团详情', '颜色']
    
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(favorites_data)
    
    print(f"[OK] 导出 CSV: {output_path} (共 {len(favorites_data)} 条)")
    return output_path

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
        print("[WARN] 页面加载超时，可能没有收藏或页面结构变动")
        return favorites
    
    print("[INFO] 正在提取社团信息...")
    
    # 方法1: 尝试提取页面中的 JSON 数据（最稳定）
    try:
        import json
        json_element = await page.query_selector('#TheModel')
        if json_element:
            json_text = await json_element.inner_text()
            data = json.loads(json_text)
            circles = data.get('Circles', [])
            
            if circles:
                print(f"[OK] 从 JSON 数据中提取到 {len(circles)} 个社团")
                for circle in circles:
                    # 提取推特链接
                    twitter_url = circle.get('TwitterUrl', '')
                    pixiv_url = circle.get('PixivUrl', '')
                    備注_links = []
                    if twitter_url:
                        備注_links.append(twitter_url)
                    if pixiv_url:
                        備注_links.append(pixiv_url)
                    
                    # 构造数据
                    data_row = {
                        '摊位': circle.get('HaichiStr', '').replace('曜日', '').strip(),  # 去掉"曜日"
                        '社团': circle.get('Name', ''),
                        '作者': circle.get('Author', ''),
                        '备注': ' '.join(備注_links),  # 外部链接
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
        print(f"[WARN] JSON 提取失败: {e}，回退到 DOM 解析")
    
    # 方法2: DOM 解析（回退方案）
    circle_rows = await page.query_selector_all('tr.webcatalog-circle-list-detail')
    
    if not circle_rows:
        print("[WARN] 未找到社团行，可能需要调整选择器")
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
            print(f"[WARN] 提取社团信息失败: {e}")
            continue
    
    print(f"[INFO] 从 DOM 提取到 {len(favorites)} 个社团")
    return favorites

async def run_catalog_sync(config):
    """
    运行 Circle.ms 收藏同步
    """
    from src.utils import get_path
    
    output_dir = get_path(config, 'paths.comike_info_dir')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 浏览器数据目录 (存放 Cookie 和登录状态)
    browser_data_dir = Path.cwd() / "browser_data"
    browser_data_dir.mkdir(exist_ok=True)
    
    print("[INFO] 启动浏览器...")
    print("[INFO] 使用本地 Chrome (如果首次运行，您可能需要手动登录)")
    
    async with async_playwright() as p:
        # 使用持久化上下文，保存登录状态
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(browser_data_dir),
            headless=False,  # 首次运行建议可见模式
            channel="chrome",  # 使用系统 Chrome
            args=[
                '--disable-blink-features=AutomationControlled',  # 反检测
            ]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # 访问收藏页面
        print("[INFO] 访问 Circle.ms 收藏页面...")
        favorite_url = "https://webcatalog.circle.ms/Favorite/List"
        
        try:
            await page.goto(favorite_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"[ERROR] 页面加载失败: {e}")
            await context.close()
            return
        
        # 检查是否需要登录
        if "Login" in page.url or "login" in page.url.lower():
            print("[INFO] 检测到需要登录，请在浏览器窗口中手动登录...")
            print("[INFO] 登录完成后，脚本将自动继续...")
            
            # 等待用户登录（监测 URL 变化）
            try:
                await page.wait_for_url("**/Favorite/**", timeout=120000)  # 等待最多2分钟
                print("[OK] 登录成功！")
            except PlaywrightTimeout:
                print("[ERROR] 登录超时，脚本退出")
                await context.close()
                return
        
        # 收集所有收藏
        all_favorites = []
        page_num = 1
        
        while True:
            print(f"[INFO] 正在处理第 {page_num} 页...")
            
            # 提取当前页数据
            favorites = await extract_favorites_from_page(page)
            all_favorites.extend(favorites)
            
            # 检查是否有下一页（根据实际 HTML，分页信息在 m-pagination 中）
            # 从 HTML 看，这个账号只有1个收藏，所以没有下一页按钮
            # 一般情况下，检查分页标签
            pagination = await page.query_selector('.m-pagination-label')
            if pagination:
                pagination_text = await pagination.inner_text()
                print(f"[INFO] 分页信息: {pagination_text}")
                # 解析类似 "1 件中 1 件目 - 1 件目" 的文本
                # 如果当前已是最后一页，则退出
            
            # 尝试查找"下一页"按钮
            # 在实际页面中，如果有多页，会有类似的结构
            next_link = await page.query_selector('a[href*="page="]:has-text("次へ"), a[href*="page="]:has-text("›"), a.next')
            
            if next_link and not await next_link.is_disabled():
                print("[INFO] 跳转到下一页...")
                await next_link.click()
                await page.wait_for_timeout(2000)  # 等待页面加载
                page_num += 1
            else:
                print("[INFO] 已到达最后一页")
                break
            
            # 安全机制：最多翻100页（避免死循环）
            if page_num > 100:
                print("[WARN] 已达到最大页数限制")
                break
        
        print(f"[OK] 共收集到 {len(all_favorites)} 个收藏社团")
        
        # 保存为 CSV
        if all_favorites:
            save_favorites_to_csv(all_favorites, output_dir)
        else:
            print("[WARN] 未提取到任何数据，请检查页面选择器是否正确")
        
        # 关闭浏览器
        print("[INFO] 关闭浏览器...")
        await context.close()

async def run_catalog_sync_debug(config):
    """
    调试模式：打开收藏页面，并打印页面结构以便分析
    """
    
    browser_data_dir = Path.cwd() / "browser_data"
    browser_data_dir.mkdir(exist_ok=True)
    
    print("[DEBUG] 启动调试模式...")
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(browser_data_dir),
            headless=False,
            channel="chrome"
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://webcatalog.circle.ms/Favorite/List", wait_until="networkidle")
        
        print("\n[DEBUG] 当前页面 URL:", page.url)
        print("[DEBUG] 页面标题:", await page.title())
        print("\n[DEBUG] 请在浏览器中检查页面结构")
        print("[DEBUG] 按 Ctrl+C 退出")
        
        try:
            await page.wait_for_timeout(300000)  # 等待 5 分钟
        except KeyboardInterrupt:
            print("\n[DEBUG] 用户中断")
        
        await context.close()
