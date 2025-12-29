import serial
import time
import requests
import json
import base64
import os

# Try importing OpenCV
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    print("OpenCV (cv2) not found. Image capture disabled.")
    CV2_AVAILABLE = False

# Configuration
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600
# Placeholder - user must update this!
API_URL = "https://abal53wj01.execute-api.us-east-1.amazonaws.com" 
SENSOR_ID = "PIR_SENSOR_01"

def capture_image():
    if not CV2_AVAILABLE:
        return None
    
    try:
        # Open default camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Could not open camera")
            return None
            
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            # Resize to reduce payload size (e.g., 640x480)
            frame = cv2.resize(frame, (640, 480))
            # Encode as JPEG
            retval, buffer = cv2.imencode('.jpg', frame)
            if retval:
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                return jpg_as_text
    except Exception as e:
        print(f"Camera error: {e}")
    
    return None

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
        # For testing without Arduino, we loop but don't crash
        # return 

    last_state = "OFF"
    
    print("Fog Node Running. Waiting for motion...")

    while True:
        try:
            # Check for serial data
            if 'ser' in locals() and ser.is_open and ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                
                if line == "ON" and last_state != "ON":
                    print("Motion Detected! Capturing event...")
                    
                    # Capture Image
                    image_b64 = capture_image()
                    
                    data = {
                        "sensor": SENSOR_ID,
                        "timestamp": time.time(),
                        "type": "motion_detected"
                    }
                    
                    if image_b64:
                        print(f"Image captured ({len(image_b64)} bytes).")
                        data["image"] = image_b64

                    # Send to Cloud
                    try:
                        if "YOUR_API" not in API_URL:
                             response = requests.post(f"{API_URL}/motion", json=data)
                             print(f"Cloud upload: {response.status_code}")
                    except Exception as req_err:
                        print(f"Upload failed: {req_err}")

                    last_state = "ON"
                
                elif line == "OFF":
                    last_state = "OFF"

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
