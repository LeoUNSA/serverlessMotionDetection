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
SERIAL_PORT = '/dev/ttyUSB0' # Update this to match your connected Arduino
BAUD_RATE = 9600
API_URL = "https://abal53wj01.execute-api.us-east-1.amazonaws.com/" # Placeholder, will be updated after Terraform deploy
SENSOR_ID = "PIR_SENSOR_01"

# Motion detection sensitivity settings
COOLDOWN_PERIOD = 1  # Seconds to wait before sending another motion event
CONFIRMATION_READINGS = 10  # Number of consecutive "ON" readings required to confirm motion
READING_INTERVAL = 0.5  # Seconds between readings for confirmation
DEBUG_COOLDOWN = False  # Set to True to see cooldown messages

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
    last_sent_time = 0  # Timestamp of last sent event
    consecutive_on_count = 0  # Counter for consecutive ON readings
    
    print("Fog Node Running. Waiting for motion...")

    while True:
        try:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                except UnicodeDecodeError:
                    continue  # Skip corrupted data
                
                # Filter logic with cooldown and confirmation
                if line == "ON":
                    current_time = time.time()
                    time_since_last_event = current_time - last_sent_time
                    
                    # If we're in cooldown period, ignore all readings and reset counter
                    if time_since_last_event < COOLDOWN_PERIOD:
                        if DEBUG_COOLDOWN and consecutive_on_count == 0:
                            print(f"In cooldown: {time_since_last_event:.1f}s / {COOLDOWN_PERIOD}s - ignoring sensor")
                        consecutive_on_count = 0  # Reset counter during cooldown
                        continue
                    
                    # Only count consecutive readings if we're outside cooldown period
                    consecutive_on_count += 1
                    
                    # Check if we have enough consecutive readings
                    if consecutive_on_count >= CONFIRMATION_READINGS and last_state != "ON":
                        
                        print(f"✓ Motion Confirmed! ({consecutive_on_count} readings, {time_since_last_event:.1f}s since last event)")
                        print("Capturing event...")
                        
                        # Capture Image
                        image_b64 = capture_image()
                        
                        data = {
                            "sensor": SENSOR_ID,
                            "timestamp": current_time,
                            "type": "motion_detected"
                        }
                        
                        if image_b64:
                            print(f"Image captured ({len(image_b64)} bytes).")
                            data["image"] = image_b64
                        
                        try:
                            # Send to Cloud
                            if "YOUR_API" not in API_URL:
                                response = requests.post(f"{API_URL}/motion", json=data)
                                print(f"  Server response: {response.status_code}")
                            else:
                                print("  API URL not set. Skipping upload.")
                        except Exception as req_err:
                            print(f"  Error sending request: {req_err}")

                        last_state = "ON"
                        last_sent_time = current_time
                        consecutive_on_count = 0  # Reset counter after sending
                    elif consecutive_on_count < CONFIRMATION_READINGS:
                        print(f"  Confirming motion... {consecutive_on_count}/{CONFIRMATION_READINGS}")
                
                elif line == "OFF":
                    if consecutive_on_count > 0 and consecutive_on_count < CONFIRMATION_READINGS:
                        print(f"  Motion cancelled - only {consecutive_on_count}/{CONFIRMATION_READINGS} readings")
                    consecutive_on_count = 0  # Reset counter on OFF
                    last_state = "OFF"
                
                # Small delay between readings for confirmation logic
                time.sleep(READING_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
