import zmq
import time
import cv2
import numpy as np
import threading

EXTERNAL_CAMERAS = ["cam1", "cam2", "cam3"]
INTERNAL_CAMERAS = ["cam4", "cam5"]

ALL_CAMERAS = EXTERNAL_CAMERAS + INTERNAL_CAMERAS


def start_zmq_receiver(data_manager, frame_queue):
    def receiver():
        context = zmq.Context()
        socket = context.socket(zmq.PULL)
        socket.setsockopt(zmq.RCVHWM, 5)
        socket.setsockopt(zmq.LINGER, 0)
        socket.bind("tcp://*:5555")
        print("[ZMQ] Alıcı başlatıldı")

        while True:
            try:
                if socket.poll(timeout=1):
                    msg = socket.recv_json(zmq.NOBLOCK)
                    cam_name = msg["cam"]
                    img_bytes = bytes.fromhex(msg["img"])
                    npimg = np.frombuffer(img_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

                    if frame is not None and cam_name in ALL_CAMERAS:
                        cam_type = "external" if cam_name in EXTERNAL_CAMERAS else "internal"
                        data_manager.add_frame(cam_type, cam_name, frame)

                        try:
                            if frame_queue.qsize() < 10:
                                frame_queue.put_nowait((cam_name, frame))
                            else:
                                frame_queue.get_nowait()
                                frame_queue.put_nowait((cam_name, frame))
                        except:
                            pass
            except Exception as e:
                print(f"[ZMQ ERROR] {e}")
                time.sleep(0.01)

    threading.Thread(target=receiver, daemon=True).start()
