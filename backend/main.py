import json
import datetime
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
import base64
import os
from typing import Dict, List

import models, schemas, database
from services.gaze_processor import GazeProcessor
from services.audio_processor import AudioProcessor
from services.identity_processor import IdentityProcessor
from services.report_generator import generate_session_report
from api_utils import save_snapshot

# Setup Database
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Exam Cheating Detection API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static files directory for snapshots
public_dir = os.path.join(os.path.dirname(__file__), "..", "public")
snapshots_dir = os.path.join(public_dir, "snapshots")
if not os.path.exists(snapshots_dir):
    os.makedirs(snapshots_dir)
app.mount("/snapshots", StaticFiles(directory=snapshots_dir), name="snapshots")

# Connection Manager for WebSockets (Admin dashboard notifications)
class ConnectionManager:
    def __init__(self):
        self.active_admin_connections: List[WebSocket] = []

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.active_admin_connections.append(websocket)

    def disconnect_admin(self, websocket: WebSocket):
        if websocket in self.active_admin_connections:
            self.active_admin_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_admin_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()
gaze_processor = GazeProcessor()
audio_processor = AudioProcessor()
identity_processor = IdentityProcessor()

@app.post("/users", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.student_id == user.student_id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Student ID already registered")
        
    encoding_json = None
    if user.enrollment_image:
        frame = gaze_processor.decode_base64_frame(user.enrollment_image)
        encoding, error = gaze_processor.get_face_encoding(frame)
        if error:
            raise HTTPException(status_code=400, detail=f"Enrollment Error: {error}")
        if encoding is not None:
            encoding_json = json.dumps(encoding if isinstance(encoding, list) else encoding.tolist())
            
    new_user = models.User(
        name=user.name, 
        student_id=user.student_id, 
        face_encoding=encoding_json
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users", response_model=List[schemas.UserOut])
def get_users(db: Session = Depends(database.get_db)):
    return db.query(models.User).all()

@app.post("/sessions", response_model=schemas.SessionOut)
def create_session(session: schemas.SessionCreate, db: Session = Depends(database.get_db)):
    new_session = models.ExamSession(student_id=session.student_id)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@app.get("/violations", response_model=List[schemas.ViolationOut])
def get_violations(db: Session = Depends(database.get_db)):
    violations = db.query(models.ViolationLog).order_by(models.ViolationLog.timestamp.desc()).all()
    # Add UTC timezone to naive timestamps
    for v in violations:
        if v.timestamp.tzinfo is None:
            v.timestamp = v.timestamp.replace(tzinfo=datetime.timezone.utc)
    return violations

@app.post("/log_violation_rest/{session_id}")
async def log_violation_rest(session_id: int, data: dict, db: Session = Depends(database.get_db)):
    # Retrieve session and user
    session_db = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session_db:
        raise HTTPException(status_code=404, detail="Session not found")
    
    user_db = session_db.student
    detail = data.get("detail", "Tab Switched")
    alerts = [detail]
    
    # Penalty only for switching away, not coming back
    penalty = 1.0 if "Regained" not in detail and "visible" not in detail.lower() else 0.0
    
    # Log to DB
    log = models.ViolationLog(
        session_id=session_id,
        violation_type=detail,
        snapshot_url=None
    )
    db.add(log)
    if penalty > 0:
        session_db.trust_score = max(0.0, session_db.trust_score - penalty)
    
    db.commit()
    db.refresh(session_db)
    
    # Broadcast to Admin Dashboard
    await manager.broadcast({
        "type": "violation",
        "session_id": session_id,
        "student_id": user_db.id,
        "student_name": user_db.name,
        "alerts": alerts,
        "snapshot_url": "",
        "new_trust_score": session_db.trust_score
    })
    
    return {"status": "logged"}

# WebSocket for Admin Dashboard
@app.websocket("/ws/admin")
async def websocket_admin_endpoint(websocket: WebSocket):
    await manager.connect_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)

# WebSocket for Video Streaming & Processing (Student Portal)
@app.websocket("/ws/exam/{session_id}")
async def websocket_exam_endpoint(websocket: WebSocket, session_id: int, db: Session = Depends(database.get_db)):
    await websocket.accept()
    
    # Retrieve session
    session_db = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session_db:
        await websocket.close(code=1000)
        return
        
    user_db = db.query(models.User).filter(models.User.id == session_db.student_id).first()
    enrolled_encoding_list = json.loads(user_db.face_encoding) if user_db and user_db.face_encoding else None
    
    try:
        while True:
            receive_data = await websocket.receive()
            
            # 1. Handle Binary Audio Data (PCM 16-bit 16kHz)
            if "bytes" in receive_data:
                audio_data = receive_data["bytes"]
                recognized_text = audio_processor.process_chunk(session_id, audio_data)
                
                if recognized_text:
                    # Talking Detected via STT
                    alerts = [f"Talking Detected: '{recognized_text}'"]
                    db_session = database.SessionLocal()
                    try:
                        for alert_type in alerts:
                            log = models.ViolationLog(
                                session_id=session_id,
                                violation_type=alert_type,
                                snapshot_url=""
                            )
                            db_session.add(log)
                            session_db = db_session.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
                            if session_db:
                                session_db.trust_score = max(0.0, session_db.trust_score - 0.5) # Penalty for talking
                        db_session.commit()
                        session_db = db_session.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
                        await manager.broadcast({
                            "type": "violation",
                            "session_id": session_id,
                            "student_id": user_db.id,
                            "student_name": user_db.name,
                            "alerts": alerts,
                            "snapshot_url": "",
                            "new_trust_score": session_db.trust_score
                        })
                        
                        # Notify the student directly
                        await websocket.send_json({"alert": alerts[0]})
                    finally:
                        db_session.close()
                continue

            # 2. Handle Text Metadata (Frames, etc.)
            if "text" in receive_data:
                message = json.loads(receive_data["text"])
                
                if "frame" in message:
                    frame_data = message["frame"]
                    frame = gaze_processor.decode_base64_frame(frame_data)
                    
                    # --- 1. LIVE RELAY TO ADMINS ---
                    await manager.broadcast({
                        "type": "live_frame",
                        "student_id": user_db.student_id,
                        "student_name": user_db.name,
                        "frame": frame_data
                    })
                    
                    alerts = []
                    result = gaze_processor.process_frame(frame)
                    
                    if not result["face_detected"]:
                        alerts.append("Face Not Detected")
                    else:
                        # --- 2. IDENTITY RE-AUTHENTICATION (Pose-Gated) ---
                        # Only verify if the student is facing the camera to avoid projection drift
                        if result["is_neutral"]:
                            landmarks = result["landmarks"]
                            signature = identity_processor.calculate_signature(landmarks)
                            if signature is not None:
                                match = identity_processor.verify_identity(session_id, signature)
                                if match is False:
                                    alerts.append("Wrong Person Detected")
                        
                        if result["alerts"]:
                            alerts.extend(result["alerts"])
                            
                    if alerts:
                        snapshot_url = save_snapshot(frame_data)
                        db_session = database.SessionLocal()
                        try:
                            for alert_type in alerts:
                                log = models.ViolationLog(
                                    session_id=session_id,
                                    violation_type=alert_type,
                                    snapshot_url=snapshot_url
                                )
                                db_session.add(log)
                                session_db = db_session.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
                                if session_db:
                                    session_db.trust_score = max(0.0, session_db.trust_score - 0.5)
                            
                            db_session.commit()
                            session_db = db_session.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
                            await manager.broadcast({
                                "type": "violation",
                                "session_id": session_id,
                                "student_id": user_db.id,
                                "student_name": user_db.name,
                                "alerts": alerts,
                                "snapshot_url": snapshot_url,
                                "new_trust_score": session_db.trust_score
                            })
                        finally:
                            db_session.close()

                    await websocket.send_json({"status": "processed"})

                    await websocket.send_json({"status": "processed"})
                
    except (WebSocketDisconnect, RuntimeError):
        audio_processor.cleanup_session(session_id)
        identity_processor.reset_session(session_id)

@app.get("/sessions")
def get_sessions(db: Session = Depends(database.get_db)):
    # Join with User to get student names
    sessions = db.query(models.ExamSession).all()
    result = []
    for s in sessions:
        # Create a timezone-aware ISO string for the frontend
        start_time_iso = s.start_time.replace(tzinfo=datetime.timezone.utc).isoformat()
        result.append({
            "id": s.id,
            "student_id": s.student.student_id,
            "student_name": s.student.name,
            "start_time": start_time_iso,
            "trust_score": s.trust_score,
            "violation_count": len(s.violations)
        })
    return result
        
@app.get("/generate_pdf_report/{session_id}")
def generate_pdf_report(session_id: int, db: Session = Depends(database.get_db)):
    file_path, error = generate_session_report(db, session_id)
    if error:
        raise HTTPException(status_code=404, detail=error)
    
    return FileResponse(
        path=file_path, 
        media_type='application/pdf', 
        filename=f"exam_report_{session_id}.pdf"
    )

if __name__ == "__main__":
    import uvicorn
    # host=0.0.0.0 allows access from other devices on the same network
    uvicorn.run(app, host="0.0.0.0", port=8000)
