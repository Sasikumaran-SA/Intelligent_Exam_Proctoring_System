import base64
import os
import uuid

def save_snapshot(frame_data, directory="snapshots"):
    """
    Saves a base64 string or an OpenCV frame to a file and returns the path.
    """
    base_dir = os.path.join(os.path.dirname(__file__), "..", "public", directory)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(base_dir, filename)
    public_url = f"/{directory}/{filename}"
    
    if isinstance(frame_data, str):
        # Decode base64
        if "," in frame_data:
            frame_data = frame_data.split(',')[1]
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(frame_data))
    else:
        # Save opencv frame
        import cv2
        cv2.imwrite(filepath, frame_data)
        
    return public_url
