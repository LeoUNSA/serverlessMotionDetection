import serial
import time
import json
import base64
import os
import urllib.request
import urllib.error
from collections import deque

# Try importing OpenCV and numpy
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    print("OpenCV (cv2) or numpy not found. Image capture disabled.")
    CV2_AVAILABLE = False

# Configuration
SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 9600
# Placeholder - user must update this!
API_URL = "https://abal53wj01.execute-api.us-east-1.amazonaws.com" 
SENSOR_ID = "PIR_SENSOR_01"

# Fog Computing - Motion Detection Parameters
MIN_MOTION_FRAMES = 3          # Número mínimo de frames consecutivos con movimiento
MOTION_THRESHOLD = 25          # Umbral de diferencia de píxeles (0-255)
MIN_CONTOUR_AREA = 500         # Área mínima de contorno para considerar movimiento real
MAX_CONTOUR_AREA = 200000      # Área máxima (evita cambios de iluminación completos)
CONFIDENCE_THRESHOLD = 0.6     # Confianza mínima para enviar a cloud (0.0-1.0)
FRAME_BUFFER_SIZE = 5          # Tamaño del buffer de frames para análisis
COOLDOWN_PERIOD = 5            # Segundos de espera después de enviar un evento

# Timing Parameters
REFERENCE_FRAMES_COUNT = 5     # Cantidad de frames de referencia a capturar
ANALYSIS_FRAMES_COUNT = 15     # Cantidad de frames a analizar (más tiempo de análisis)
FRAME_DELAY = 0.15             # Delay entre frames (segundos) - ~6-7 FPS
REFERENCE_FRAME_DELAY = 0.1    # Delay entre frames de referencia

