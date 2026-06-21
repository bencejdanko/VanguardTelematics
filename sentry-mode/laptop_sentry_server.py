import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Thread-safe buffer for the latest camera frame
latest_frame = None
frame_lock = threading.Lock()
last_frame_time = 0

class SentryHubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global latest_frame, last_frame_time
        if self.path == '/feed':
            # Read incoming raw JPEG bytes from the Pi
            content_length = int(self.headers['Content-Length'])
            frame_data = self.rfile.read(content_length)
            
            with frame_lock:
                # Check if headers indicate raw frame format from QNX
                width_hdr = self.headers.get('X-Width')
                height_hdr = self.headers.get('X-Height')
                fmt_hdr = self.headers.get('X-Format')
                
                if width_hdr and height_hdr and fmt_hdr:
                    try:
                        import numpy as np
                        import cv2
                        
                        width = int(width_hdr)
                        height = int(height_hdr)
                        fmt = int(fmt_hdr)
                        
                        raw_arr = np.frombuffer(frame_data, dtype=np.uint8)
                        
                        # Handle different frame buffer formats
                        if len(raw_arr) == width * height * 4: # BGR8888 or RGB8888
                            img = raw_arr.reshape((height, width, 4))
                            # Most QNX camera feeds default to BGR8888 (fmt=0) or RGB8888 (fmt=1)
                            # Convert BGRx/RGBx to 3-channel BGR for JPEG compression
                            bgr_img = img[:, :, :3]
                            if fmt == 1: # RGB8888 -> swap red and blue channels
                                bgr_img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                            _, jpeg = cv2.imencode('.jpg', bgr_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            latest_frame = jpeg.tobytes()
                        elif len(raw_arr) == int(width * height * 1.5): # NV12 (YUV420 semi-planar)
                            yuv = raw_arr.reshape((int(height * 1.5), width))
                            bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_NV12)
                            _, jpeg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            latest_frame = jpeg.tobytes()
                        elif fmt == 14: # CAMERA_FRAMETYPE_YCBYCR (YUV 4:2:2 packed / YUYV / YUY2)
                            yuv = raw_arr.reshape((height, width, 2))
                            bgr = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_YUY2)
                            _, jpeg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            latest_frame = jpeg.tobytes()
                        else:
                            # Unsupported buffer layout fallback
                            latest_frame = frame_data
                    except Exception as e:
                        print(f"Error converting raw frame: {e}")
                        latest_frame = frame_data
                else:
                    # Direct JPEG fallback
                    latest_frame = frame_data
                    
                last_frame_time = time.time()
                
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            
    def do_GET(self):
        global latest_frame, last_frame_time
        if self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            try:
                while True:
                    # If no frame received in the last 5 seconds, idle
                    if time.time() - last_frame_time > 5.0:
                        time.sleep(0.5)
                        continue
                        
                    with frame_lock:
                        frame = latest_frame
                    
                    if frame:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', str(len(frame)))
                        self.end_headers()
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                    
                    time.sleep(0.05) # Stream at ~20 FPS
            except Exception:
                pass
        else:
            self.send_response(404)
            self.end_headers()

def main():
    # Bind to 0.0.0.0 so the Pi on the local network can hit it
    server = HTTPServer(('0.0.0.0', 8080), SentryHubHandler)
    print("Sentry Hub broadcasting at: http://localhost:8080/stream.mjpg")
    print("Point your Cloudflare Tunnel to this port.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Broadcast Server.")

if __name__ == "__main__":
    main()
