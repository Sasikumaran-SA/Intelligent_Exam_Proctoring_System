import numpy as np

class IdentityProcessor:
    def __init__(self, tolerance=0.20):
        self.tolerance = tolerance
        # Stores the reference baseline for each session
        self.baselines = {} # {session_id: [ratios]}

    def calculate_signature(self, landmarks):
        """
        Extracts a 1D signature (normalized ratios) from face landmarks.
        Uses key points as defined by MediaPipe Face Mesh.
        """
        try:
            # 1. Helper to calculate Euclidean distance between two points
            def dist(p1, p2):
                return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

            # 2. Key Landmark Indexes
            # Top: 10, Bottom: 152, Left: 234, Right: 454
            # Nose Tip: 4
            # Eye Centers (approx): 468 (R), 473 (L)
            # Mouth Corners: 61, 291
            # Eyebrow Centers: 105 (R), 334 (L)

            face_h = dist(landmarks[10], landmarks[152])
            face_w = dist(landmarks[234], landmarks[454])
            
            if face_h == 0 or face_w == 0: return None

            # 3. Calculate Ratios (Distance / Face Scale) using universally available base contour points
            ratios = [
                dist(landmarks[159], landmarks[386]) / face_w,  # Inter-eye (top lids) / face width
                dist(landmarks[4], landmarks[152]) / face_h,    # Nose-to-chin / face height
                dist(landmarks[10], landmarks[4]) / face_h,     # Forehead-to-nose / face height
                dist(landmarks[61], landmarks[291]) / face_w,   # Mouth width / face width
                dist(landmarks[105], landmarks[159]) / face_h,  # R Eyebrow-to-eye / face height
                dist(landmarks[334], landmarks[386]) / face_h,  # L Eyebrow-to-eye / face height
                dist(landmarks[159], landmarks[61]) / face_h,   # R Eye-to-mouth / face height
                dist(landmarks[386], landmarks[291]) / face_h,  # L Eye-to-mouth / face height
                dist(landmarks[4], landmarks[61]) / face_w,     # Nose-to-Rmouth / face width
                dist(landmarks[4], landmarks[454]) / face_w,    # Nose-to-edge / face width
            ]
            
            return np.array(ratios)
        except Exception as e:
            # Prevent backend crashes on index out of range
            print(f"Warning: Signature calculation failed: {e}")
            return None

    def verify_identity(self, session_id, current_signature):
        """
        Compare current signature with stored baseline.
        Returns True if matched, False if fraud, None if no baseline.
        """
        if session_id not in self.baselines:
            # Save this as the baseline
            self.baselines[session_id] = current_signature
            return True
        
        baseline = self.baselines[session_id]
        
        # Calculate Mean Squared Error or Mean Absolute Percentage Error
        # Using Relative difference to be scale invariant
        diff = np.abs(current_signature - baseline) / (baseline + 1e-6)
        mean_diff = np.mean(diff)
        
        # If average deviation across all ratios > 15%, highly likely a different person
        if mean_diff > self.tolerance:
            return False
        return True

    def reset_session(self, session_id):
        if session_id in self.baselines:
            del self.baselines[session_id]