class MotionDetector:
    """
    Clase para detección inteligente de movimiento en el edge/fog.
    Analiza múltiples frames y criterios para filtrar falsos positivos.
    """
    def __init__(self):
        self.frame_buffer = deque(maxlen=FRAME_BUFFER_SIZE)
        self.motion_frame_count = 0
        self.last_valid_motion_time = 0
        self.background_frame = None
        self.is_initialized = False
        
    def analyze_frame(self, frame):
        """
        Analiza un frame y determina si hay movimiento real.
        Retorna (is_motion, confidence, debug_info)
        """
        if not self.is_initialized:
            self._initialize_background(frame)
            return False, 0.0, {
                'status': 'Initializing background model',
                'confidence': '0.00',
                'contours': 0,
                'motion_area': 0,
                'consistency': '0.00',
                'mean_diff': '0.00',
                'motion_frames': 0
            }
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Agregar al buffer
        self.frame_buffer.append(gray)
        
        if len(self.frame_buffer) < 2:
            return False, 0.0, {
                'status': 'Building frame buffer',
                'confidence': '0.00',
                'contours': 0,
                'motion_area': 0,
                'consistency': '0.00',
                'mean_diff': '0.00',
                'motion_frames': 0
            }
        
        # Calcular diferencia con frame anterior y con background
        frame_diff = cv2.absdiff(self.frame_buffer[-1], self.frame_buffer[-2])
        bg_diff = cv2.absdiff(gray, self.background_frame)
        
        # Umbralizar las diferencias
        _, frame_thresh = cv2.threshold(frame_diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
        _, bg_thresh = cv2.threshold(bg_diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
        
        # Dilatar para llenar huecos
        kernel = np.ones((5,5), np.uint8)
        frame_thresh = cv2.dilate(frame_thresh, kernel, iterations=2)
        bg_thresh = cv2.dilate(bg_thresh, kernel, iterations=2)
        
        # Encontrar contornos en ambas diferencias
        contours_frame, _ = cv2.findContours(frame_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_bg, _ = cv2.findContours(bg_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Analizar contornos significativos
        significant_contours = []
        total_motion_area = 0
        
        for contour in contours_bg:
            area = cv2.contourArea(contour)
            if MIN_CONTOUR_AREA < area < MAX_CONTOUR_AREA:
                significant_contours.append(contour)
                total_motion_area += area
        
        # Calcular métricas de confianza
        confidence_factors = []
        debug_info = {}
        
        # Factor 1: Número de contornos significativos (peso: 0.3)
        contour_score = min(len(significant_contours) / 3.0, 1.0)
        confidence_factors.append(contour_score * 0.3)
        debug_info['contours'] = len(significant_contours)
        
        # Factor 2: Área total de movimiento (peso: 0.25)
        area_score = min(total_motion_area / 50000.0, 1.0) if total_motion_area > 0 else 0
        confidence_factors.append(area_score * 0.25)
        debug_info['motion_area'] = total_motion_area
        
        # Factor 3: Consistencia entre frames (peso: 0.25)
        frame_consistency = len(contours_frame) / max(len(contours_bg), 1)
        consistency_score = min(frame_consistency, 1.0)
        confidence_factors.append(consistency_score * 0.25)
        debug_info['consistency'] = f"{consistency_score:.2f}"
        
        # Factor 4: Diferencia promedio de píxeles (peso: 0.2)
        mean_diff = np.mean(bg_diff)
        diff_score = min(mean_diff / 50.0, 1.0)
        confidence_factors.append(diff_score * 0.2)
        debug_info['mean_diff'] = f"{mean_diff:.2f}"
        
        # Confianza total
        confidence = sum(confidence_factors)
        debug_info['confidence'] = f"{confidence:.2f}"
        
        # Verificar si hay movimiento real
        has_motion = (
            confidence >= CONFIDENCE_THRESHOLD and
            len(significant_contours) > 0 and
            total_motion_area > MIN_CONTOUR_AREA
        )
        
        # Contador de frames consecutivos con movimiento
        if has_motion:
            self.motion_frame_count += 1
        else:
            self.motion_frame_count = max(0, self.motion_frame_count - 1)
        
        debug_info['motion_frames'] = self.motion_frame_count
        
        # Actualizar background gradualmente (adaptación a cambios de luz)
        self.background_frame = cv2.addWeighted(
            self.background_frame, 0.95, gray, 0.05, 0
        ).astype(np.uint8)
        
        # Movimiento confirmado solo si hay suficientes frames consecutivos
        is_confirmed = self.motion_frame_count >= MIN_MOTION_FRAMES
        
        return is_confirmed, confidence, debug_info
    
    def _initialize_background(self, frame):
        """Inicializa el modelo de background"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.background_frame = cv2.GaussianBlur(gray, (21, 21), 0)
        self.is_initialized = True
        print("Background model initialized")
    
    def reset_motion_count(self):
        """Resetea el contador de movimiento después de enviar evento"""
        self.motion_frame_count = 0
        self.last_valid_motion_time = time.time()
    
    def is_in_cooldown(self):
        """Verifica si estamos en período de cooldown"""
        return (time.time() - self.last_valid_motion_time) < COOLDOWN_PERIOD


def verify_motion_with_camera():
    """
    Verifica si el movimiento detectado por el PIR es real usando análisis de video.
    El PIR ya detectó algo, ahora validamos con la cámara.
    Retorna (is_real_motion, confidence, image_b64, debug_info)
    """
    if not CV2_AVAILABLE:
        print("⚠️  OpenCV not available, cannot verify motion. Assuming PIR is correct.")
        # Sin OpenCV, confiamos en el PIR y capturamos una imagen simple
        image = capture_image()
        return True, 1.0, image, "OpenCV not available"
    
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("⚠️  Could not open camera, cannot verify. Assuming PIR is correct.")
            return True, 1.0, None, "Camera unavailable"
        
        print("📹 Camera opened, capturing frames for analysis...")
        print(f"   Will analyze for ~{(REFERENCE_FRAMES_COUNT * REFERENCE_FRAME_DELAY + ANALYSIS_FRAMES_COUNT * FRAME_DELAY):.1f} seconds")
        
        # FASE 1: Capturar frames de referencia (escena inicial)
        print(f"📸 Phase 1: Capturing {REFERENCE_FRAMES_COUNT} reference frames...")
        reference_frames = []
        for i in range(REFERENCE_FRAMES_COUNT):
            ret, frame = cap.read()
            if ret:
                reference_frames.append(cv2.resize(frame, (640, 480)))
                print(f"   Reference frame {i+1}/{REFERENCE_FRAMES_COUNT} captured")
            time.sleep(REFERENCE_FRAME_DELAY)
        
        if len(reference_frames) < 2:
            cap.release()
            return True, 1.0, None, "Not enough reference frames"
        
        # Calcular frame de referencia promedio (background)
        reference = reference_frames[0].copy().astype(np.float32)
        for rf in reference_frames[1:]:
            reference = cv2.addWeighted(reference, 0.5, rf.astype(np.float32), 0.5, 0)
        reference = reference.astype(np.uint8)
        
        # Convertir referencia a escala de grises
        ref_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        ref_gray = cv2.GaussianBlur(ref_gray, (21, 21), 0)
        
        print(f"✓ Background model established")
        
        # FASE 2: Capturar y analizar frames actuales (buscar movimiento)
        print(f"🔍 Phase 2: Analyzing {ANALYSIS_FRAMES_COUNT} frames for motion...")
        motion_scores = []
        max_confidence = 0.0
        best_frame = None
        frames_with_motion = 0
        detailed_logs = []
        
        for frame_idx in range(ANALYSIS_FRAMES_COUNT):
            ret, frame = cap.read()
            if not ret:
                continue
            
            frame_resized = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            # Diferencia con frame de referencia
            diff = cv2.absdiff(ref_gray, gray)
            _, thresh = cv2.threshold(diff, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
            
            # Dilatar para llenar huecos
            kernel = np.ones((5, 5), np.uint8)
            thresh = cv2.dilate(thresh, kernel, iterations=2)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filtrar contornos significativos
            significant_contours = []
            total_area = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if MIN_CONTOUR_AREA < area < MAX_CONTOUR_AREA:
                    significant_contours.append(contour)
                    total_area += area
            
            # Calcular score de este frame
            num_contours = len(significant_contours)
            mean_diff = np.mean(diff)
            
            # Score simple basado en área y diferencia
            frame_score = 0.0
            if num_contours > 0:
                area_score = min(total_area / 50000.0, 1.0)
                diff_score = min(mean_diff / 50.0, 1.0)
                contour_score = min(num_contours / 3.0, 1.0)
                frame_score = (area_score * 0.4) + (diff_score * 0.3) + (contour_score * 0.3)
            
            motion_scores.append(frame_score)
            
            # Contar frames con movimiento significativo
            if frame_score >= CONFIDENCE_THRESHOLD:
                frames_with_motion += 1
            
            # Log detallado del análisis
            status_icon = "✓" if frame_score >= CONFIDENCE_THRESHOLD else "○"
            log_line = f"  {status_icon} Frame {frame_idx+1:2d}/{ANALYSIS_FRAMES_COUNT}: Score={frame_score:.2f}, Contours={num_contours}, Area={total_area:6.0f}px²"
            print(log_line)
            detailed_logs.append(log_line)
            
            # Guardar mejor frame
            if frame_score > max_confidence:
                max_confidence = frame_score
                best_frame = frame_resized.copy()
            
            # Actualizar referencia ligeramente (adaptación a cambios de luz)
            ref_gray = cv2.addWeighted(ref_gray, 0.92, gray, 0.08, 0)
            
            time.sleep(FRAME_DELAY)
        
        cap.release()
        print(f"✓ Analysis complete. Camera released.\n")
        
        # FASE 3: Decisión final
        print("📊 Computing final decision...")
        avg_confidence = sum(motion_scores) / len(motion_scores) if motion_scores else 0.0
        
        # Calcular también mediana para ser más robusto contra outliers
        sorted_scores = sorted(motion_scores)
        median_confidence = sorted_scores[len(sorted_scores)//2] if sorted_scores else 0.0
        
        is_real = (
            frames_with_motion >= MIN_MOTION_FRAMES and 
            max_confidence >= CONFIDENCE_THRESHOLD and
            avg_confidence >= (CONFIDENCE_THRESHOLD * 0.4)  # Un poco más permisivo
        )
        
        # Crear resumen detallado
        debug_summary = {
            "total_frames": len(motion_scores),
            "frames_with_motion": frames_with_motion,
            "max_confidence": round(max_confidence, 3),
            "avg_confidence": round(avg_confidence, 3),
            "median_confidence": round(median_confidence, 3),
            "threshold_used": CONFIDENCE_THRESHOLD,
            "min_frames_required": MIN_MOTION_FRAMES,
            "analysis_duration": f"{(REFERENCE_FRAMES_COUNT * REFERENCE_FRAME_DELAY + ANALYSIS_FRAMES_COUNT * FRAME_DELAY):.1f}s"
        }
        
        debug_text = (f"Analyzed: {len(motion_scores)} frames, "
                     f"Motion in: {frames_with_motion} frames, "
                     f"Max: {max_confidence:.2f}, "
                     f"Avg: {avg_confidence:.2f}, "
                     f"Median: {median_confidence:.2f}")
        
        print(f"   {debug_text}")
        print(f"   Required: ≥{MIN_MOTION_FRAMES} frames with score ≥{CONFIDENCE_THRESHOLD}")
        print(f"   Decision: {'✓ REAL MOTION' if is_real else '✗ FALSE POSITIVE'}")
        
        # Codificar mejor frame si hay movimiento real
        image_b64 = None
        if is_real and best_frame is not None:
            print(f"   Encoding best frame (quality=85%)...")
            retval, buffer = cv2.imencode('.jpg', best_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if retval:
                image_b64 = base64.b64encode(buffer).decode('utf-8')
                print(f"   Image size: {len(image_b64)} bytes\n")
        
        return is_real, max_confidence, image_b64, json.dumps(debug_summary)
        
    except Exception as e:
        print(f"❌ Motion verification error: {e}")
        import traceback
        traceback.print_exc()
        return False, 0.0, None, f"Error: {str(e)}"


def capture_image():
    """Captura simple de imagen (método legacy)"""
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

def send_to_cloud(data):
    try:
        if "YOUR_API" in API_URL:
             print("Please configure API_URL script.")
             return

        url = f"{API_URL}/motion"
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        jsondata = json.dumps(data).encode('utf-8')
        
        print(f"Sending verified motion event to cloud...")
        with urllib.request.urlopen(req, jsondata, timeout=10) as response:
            print(f"✓ Cloud upload successful: {response.getcode()}")
            
    except urllib.error.HTTPError as e:
        print(f"✗ HTTP Error: {e.code} - {e.reason}")
    except urllib.error.URLError as e:
        print(f"✗ URL Error: {e.reason}")
    except Exception as e:
        print(f"✗ Upload failed: {e}")

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
        # For testing without Arduino, we loop but don't crash
        # return 

    last_state = "OFF"
    detector_cooldown = 0
    
    print("=" * 60)
    print("FOG NODE - Intelligent Motion Detection System")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  - Min motion frames: {MIN_MOTION_FRAMES}")
    print(f"  - Motion threshold: {MOTION_THRESHOLD}")
    print(f"  - Min contour area: {MIN_CONTOUR_AREA} px²")
    print(f"  - Max contour area: {MAX_CONTOUR_AREA} px²")
    print(f"  - Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"  - Cooldown period: {COOLDOWN_PERIOD}s")
    print(f"  - Reference frames: {REFERENCE_FRAMES_COUNT}")
    print(f"  - Analysis frames: {ANALYSIS_FRAMES_COUNT}")
    print(f"  - Analysis duration: ~{(REFERENCE_FRAMES_COUNT * REFERENCE_FRAME_DELAY + ANALYSIS_FRAMES_COUNT * FRAME_DELAY):.1f}s per event")
    print("=" * 60)
    print("Waiting for motion events from PIR sensor...\n")

    while True:
        try:
            # Check for serial data
            if 'ser' in locals() and ser.is_open and ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                
                if line == "ON" and last_state != "ON":
                    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🚨 PIR Sensor triggered!")
                    
                    # Verificar cooldown
                    if time.time() < detector_cooldown:
                        remaining = int(detector_cooldown - time.time())
                        print(f"⏳ In cooldown period. Ignoring event ({remaining}s remaining)")
                        last_state = "ON"
                        continue
                    
                    print("🔍 PIR detected something. Starting camera verification...")
                    print("=" * 60)
                    
                    # VERIFICAR con cámara si el movimiento del PIR es real
                    verification_start = time.time()
                    is_real, confidence, image_b64, debug_info = verify_motion_with_camera()
                    verification_time = time.time() - verification_start
                    
                    print("=" * 60)
                    if is_real:
                        print(f"✅ REAL MOTION CONFIRMED!")
                        print(f"   Confidence: {confidence:.2f}")
                        print(f"   Verification time: {verification_time:.1f}s")
                        print(f"   Details: {debug_info}")
                        
                        if image_b64:
                            print(f"\n📤 Sending verified event to AWS Lambda...")
                            
                            data = {
                                "sensor": SENSOR_ID,
                                "timestamp": time.time(),
                                "type": "motion_detected",
                                "confidence": round(confidence, 3),
                                "fog_verified": True,
                                "verification_time": round(verification_time, 2),
                                "verification_details": debug_info,
                                "image": image_b64
                            }
                            
                            # Enviar a la nube solo si es movimiento real
                            send_to_cloud(data)
                            
                            # Establecer cooldown
                            detector_cooldown = time.time() + COOLDOWN_PERIOD
                            print(f"⏳ Cooldown activated for {COOLDOWN_PERIOD} seconds")
                            print("=" * 60 + "\n")
                        else:
                            print("⚠️  Motion confirmed but no image captured. Not sending.")
                            print("=" * 60 + "\n")
                        
                    else:
                        print(f"❌ FALSE POSITIVE DETECTED!")
                        print(f"   PIR triggered but camera analysis shows no real motion")
                        print(f"   Max confidence: {confidence:.2f} (threshold: {CONFIDENCE_THRESHOLD})")
                        print(f"   Verification time: {verification_time:.1f}s")
                        print(f"   Details: {debug_info}")
                        print(f"   → Filtered by fog node. NOT sending to AWS 💰")
                        print("=" * 60 + "\n")
                    
                    last_state = "ON"
                
                elif line == "OFF":
                    if last_state != "OFF":
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] PIR: No motion")
                    last_state = "OFF"

        except KeyboardInterrupt:
            print("\n\nShutting down fog node...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)
    
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Serial connection closed.")

if __name__ == "__main__":
    main()
