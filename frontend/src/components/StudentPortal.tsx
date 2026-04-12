import { useState, useRef, useEffect, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Camera, Mic, AppWindow, ShieldAlert } from 'lucide-react';

const API_URL = `http://${window.location.hostname}:8000`;
const WS_URL = `ws://${window.location.hostname}:8000`;

export default function StudentPortal() {
  const [step, setStep] = useState<'LOGIN' | 'EXAM'>('LOGIN');
  const [name, setName] = useState('');
  const [studentId, setStudentId] = useState('');
  const [sessionId, setSessionId] = useState<number | null>(null);
  
  const [tabSwitched, setTabSwitched] = useState(false);
  const [serverAlert, setServerAlert] = useState<string | null>(null);
  
  const webcamRef = useRef<Webcam>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Helper handling tab switches (anti-spoofing)
  useEffect(() => {
    if (step !== 'EXAM') return;
    const reportSwitch = (event_type: string) => {
      console.log(`[Alert] Tab Event: ${event_type}`);
      // Use REST for critical tab events to bypass WebSocket background throttling
      if (sessionId) {
        fetch(`${API_URL}/log_violation_rest/${sessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ detail: event_type }),
          keepalive: true // Crucial: ensures request finishes even if tab is being backgrounded/closed
        }).catch(err => console.error("REST Alert Failed:", err));
      }
    };

    const handleVisibility = () => {
      const state = document.visibilityState;
      reportSwitch(`Visibility Changed: ${state}`);
      if (document.hidden) setTabSwitched(true);
    };
    const handleBlur = () => {
      reportSwitch("Window Blurred (Switched Away)");
      setTabSwitched(true);
    };
    const handleFocus = () => {
      reportSwitch("Window Focused (Returned)");
    };

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("focus", handleFocus);
    
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("focus", handleFocus);
    };
  }, [step]);

  const handleEnroll = async () => {
    if (!name || !studentId) return alert('Fill all fields');
    
    // Attempt to take an enrollment snapshot
    const imageSrc = webcamRef.current?.getScreenshot();
    
    try {
      // 1. Create/Get User
      const userRes = await fetch(`${API_URL}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, student_id: studentId, enrollment_image: imageSrc })
      });
      
      let user = null;
      if (!userRes.ok) {
        // If already exists, fetch the user (simplification for MVP)
        const fetchUsers = await fetch(`${API_URL}/users`);
        const users = await fetchUsers.json();
        user = users.find((u: any) => u.student_id === studentId);
        if (!user) throw new Error("Could not log in");
      } else {
        user = await userRes.json();
      }

      // 2. Create Session
      const sessionRes = await fetch(`${API_URL}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: user.id })
      });
      const session = await sessionRes.json();
      setSessionId(session.id);
      setStep('EXAM');
    } catch (err: any) {
      alert("Error: " + err.message);
    }
  };

  const captureFrame = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const imageSrc = webcamRef.current?.getScreenshot();
      if (imageSrc) {
        wsRef.current.send(JSON.stringify({ frame: imageSrc }));
      }
    }
  }, []);

  // Helper for Audio monitoring
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioFramesAcc = useRef<number>(0);

  useEffect(() => {
    if (step === 'EXAM' && sessionId) {
      const socket = new WebSocket(`${WS_URL}/ws/exam/${sessionId}`);
      socket.onopen = () => console.log("WebSocket connected.");
      socket.onerror = (e) => console.error("WebSocket error:", e);
      wsRef.current = socket;
      
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.alert) {
          setServerAlert(data.alert);
          setTimeout(() => setServerAlert(null), 3000);
        }
      };
      
      const interval = setInterval(captureFrame, 1000); // 1 FPS

      let audioMonitoringActive = true;
      const initAudio = async () => {
         try {
             const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
             const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
             const source = audioContext.createMediaStreamSource(stream);
             
             // Using ScriptProcessor for real-time PCM extraction (compatible with offline STT)
             const processor = audioContext.createScriptProcessor(4096, 1, 1);
             
             source.connect(processor);
             processor.connect(audioContext.destination);
             
             processor.onaudioprocess = (e) => {
                 if (!audioMonitoringActive) return;
                 const inputData = e.inputBuffer.getChannelData(0);
                 
                 // Convert Float32 to Int16
                 const pcmData = new Int16Array(inputData.length);
                 for (let i = 0; i < inputData.length; i++) {
                     pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                 }
                 
                 if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                     wsRef.current.send(pcmData.buffer);
                 }
             };
             
             audioContextRef.current = audioContext;
         } catch(e) {
             console.error("Microphone access denied or error:", e);
         }
      };
      initAudio();

      return () => {
        audioMonitoringActive = false;
        clearInterval(interval);
        if (wsRef.current) wsRef.current.close();
        if (audioContextRef.current) audioContextRef.current.close();
      };
    }
  }, [step, sessionId, captureFrame]);

  if (step === 'LOGIN') {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
        <div className="surface-card w-full max-w-md shadow-glow-primary flex flex-col space-y-6">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-white mb-2">Student Pre-Check</h2>
            <p className="text-sm text-gray-400">Position your face in the camera to enroll.</p>
          </div>
          
          <div className="rounded-lg overflow-hidden bg-black object-cover relative">
             <Webcam
                ref={webcamRef}
                audio={false}
                screenshotFormat="image/jpeg"
                className="w-full h-auto"
                videoConstraints={{ facingMode: "user" }}
             />
             <div className="absolute inset-0 border-2 border-primary/50 pointer-events-none rounded-lg"></div>
          </div>

          <div className="space-y-4">
            <input 
              type="text" placeholder="Full Name" 
              className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white focus:outline-none focus:border-primary"
              value={name} onChange={e => setName(e.target.value)}
            />
            <input 
              type="text" placeholder="Student ID" 
              className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white focus:outline-none focus:border-primary"
              value={studentId} onChange={e => setStudentId(e.target.value)}
            />
            <button 
              onClick={handleEnroll}
              className="w-full py-2 bg-primary hover:bg-blue-600 text-white font-bold rounded transition-colors"
            >
              Start Secure Exam
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="surface-card w-full max-w-4xl grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Main Exam Area */}
        <div className="col-span-2 flex flex-col space-y-4 shadow-[0_0_15px_rgba(59,130,246,0.1)] p-4 rounded-xl">
           <h2 className="text-xl font-bold text-white">Active Exam Session</h2>
           <div className="prose prose-invert max-w-none text-gray-300">
              <p>Please read the following text carefully. Do not look away from the screen.</p>
              <br/>
              <h3>Q1: Explain the mechanisms of backpropagation in Deep Learning.</h3>
              <textarea className="w-full bg-gray-900 border border-gray-700 rounded p-4 h-64 text-white focus:outline-none" placeholder="Type your answer here..."></textarea>
           </div>
        </div>

        {/* Status Area */}
        <div className="flex flex-col space-y-4">
           <div className="rounded-lg overflow-hidden relative shadow-glow-primary">
              <Webcam
                ref={webcamRef}
                audio={false}
                screenshotFormat="image/jpeg"
                className="w-full h-auto"
                videoConstraints={{ facingMode: "user" }}
              />
              <div className="absolute top-2 left-2 bg-red-600 animate-pulse text-xs font-bold px-2 py-1 rounded text-white flex items-center space-x-1">
                 <Camera size={12} />
                 <span>REC</span>
              </div>
           </div>

           <div className="surface-card !p-3 space-y-3">
              <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">System Checks</h3>
              <div className="flex items-center justify-between text-sm">
                 <div className="flex items-center space-x-2 text-gray-300">
                    <Mic size={16} /> <span>Audio Monitoring</span>
                 </div>
                 {serverAlert?.includes('Talking') ? <span className="text-red-500 font-bold flex items-center"><ShieldAlert size={14}/> Talking</span> : <span className="text-success font-bold">Clear</span>}
              </div>
              <div className="flex items-center justify-between text-sm">
                 <div className="flex items-center space-x-2 text-gray-300">
                    <AppWindow size={16} /> <span>Tab Tracking</span>
                 </div>
                 {tabSwitched ? <span className="text-red-500 font-bold flex items-center"><ShieldAlert size={14}/> Switched</span> : <span className="text-success font-bold">Clear</span>}
              </div>
              <div className="flex items-center justify-between text-sm">
                 <div className="flex items-center space-x-2 text-gray-300">
                    <Camera size={16} /> <span>Gaze Tracking</span>
                 </div>
                 <span className="text-success font-bold">Active</span>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
}
