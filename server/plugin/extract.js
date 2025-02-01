// 在文件开头添加调试开关
const DEBUG = true; // 设为false关闭调试输出

(async function () {
    if (DEBUG) console.debug('🔍 开始提取页面内容...');

    // 克隆整个文档结构
    const clone = document.documentElement.cloneNode(true);
    if (DEBUG) console.debug('✅ 克隆文档完成');

    // 移除所有多媒体元素
    const mediaSelectors = [
        'img', 'video', 'audio', 'source', 'track',
        'object', 'embed', 'iframe', 'canvas', 'svg'
    ];
    const mediaElements = clone.querySelectorAll(mediaSelectors.join(','));
    mediaElements.forEach(el => el.remove());
    if (DEBUG) console.debug(`🗑️ 移除 ${mediaElements.length} 个媒体元素`);

    // 替换CSS链接为内联样式
    const links = clone.querySelectorAll('link[rel="stylesheet"]');
    if (DEBUG) console.debug(`🎨 内联 ${links.length} 个CSS文件`);
    for (const link of links) {
        try {
            const response = await fetch(link.href);
            const css = await response.text();
            const style = document.createElement('style');
            style.textContent = css;
            link.replaceWith(style);
        } catch (error) {
            link.remove();
        }
    }

    // 构建最终HTML
    const html = `<!DOCTYPE html>
<html>
<head>
    <meta charset="${document.characterSet}">
    <title>${document.title}</title>
    ${Array.from(clone.querySelectorAll('style')).map(s => s.outerHTML).join('\n')}
</head>
<body>
    ${clone.querySelector('body').innerHTML}
</body>
</html>`;

    if (DEBUG) {
        console.debug('📄 生成最终HTML:');
        console.debug(html.substring(0, 200) + '...');
    }

    chrome.runtime.sendMessage({
        action: "htmlContent",
        content: html
    });
    if (DEBUG) console.debug('📨 已发送HTML内容到后台脚本');
})();
