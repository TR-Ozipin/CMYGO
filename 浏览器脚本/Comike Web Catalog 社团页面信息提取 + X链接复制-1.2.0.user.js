// ==UserScript==
// @name         Comike Web Catalog 社团页面信息提取 + X链接复制
// @namespace    http://tampermonkey.net/
// @version      1.2.0
// @description  提取Comike Web Catalog社团页面的日期、摊位、社团、作者信息，并实现单击复制功能，增加X(Twitter)链接复制按钮（仅匹配带Twitter图标的链接，并添加作者名，空值用全角问号）
// @author       Saline
// @match        https://webcatalog.circle.ms/Circle/*
// @match        https://webcatalog-free.circle.ms/Circle/*
// @exclude      https://webcatalog.circle.ms/Circle/List*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // 提取title中的'サークル名'
    let metaTag = document.querySelector('meta[property="og:title"]');
    let circleName = metaTag ? metaTag.getAttribute('content').split(' | ')[0] : '';

    // 获取所有的th元素
    let thElements = document.querySelectorAll('th');
    let spaceName = '';
    let authorName = '';
    for (let th of thElements) {
        if (th.textContent.includes('配置スペース')) {
            let spaceTd = th.nextElementSibling;
            if (spaceTd) {
                spaceName = spaceTd.textContent.trim();
            }
        }
        if (th.textContent.includes('執筆者名')) {
            let authorTd = th.nextElementSibling;
            if (authorTd) {
                authorName = authorTd.textContent.trim();
            }
        }
        if (spaceName && authorName) {
            break;
        }
    }

    // 创建显示摊位信息的div
    let displayDiv = document.createElement('div');
    displayDiv.style.backgroundColor = 'white';
    displayDiv.style.padding = '10px';
    displayDiv.style.border = '1px solid black';
    displayDiv.style.margin = '10px 0';
    displayDiv.style.cursor = 'pointer';

    let day = spaceName.split('曜日 ')[0];
    let space = spaceName.split('曜日 ')[1];
    let circle_author = `[${circleName} (${authorName || 'NoName'})]` // 空值用“NoName”代替
    let spaceInfo = `${day}${space} ${circle_author}`;
    //let spaceInfo = `${day}${space} [${circleName || '？'} (${authorName || '？'})]`;
    displayDiv.textContent = spaceInfo;

    // 插入摊位信息按钮
    let targetElements = document.querySelectorAll('div.item');
    if (targetElements.length > 0) {
        targetElements.forEach(function(targetElement) {
            targetElement.appendChild(displayDiv);
        });
    }

    // 点击复制摊位信息
    displayDiv.addEventListener('click', function() {
        navigator.clipboard.writeText(spaceInfo).then(function() {
            displayDiv.textContent = `${spaceInfo} 已复制`;
        }).catch(function(err) {
            console.error('无法复制内容: ', err);
        });
    });

    // ===== 新增部分：提取并复制X(Twitter)链接（限定图标+作者名+空值问号） =====
    let twitterLink = '';
    let twitterIconImg = document.querySelector('img[src*="img_icon_twitter_on.png"]');
    if (twitterIconImg) {
        let twitterAnchor = twitterIconImg.closest('a');
        if (twitterAnchor && twitterAnchor.href.startsWith('https://twitter.com/')) {
            // 替换成 x.com
            twitterLink = twitterAnchor.href.replace('https://twitter.com/', 'https://x.com/').trim();
        }
    }

    // 空值用“NoLink”代替
    //let safeAuthorName = authorName || '？';
    let safeTwitterLink = twitterLink || 'NoLink';
    //let twitterInfo = `${safeAuthorName} ${safeTwitterLink}`;
    let twitterInfo = `${safeTwitterLink} ${circle_author}`;

    let twitterDiv = document.createElement('div');
    twitterDiv.style.backgroundColor = 'white';
    twitterDiv.style.padding = '10px';
    twitterDiv.style.border = '1px solid black';
    twitterDiv.style.margin = '10px 0';
    twitterDiv.style.cursor = 'pointer';
    twitterDiv.textContent = twitterInfo;

    if (targetElements.length > 0) {
        targetElements.forEach(function(targetElement) {
            targetElement.appendChild(twitterDiv);
        });
    }

    // 点击复制
    twitterDiv.addEventListener('click', function() {
        navigator.clipboard.writeText(twitterInfo).then(function() {
            twitterDiv.textContent = `${twitterInfo} 已复制`;
        }).catch(function(err) {
            console.error('无法复制内容: ', err);
        });
    });
})();
