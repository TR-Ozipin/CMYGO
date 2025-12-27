// ==UserScript==
// @name         Comike Web Catalog 收藏页面添加X链接按钮
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  在收藏页面メモ編集按钮右边添加访问X链接的按钮
// @author       Saline
// @match        https://webcatalog.circle.ms/User/Favorites*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    function addLinkButtons() {
        document.querySelectorAll('td.infotable-left[colspan="3"]').forEach(td => {
            const memoEditBtn = td.querySelector('a.c-btn.c-btn--blue');
            const spanMemo = td.querySelector('span[data-bind*="favMemo"]');
            if (!memoEditBtn || !spanMemo) return;

            const memoText = spanMemo.textContent.trim();
            const match = memoText.match(/https:\/\/x\.com\/\S+/);
            if (!match) return;

            const url = match[0];
            if (td.querySelector('.js-open-x-link')) return;

            const linkBtn = document.createElement('a');
            linkBtn.textContent = 'X链接';
            linkBtn.href = url;
            linkBtn.target = '_blank';
            linkBtn.className = 'c-btn c-btn--green js-open-x-link';
            linkBtn.style.marginLeft = '8px';

            memoEditBtn.insertAdjacentElement('afterend', linkBtn);
        });
    }

    // 初次运行
    addLinkButtons();

    // 监控DOM变化（包括属性变化）
    const observer = new MutationObserver(() => {
        addLinkButtons();
    });
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true
    });

    // 兜底轮询，每 1 秒检查一次
    setInterval(addLinkButtons, 1000);
})();
