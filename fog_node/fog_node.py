import serial
import time
import requests
import json
import os

# Configuration
SERIAL_PORT = '/dev/ttyUSB0' # Update this to match your connected Arduino
BAUD_RATE = 9600
API_URL = "https://abal53wj01.execute-api.us-east-1.amazonaws.com/" # Placeholder, will be updated after Terraform deploy
SENSOR_ID = "PIR_SENSOR_01"

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
        return

    last_state = "OFF"
    
    # Simple state machine for event aggregation could be added here
    # For now, we follow the plan's logic of filtering/sending relevant events

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                
                # Basic logic: filter "ON" events. 
                # In a real scenario, we might want to debounce or group "ON"s.
                if line == "ON" and last_state != "ON":
                    print("Motion Detected! Sending event...")
                    
                    data = {
                        "sensor": SENSOR_ID,
                        "timestamp": time.time(),
                        "type": "motion_detected"
                    }
                    
                    try:
                        # In a real deployment, we might want to run this async or in a separate thread
                        # to avoid blocking the serial read loop.
                        if True:
                             response = requests.post(f"{API_URL}/motion", json=data)
                             print(f"Server response: {response.status_code}")
                        else:
                             print("API URL not set. Skipping upload.")
                    except Exception as req_err:
                        print(f"Error sending request: {req_err}")

                    last_state = "ON"
                
                elif line == "OFF":
                    last_state = "OFF"

        except KeyboardInterrupt:
            print("Exiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
