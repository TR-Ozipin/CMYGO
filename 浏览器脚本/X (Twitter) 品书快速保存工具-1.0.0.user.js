// ==UserScript==
// @name         X (Twitter) 品书快速保存工具
// @namespace    https://github.com/cmygo
// @version      1.0.0
// @description  在 X (Twitter) 页面上快速识别并下载品书图片，自动命名以便后续处理
// @author       CMYGO Community
// @match        https://twitter.com/*
// @match        https://x.com/*
// @grant        GM_download
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_addStyle
// @require      https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js
// @license      MIT
// ==/UserScript==

(function() {
    'use strict';

    // ========== 配置区域 ==========
    const CONFIG = {
        // 品书关键词（检测推文内容）
        keywords: ['お品書き', '品書き', '品書', 'menu', 'おしながき', 'Menu', 'INFO', 'Info'],
        
        // 按钮样式
        buttonColor: '#1d9bf0',
        buttonHoverColor: '#1a8cd8',
        
        // 是否自动高亮包含关键词的推文
        autoHighlight: true,
        
        // 下载延迟（避免触发限流，单位：毫秒）
        downloadDelay: 500
    };

    // ========== 样式注入 ==========
    GM_addStyle(`
        /* 保存品书按钮 */
        .cmygo-save-btn {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 6px 12px;
            margin: 8px 0;
            background-color: ${CONFIG.buttonColor};
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .cmygo-save-btn:hover {
            background-color: ${CONFIG.buttonHoverColor};
            transform: scale(1.05);
        }
        
        .cmygo-save-btn:active {
            transform: scale(0.95);
        }
        
        .cmygo-save-btn.downloading {
            background-color: #10a37f;
            cursor: wait;
        }
        
        .cmygo-save-btn.completed {
            background-color: #059669;
        }
        
        /* 高亮品书推文 */
        .cmygo-shinagaki-tweet {
            border-left: 3px solid #1d9bf0 !important;
            background-color: rgba(29, 155, 240, 0.05) !important;
        }
        
        /* 批量下载面板 */
        .cmygo-batch-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: white;
            border: 2px solid ${CONFIG.buttonColor};
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            min-width: 200px;
        }
        
        .cmygo-batch-panel h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #333;
        }
        
        .cmygo-batch-panel button {
            width: 100%;
            padding: 8px;
            margin: 5px 0;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .cmygo-info-badge {
            display: inline-block;
            padding: 2px 8px;
            background-color: #fef3c7;
            color: #92400e;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }
    `);

    // ========== 工具函数 ==========
    
    /**
     * 检测推文是否包含品书关键词
     */
    function containsShinagakiKeyword(text) {
        if (!text) return false;
        const lowerText = text.toLowerCase();
        return CONFIG.keywords.some(keyword => 
            lowerText.includes(keyword.toLowerCase())
        );
    }
    
    /**
     * 从推文元素中提取用户名
     */
    function extractUsername(tweetElement) {
        // X 的 DOM 结构：a[href^="/"][href*="/status/"] 的父级链接包含用户名
        const userLinks = tweetElement.querySelectorAll('a[href^="/"][role="link"]');
        for (const link of userLinks) {
            const href = link.getAttribute('href');
            // 匹配 /@username 或 /username 格式
            const match = href.match(/^\/([^\/]+)$/);
            if (match && !href.includes('/status/')) {
                return match[1].replace('@', '');
            }
        }
        return 'unknown';
    }
    
    /**
     * 从推文 URL 中提取推文 ID
     */
    function extractTweetId(tweetElement) {
        const timeElement = tweetElement.querySelector('time');
        if (!timeElement) return Date.now().toString();
        
        const link = timeElement.closest('a');
        if (!link) return Date.now().toString();
        
        const href = link.getAttribute('href');
        const match = href.match(/\/status\/(\d+)/);
        return match ? match[1] : Date.now().toString();
    }
    
    /**
     * 获取推文中的所有图片 URL（原图）
     */
    function extractImageUrls(tweetElement) {
        const images = [];
        const imgElements = tweetElement.querySelectorAll('img[src*="pbs.twimg.com/media"]');
        
        imgElements.forEach(img => {
            let url = img.src;
            // 转换为原图 URL：移除尺寸参数，添加 ?format=jpg&name=orig
            url = url.split('?')[0];
            // 提取格式
            const format = url.match(/\.(jpg|png|webp)$/)?.[1] || 'jpg';
            url = `${url}?format=${format}&name=orig`;
            images.push(url);
        });
        
        return images;
    }
    
    /**
     * 下载图片（使用 GM_download 或回退到 a 标签）
     */
    async function downloadImage(url, filename) {
        if (typeof GM_download !== 'undefined') {
            // 使用 GM_download（推荐）
            return new Promise((resolve, reject) => {
                GM_download({
                    url: url,
                    name: filename,
                    onload: () => resolve(),
                    onerror: (err) => reject(err)
                });
            });
        } else {
            // 回退方案：创建隐藏的 a 标签
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            return Promise.resolve();
        }
    }
    
    /**
     * 批量下载推文图片
     */
    async function downloadTweetImages(tweetElement, button) {
        const username = extractUsername(tweetElement);
        const tweetId = extractTweetId(tweetElement);
        const imageUrls = extractImageUrls(tweetElement);
        
        if (imageUrls.length === 0) {
            alert('未找到图片！');
            return;
        }
        
        // 更新按钮状态
        button.classList.add('downloading');
        button.textContent = `⏳ 下载中 (0/${imageUrls.length})`;
        button.disabled = true;
        
        const today = new Date().toISOString().split('T')[0].replace(/-/g, '.');
        
        for (let i = 0; i < imageUrls.length; i++) {
            const url = imageUrls[i];
            const ext = url.match(/format=(\w+)/)?.[1] || 'jpg';
            // 文件名格式：twitter-{username}-{tweetId}-{index}-{date}.{ext}
            const filename = `twitter-${username}-${tweetId}-${i + 1}-${today}.${ext}`;
            
            try {
                await downloadImage(url, filename);
                button.textContent = `⏳ 下载中 (${i + 1}/${imageUrls.length})`;
                
                // 延迟，避免触发限流
                if (i < imageUrls.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, CONFIG.downloadDelay));
                }
            } catch (err) {
                console.error(`下载失败: ${filename}`, err);
                alert(`下载失败: ${filename}\n${err.message}`);
                button.classList.remove('downloading');
                button.textContent = '💾 保存品书';
                button.disabled = false;
                return;
            }
        }
        
        // 完成
        button.classList.remove('downloading');
        button.classList.add('completed');
        button.textContent = `✅ 已保存 ${imageUrls.length} 张`;
        
        setTimeout(() => {
            button.classList.remove('completed');
            button.textContent = '💾 保存品书';
            button.disabled = false;
        }, 3000);
    }
    
    /**
     * 为推文添加保存按钮
     */
    function addSaveButton(tweetElement) {
        // 避免重复添加
        if (tweetElement.querySelector('.cmygo-save-btn')) return;
        
        // 查找推文的交互区域（通常在底部）
        const actionBar = tweetElement.querySelector('[role="group"]');
        if (!actionBar) return;
        
        // 创建按钮
        const button = document.createElement('button');
        button.className = 'cmygo-save-btn';
        button.textContent = '💾 保存品书';
        
        // 添加图片数量提示
        const imageCount = extractImageUrls(tweetElement).length;
        if (imageCount > 0) {
            const badge = document.createElement('span');
            badge.className = 'cmygo-info-badge';
            badge.textContent = `${imageCount} 张`;
            button.appendChild(badge);
        }
        
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            await downloadTweetImages(tweetElement, button);
        });
        
        // 插入按钮（在交互栏之后）
        actionBar.parentElement.insertBefore(button, actionBar.nextSibling);
    }
    
    /**
     * 扫描页面中的推文
     */
    function scanTweets() {
        // X 的推文容器：article[data-testid="tweet"]
        const tweets = document.querySelectorAll('article[data-testid="tweet"]');
        
        tweets.forEach(tweet => {
            // 提取推文文本
            const textElement = tweet.querySelector('[data-testid="tweetText"]');
            const text = textElement ? textElement.textContent : '';
            
            // 检查是否包含品书关键词
            if (containsShinagakiKeyword(text)) {
                // 高亮推文
                if (CONFIG.autoHighlight) {
                    tweet.classList.add('cmygo-shinagaki-tweet');
                }
                
                // 添加保存按钮
                addSaveButton(tweet);
            }
        });
    }
    
    // ========== 主逻辑 ==========
    
    // 页面加载后首次扫描
    setTimeout(scanTweets, 2000);
    
    // 监听页面变化（X 是单页应用，需要持续监听）
    const observer = new MutationObserver(() => {
        scanTweets();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // 添加全局提示
    console.log('[CMYGO] 品书保存工具已启动！遇到包含品书关键词的推文将自动添加下载按钮。');
    
})();

