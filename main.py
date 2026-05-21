import asyncio
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import hashlib
from dotenv import load_dotenv
import os
from pathlib import Path
import uvicorn

base_path = Path(__file__).resolve().parent
env_path = base_path / '.env'
app = FastAPI()

# Cấu hình CORS để Frontend ở domain/port khác có thể gọi được
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv(dotenv_path = env_path)
TARGET_URL = os.getenv("TARGET_URL")
# Thời gian chờ giữa mỗi lần F5 (giây). 
# Cẩn thận không để quá nhỏ tránh làm sập server cũ.
RELOAD_INTERVAL = float(os.getenv("RELOAD_INTERVAL"))

@app.websocket("/ws/stream")
async def stream_ui(websocket: WebSocket):
    """
    Endpoint WebSocket này sẽ liên tục F5 trang web cũ, 
    chụp ảnh màn hình và gửi về cho Frontend.
    """
    await websocket.accept()
    last_image_hash = None
    async with async_playwright() as p:
        # Khởi chạy trình duyệt ẩn
        # browser = await p.chromium.launch(headless=True)
        browser = await p.chromium.launch(headless=True, channel="chrome")
        # Set kích thước viewport theo độ phân giải muốn hiển thị trên fe
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        try:
            # Truy cập lần đầu
            await page.goto(TARGET_URL, wait_until="domcontentloaded")
            
            while True:
                # F5 trang web
                await page.reload(wait_until="domcontentloaded") 
                
                # Chụp ảnh (Dùng định dạng JPEG để giảm dung lượng truyền tải qua mạng)
                screenshot = await page.screenshot(type="jpeg", quality=70)
                # Tính mã băm của ảnh vừa chụp
                current_image_hash = hashlib.md5(screenshot).hexdigest()
                if current_image_hash != last_image_hash:
                    # Nếu ảnh khác nhau, mới tiến hành gửi
                    base64_image = base64.b64encode(screenshot).decode('utf-8')
                    await websocket.send_text(f"data:image/jpeg;base64,{base64_image}")
                    
                    # Cập nhật lại hash của ảnh mới nhất
                    last_image_hash = current_image_hash

                # chờ 1s để F5 lần tiếp theo
                await asyncio.sleep(RELOAD_INTERVAL) 

        except WebSocketDisconnect:
            print("Frontend đã ngắt kết nối WebSocket (Người dùng tắt Tự động cập nhật).")
        except Exception as e:
            print(f"Có lỗi xảy ra: {e}")
        finally:
            # Đóng trình duyệt để giải phóng RAM khi ngắt kết nối
            await browser.close()

if __name__ == "__main__":
    # "main:app" nghĩa là tìm đối tượng 'app' trong file 'main.py'
    # Bạn có thể thay đổi port hoặc host tại đây
    uvicorn.run(app, host="0.0.0.0", port=8000)