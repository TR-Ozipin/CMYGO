import os
import csv
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

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

def extract_favorites_from_page(page):
    """
    从当前页面提取收藏社团信息
    """
    favorites = []
    
    # 等待页面加载完成
    try:
        page.wait_for_selector('.exhibitorList, .circle-list, [class*="circle"]', timeout=10000)
    except PlaywrightTimeout:
        print("[WARN] 页面加载超时，可能没有收藏或页面结构变动")
        return favorites
    
    # 这里的选择器需要根据实际页面结构调整
    # 以下是一个通用的示例，需要根据实际情况修改
    print("[INFO] 正在提取社团信息...")
    
    # 尝试多种可能的选择器（Circle.ms 的页面结构）
    circle_cards = page.query_selector_all('.exhibitorDataRow, .circleData, [class*="exhibitor"]')
    
    if not circle_cards:
        print("[WARN] 未找到社团卡片，可能需要调整选择器")
        # 输出页面 HTML 以便调试
        # print(page.content())
        return favorites
    
    for card in circle_cards:
        try:
            # 这些字段名需要根据实际页面调整
            space = card.query_selector('.space, [class*="space"]')
            circle_name = card.query_selector('.circleName, [class*="circle-name"]')
            author = card.query_selector('.penName, [class*="author"]')
            detail_link = card.query_selector('a[href*="/Circle/"], a[href*="Detail"]')
            
            data = {
                '摊位': space.inner_text().strip() if space else '',
                '社团': circle_name.inner_text().strip() if circle_name else '',
                '作者': author.inner_text().strip() if author else '',
                '备注': '',  # 可以后续填充外部链接
                '合并': '',  # 后续计算
                '社团详情': f"https://webcatalog.circle.ms{detail_link.get_attribute('href')}" if detail_link else '',
                '颜色': ''  # 默认空
            }
            
            # 计算合并字段
            if data['摊位'] and data['社团']:
                data['合并'] = f"{data['摊位']} {data['社团']}"
            
            favorites.append(data)
            
        except Exception as e:
            print(f"[WARN] 提取社团信息失败: {e}")
            continue
    
    print(f"[INFO] 当前页提取到 {len(favorites)} 个社团")
    return favorites

def run_catalog_sync(config):
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
    
    with sync_playwright() as p:
        # 使用持久化上下文，保存登录状态
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_data_dir),
            headless=False,  # 首次运行建议可见模式
            channel="chrome",  # 使用系统 Chrome
            args=[
                '--disable-blink-features=AutomationControlled',  # 反检测
            ]
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # 访问收藏页面
        print("[INFO] 访问 Circle.ms 收藏页面...")
        favorite_url = "https://webcatalog.circle.ms/Favorite/List"
        
        try:
            page.goto(favorite_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"[ERROR] 页面加载失败: {e}")
            context.close()
            return
        
        # 检查是否需要登录
        if "Login" in page.url or "login" in page.url.lower():
            print("[INFO] 检测到需要登录，请在浏览器窗口中手动登录...")
            print("[INFO] 登录完成后，脚本将自动继续...")
            
            # 等待用户登录（监测 URL 变化）
            try:
                page.wait_for_url("**/Favorite/**", timeout=120000)  # 等待最多2分钟
                print("[OK] 登录成功！")
            except PlaywrightTimeout:
                print("[ERROR] 登录超时，脚本退出")
                context.close()
                return
        
        # 收集所有收藏
        all_favorites = []
        page_num = 1
        
        while True:
            print(f"[INFO] 正在处理第 {page_num} 页...")
            
            # 提取当前页数据
            favorites = extract_favorites_from_page(page)
            all_favorites.extend(favorites)
            
            # 检查是否有下一页
            next_button = page.query_selector('.next-page, a[rel="next"], button:has-text("次へ"), button:has-text("下一页")')
            
            if next_button and not next_button.is_disabled():
                print("[INFO] 跳转到下一页...")
                next_button.click()
                time.sleep(2)  # 等待页面加载
                page_num += 1
            else:
                print("[INFO] 已到达最后一页")
                break
        
        print(f"[OK] 共收集到 {len(all_favorites)} 个收藏社团")
        
        # 保存为 CSV
        if all_favorites:
            save_favorites_to_csv(all_favorites, output_dir)
        else:
            print("[WARN] 未提取到任何数据，请检查页面选择器是否正确")
        
        # 关闭浏览器
        print("[INFO] 关闭浏览器...")
        context.close()

def run_catalog_sync_debug(config):
    """
    调试模式：打开收藏页面，并打印页面结构以便分析
    """
    from src.utils import get_path
    
    browser_data_dir = Path.cwd() / "browser_data"
    browser_data_dir.mkdir(exist_ok=True)
    
    print("[DEBUG] 启动调试模式...")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_data_dir),
            headless=False,
            channel="chrome"
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://webcatalog.circle.ms/Favorite/List", wait_until="networkidle")
        
        print("\n[DEBUG] 当前页面 URL:", page.url)
        print("[DEBUG] 页面标题:", page.title())
        print("\n[DEBUG] 请在浏览器中检查页面结构")
        print("[DEBUG] 按 Ctrl+C 退出")
        
        try:
            page.wait_for_timeout(300000)  # 等待 5 分钟
        except KeyboardInterrupt:
            print("\n[DEBUG] 用户中断")
        
        context.close()

