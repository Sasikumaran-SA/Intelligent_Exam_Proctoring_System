import cv2
import numpy as np
import base64
import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class GazeProcessor:
    def __init__(self):
        # We upgraded from the deprecated `mp.solutions` down to the brand-new 
        # MediaPipe Vision Tasks API (which natively supports modern Python 3.11)!
        model_path = os.path.join(os.path.dirname(__file__), '..', 'face_landmarker.task')
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1)
        self.detector = vision.FaceLandmarker.create_from_options(options)

    def decode_base64_frame(self, base64_string: str):
        if "," in base64_string:
            base64_string = base64_string.split(',')[1]
        img_data = base64.b64decode(base64_string)
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame
        
    def process_frame(self, frame):
        # The new Tasks API requires images to be converted into an mp.Image object
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        # Super fast object detection
        detection_result = self.detector.detect(mp_image)
        
        alerts = []
        face_detected = False
        annotated_frame = frame.copy()
        
        if detection_result and len(detection_result.face_landmarks) > 0:
            face_detected = True
            landmarks = detection_result.face_landmarks[0]
            
            # --- 1. HEAD PITCH (Up/Down) & YAW (Left/Right) ---
            nose_x = landmarks[4].x
            left_x = landmarks[234].x
            right_x = landmarks[454].x
            
            dx_left = abs(nose_x - left_x)
            dx_right = abs(nose_x - right_x)
            
            dy_top = abs(landmarks[4].y - landmarks[10].y)
            dy_bottom = abs(landmarks[152].y - landmarks[4].y)
            
            # --- 2. IRIS MONITORING (Compensation Check) ---
            is_looking_at_screen = True # Default assumption
            if len(landmarks) > 473:
                # Right Eye Horizontal Ratio
                r_outer = landmarks[33].x
                r_inner = landmarks[133].x
                r_iris_x = landmarks[468].x
                r_dist_x = abs(r_inner - r_outer)
                r_iris_ratio_x = abs(r_iris_x - r_outer) / r_dist_x if r_dist_x > 0 else 0.5
                
                # Right Eye Vertical Ratio
                r_top = landmarks[159].y
                r_bottom = landmarks[145].y
                r_iris_y = landmarks[468].y
                r_dist_y = abs(r_top - r_bottom)
                r_iris_ratio_y = (r_iris_y - r_top) / r_dist_y if r_dist_y > 0 else 0.5

                # Head Yaw Compensation Check
                if dx_left + dx_right > 0:
                    yaw_ratio = dx_left / (dx_left + dx_right)
                    
                    # Head Turned Right (from student's view) -> Need eyes to look Left (Higher ratio)
                    if yaw_ratio < 0.35:
                        if r_iris_ratio_x < 0.55: # Broader "safe" zone (was 0.65)
                            alerts.append("Head Turned Right")
                    
                    # Head Turned Left (from student's view) -> Need eyes to look Right (Lower ratio)
                    elif yaw_ratio > 0.65:
                        if r_iris_ratio_x > 0.45: # Broader "safe" zone (was 0.35)
                            alerts.append("Head Turned Left")
                
                # Head Pitch Compensation Check
                if dy_top + dy_bottom > 0:
                    pitch_ratio = dy_top / (dy_top + dy_bottom)
                    
                    # Looking Up -> Need eyes to look Down (Higher Y-ratio)
                    if pitch_ratio < 0.40:
                        if r_iris_ratio_y < 0.55: # Broader "safe" zone (was 0.60)
                            alerts.append("Looking Up")
                    
                    # Looking Down -> Need eyes to look Up (Lower Y-ratio)
                    elif pitch_ratio > 0.60:
                        if r_iris_ratio_y > 0.45: # Broader "safe" zone (was 0.40)
                            alerts.append("Looking Down")
            
            # Draw a green dot on the nose to show tracking is active
            h, w, c = frame.shape
            cv2.circle(annotated_frame, (int(nose_x * w), int(landmarks[4].y * h)), 4, (0, 255, 0), -1)
            
        # Determine if pose is neutral (facing camera)
        is_neutral = False
        if face_detected:
            # Check if eye-to-nose ratios are balanced
            dx_total = dx_left + dx_right
            dy_total = dy_top + dy_bottom
            if dx_total > 0 and dy_total > 0:
                y_r = dx_left / dx_total
                p_r = dy_top / dy_total
                # Neutral range: No alerts triggered for rotation
                if (0.35 <= y_r <= 0.65) and (0.40 <= p_r <= 0.60):
                    is_neutral = True

        alerts = list(set(alerts))

        return {
            "alerts": alerts,
            "annotated_frame": annotated_frame,
            "face_detected": face_detected,
            "landmarks": landmarks if face_detected else None,
            "is_neutral": is_neutral
        }

    def get_face_encoding(self, frame):
        return np.zeros(128).tolist(), None
        
    def verify_face(self, frame, enrolled_encoding_list):
        return True, None
