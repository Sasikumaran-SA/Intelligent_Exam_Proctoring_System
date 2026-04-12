from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    student_id = Column(String, unique=True, index=True)
    face_encoding = Column(String, nullable=True) # Will store JSON string of 128-d array
    status = Column(String, default="active")

    sessions = relationship("ExamSession", back_populates="student")

class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    trust_score = Column(Float, default=100.0)

    student = relationship("User", back_populates="sessions")
    violations = relationship("ViolationLog", back_populates="session")

class ViolationLog(Base):
    __tablename__ = "violations_log"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    violation_type = Column(String) # "Looking Left", "Looking Right", "Face Not Detected", "Multiple Faces"
    snapshot_url = Column(String, nullable=True)

    session = relationship("ExamSession", back_populates="violations")
