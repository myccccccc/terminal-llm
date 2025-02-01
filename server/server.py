
import json
import uuid
import tempfile
import os
import logging
from tornado import web, websocket, ioloop, gen
import pdb
from markitdown import MarkItDown

# 调试模式配置
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
DEBUG='true'

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

connected_clients = {}
pending_requests = {}

class BrowserWebSocketHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        """仅允许本地连接"""
        return origin.startswith("chrome-extension://") or origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:")

    def open(self):
        self.client_id = str(uuid.uuid4())
        connected_clients[self.client_id] = self
        logger.debug(f"🎮 浏览器客户端连接成功，ID: {self.client_id}")

    async def on_message(self, message):
        logger.debug(f"📨 收到浏览器消息: {message[:200]}...")
        try:
            data = json.loads(message)
            if data.get('type') == 'htmlResponse':
                request_id = data.get('requestId')
                if request_id in pending_requests:
                    pending_requests[request_id].set_result(data['content'])
                    logger.debug(f"✅ 请求 {request_id} 已设置结果")
        except Exception as e:
            logger.error(f"处理消息出错: {str(e)}")

    def on_close(self):
        del connected_clients[self.client_id]
        logger.debug(f"❌ 浏览器客户端断开，ID: {self.client_id}")

class ConvertHandler(web.RequestHandler):
    async def get(self):
        try:
            url = self.get_query_argument('url')
            logger.debug(f"🌐 收到转换请求，URL: {url}")

            if not connected_clients:
                self.set_status(503)
                return self.write({"error": "No browser connected"})

            client = next(iter(connected_clients.values()))
            request_id = str(uuid.uuid4())
            fut = gen.Future()
            pending_requests[request_id] = fut

            try:
                logger.debug(f"📤 发送提取请求到浏览器，请求ID: {request_id}")
                await client.write_message(json.dumps({
                    "type": "extract",
                    "url": url,
                    "requestId": request_id
                }))

                html = await gen.with_timeout(
                    ioloop.IOLoop.current().time() + 30,
                    fut
                )
                logger.debug(f"📥 收到HTML响应，长度: {len(html)} 字符")
                # 转换HTML为Markdown
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html',
delete=True) as f:
                    f.write(html)
                    f.flush()
                    logger.debug(f"🔄 开始转换，临时文件: {f.name}")
                    md = MarkItDown()
                    result = md.convert(f.name)
                    logger.debug(f"✅ 转换完成，Markdown长度: {len(result.text_content)} 字符")

                self.write(result.text_content)
            except gen.TimeoutError:
                logger.error(f"⏰ 请求超时，请求ID: {request_id}")
                self.set_status(504)
                self.write({"error": "Request timeout"})
            finally:
                pending_requests.pop(request_id, None)

        except web.MissingArgumentError:
            self.set_status(400)
            self.write({"error": "Missing url parameter"})
        except Exception as e:
            logger.error(f"处理请求出错: {str(e)}")
            self.set_status(500)
            self.write({"error": "Internal server error"})

def make_app():
    return web.Application([
        (r"/convert", ConvertHandler),
        (r"/ws", BrowserWebSocketHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(8000, address='127.0.0.1')  # 仅监听本地连接
    logger.info("🚀 服务器已启动，监听 127.0.0.1:8000")
    ioloop.IOLoop.current().start()
