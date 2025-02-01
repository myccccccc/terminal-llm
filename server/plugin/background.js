const DEBUG = true; // 设为false关闭调试输出

let ws = null;
let currentTabId = null;
let requestId = null;

async function connectWebSocket() {
  if (DEBUG) console.debug('🔄 正在连接WS服务器...');
  ws = new WebSocket('ws://localhost:8000/ws');

  ws.onopen = () => {
    if (DEBUG) console.debug('✅ 成功连接WS服务器');
  };

  ws.onmessage = async (event) => {
    if (DEBUG) console.debug('📨 收到服务器消息:', event.data);
    const data = JSON.parse(event.data);
    if (data.type === 'extract') {
      currentTabId = await createTab(data.url);
      requestId = data.requestId;
    }
  };

  ws.onclose = () => {
    if (DEBUG) console.debug('❌ 连接断开，1秒后重连...');
    setTimeout(connectWebSocket, 1000);
  };
}

async function createTab(url) {
  if (DEBUG) console.debug(`🆕 正在创建标签页: ${url}`);
  const tab = await chrome.tabs.create({ url, active: false });
  if (DEBUG) console.debug(`✅ 标签页创建成功，ID: ${tab.id}`);
  // 添加标签页加载监听器                                                     
  chrome.tabs.onUpdated.addListener(async function listener(tabId, changeInfo) {
    if (tabId === tab.id && changeInfo.status === 'complete') {
      if (DEBUG) console.debug(`✅ 标签页加载完成，注入提取脚本`);

      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['extract.js']
        });
      } catch (error) {
        console.error('脚本注入失败:', error);
      }

      chrome.tabs.onUpdated.removeListener(listener);
    }
  });
  return tab.id;
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.action === 'htmlContent' && sender.tab.id === currentTabId) {
    if (DEBUG) console.debug(`📤 发送HTML内容，长度: ${message.content.length} 字符`);
    ws.send(JSON.stringify({
      type: 'htmlResponse',
      content: message.content,
      requestId: requestId,
    }));
    requestId = null;
    chrome.tabs.remove(sender.tab.id);
    currentTabId = null;
  }
});

// 初始化连接
connectWebSocket();
