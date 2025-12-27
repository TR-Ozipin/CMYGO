// ==UserScript==
// @name         Comike Web Catalog 印刷页面信息重组 + CSV导出功能
// @namespace    http://tampermonkey.net/
// @version      1.4
// @description  重组Comike Web Catalog印刷页面信息，添加点击复制与CSV导出按钮（含摊位、社团、作者、备注信息、颜色、社团详情链接）
// @author       Saline
// @match        https://webcatalog.circle.ms/Print
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    window.onload = function () {
        const targetElements = document.querySelectorAll('td');
        const collectedRows = [];

        targetElements.forEach(function (td) {
            const span = td.querySelector('span.h-text--bold.h-text--center');
            if (span) {
                const parentTr = td.closest('tr'); // 找到当前td所在的<tr>
                const memoTd = parentTr ? parentTr.querySelector('td.table-column-memo') : null;
                const memo = memoTd ? memoTd.innerText.trim() : ''; // 第5列内容：备注

                // 找到颜色信息
                const colorTd = parentTr ? parentTr.querySelector('td.c-block--large') : null;
                let colorClass = '';
                if (colorTd) {
                    const match = colorTd.className.match(/favorite-(color-\d+)/);
                    if (match) {
                        colorClass = match[1]; // 提取 color-1 这种形式
                    }
                }

                // 找到社团详情链接
                const circleLinkElement = parentTr ? parentTr.querySelector('a[href^="/Circle/"]') : null;
                let circleLink = '';
                if (circleLinkElement) {
                    const href = circleLinkElement.getAttribute('href'); // 例：/Circle/21007649
                    if (href) {
                        circleLink = `https://webcatalog.circle.ms${href}`;
                    }
                }

                const dayLocation = span.innerText.trim(); // 例：日曜日 西あ12a
                const lines = td.innerHTML.split('<br>');
                if (lines.length < 4) return;

                const name = lines[1].trim();      // 社团名
                const nameAlt = lines[2].trim();   // 社团别名（未使用）
                let author = lines[3].trim();      // 作者名
                if (!author) author = '？';

                const dateSpace = `${dayLocation.split('曜日 ')[0]}${dayLocation.split('曜日 ')[1]}`;
                const textLine = `${dateSpace} [${name} (${author})]`;

                // 收集为一行数据（新增颜色列和社团详情列）
                collectedRows.push([textLine, dateSpace, name, author, memo, colorClass, circleLink]);

                // 替换显示内容
                td.innerHTML = `<div>
                                    <p><strong>${textLine}</strong></p>
                                </div>`;

                td.style.cursor = 'pointer';
                td.title = '点击复制';
                td.addEventListener('click', function () {
                    copyToClipboard(textLine);
                    td.innerHTML = `<div><p>${textLine}</p></div>`;
                });
            }
        });

        // 添加导出CSV按钮
        const exportButton = document.createElement('button');
        exportButton.innerText = '导出CSV';
        exportButton.style.position = 'fixed';
        exportButton.style.top = '10px';
        exportButton.style.right = '10px';
        exportButton.style.zIndex = '9999';
        exportButton.style.padding = '10px';
        exportButton.style.backgroundColor = '#2196F3';
        exportButton.style.color = 'white';
        exportButton.style.border = 'none';
        exportButton.style.borderRadius = '5px';
        exportButton.style.cursor = 'pointer';

        exportButton.addEventListener('click', function () {
            const csvLines = [
                ['合并', '摊位', '社团', '作者', '备注', '颜色', '社团详情'].join(',')
            ];

            collectedRows.forEach(row => {
                const line = row.map(col => `"${col.replace(/"/g, '""')}"`).join(',');
                csvLines.push(line);
            });

            const csvContent = csvLines.join('\n');
            const blob = new Blob([csvContent], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // 添加时间戳
            const now = new Date();
            const timestamp = now.getFullYear() + '-' +
                  String(now.getMonth() + 1).padStart(2, '0') + '-' +
                  String(now.getDate()).padStart(2, '0') + '_' +
                  String(now.getHours()).padStart(2, '0') + '-' +
                  String(now.getMinutes()).padStart(2, '0') + '-' +
                  String(now.getSeconds()).padStart(2, '0');

            a.download = `Comike_Info_${timestamp}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        });

        document.body.appendChild(exportButton);

        function copyToClipboard(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
        }
    };
})();
