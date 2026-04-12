import { useState, useEffect, useRef } from 'react';
import { Shield, AlertTriangle, UserCheck, ShieldAlert, DownloadCloud, Activity } from 'lucide-react';
import { LineChart, Line, XAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

const WS_URL = `ws://${window.location.hostname}:8000`;
const API_URL = `http://${window.location.hostname}:8000`;

type Violation = {
  id: number;
  session_id: number;
  timestamp: string;
  violation_type: string;
  snapshot_url: string;
}

export default function AdminDashboard() {
  const wsRef = useRef<WebSocket | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [statsData, setStatsData] = useState<any[]>([]);
  const [activeView, setActiveView] = useState<'live' | 'students' | 'reports'>('live');
  const [usersList, setUsersList] = useState<any[]>([]);
  const [sessionsList, setSessionsList] = useState<any[]>([]);
  const [liveFeeds, setLiveFeeds] = useState<Record<string, { name: string, frame: string, lastSeen: number }>>({});

  useEffect(() => {
    // Initial fetch of violations
    fetch(`${API_URL}/violations`)
      .then(res => res.json())
      .then(data => {
        setViolations(data);
        updateStats(data);
      });
      
    // Fetch users for the Students tab
    fetch(`${API_URL}/users`)
      .then(res => res.json())
      .then(data => setUsersList(data));

    // Fetch sessions for the Reports tab
    fetch(`${API_URL}/sessions`)
      .then(res => res.json())
      .then(data => setSessionsList(data));

    // WebSocket connect for live alerts
    const socket = new WebSocket(`${WS_URL}/ws/admin`);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'violation') {
        const newAlert = {
           id: Date.now(),
           ...data,
           time: new Date().toLocaleTimeString()
        };
        setAlerts(prev => [newAlert, ...prev].slice(0, 50));
        
        // Also add to violations list
        const newViolation = {
          id: Date.now(),
          session_id: data.session_id,
          timestamp: new Date().toISOString(),
          violation_type: data.alerts.join(', '),
          snapshot_url: data.snapshot_url
        };
        setViolations(prev => {
          const newViolations = [newViolation, ...prev];
          updateStats(newViolations);
          return newViolations;
        });
      }

      if (data.type === 'live_frame') {
        setLiveFeeds(prev => ({
          ...prev,
          [data.student_id]: {
            name: data.student_name,
            frame: data.frame,
            lastSeen: Date.now()
          }
        }));
      }
    };
    wsRef.current = socket;

    // Cleanup stale feeds every 5 seconds
    const cleanupInterval = setInterval(() => {
      setLiveFeeds(prev => {
        const now = Date.now();
        const updated = { ...prev };
        let changed = false;
        Object.keys(updated).forEach(id => {
          if (now - updated[id].lastSeen > 10000) { // 10s timeout
            delete updated[id];
            changed = true;
          }
        });
        return changed ? updated : prev;
      });
    }, 5000);

    return () => {
      socket.close();
      clearInterval(cleanupInterval);
    };
  }, []);

  const updateStats = (vList: Violation[]) => {
    // Simple grouping by hour for the chart
    const grouped: Record<string, number> = {};
    vList.forEach(v => {
      const d = new Date(v.timestamp);
      const label = `${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
      grouped[label] = (grouped[label] || 0) + 1;
    });
    const latestKeys = Object.keys(grouped).sort().slice(-10);
    const data = latestKeys.map(k => ({ time: k, violations: grouped[k] }));
    setStatsData(data);
  };

  return (
    <div className="min-h-screen bg-background text-gray-200 flex">
      {/* Sidebar */}
      <div className="w-64 bg-surface border-r border-gray-800 p-4 flex flex-col">
        <div className="flex items-center space-x-3 mb-8">
          <Shield className="w-8 h-8 text-success" />
          <h1 className="text-xl font-bold text-white tracking-widest uppercase">Overwatch</h1>
        </div>
        <nav className="space-y-4 flex-1">
          <button onClick={() => setActiveView('live')} className={`w-full text-left flex items-center space-x-3 px-3 py-2 rounded font-medium transition-colors ${activeView === 'live' ? 'bg-gray-800 text-white border border-gray-700' : 'hover:bg-gray-800/50 text-gray-400'}`}>
            <Activity size={18} /> <span>Live Monitor</span>
          </button>
          <button onClick={() => setActiveView('students')} className={`w-full text-left flex items-center space-x-3 px-3 py-2 rounded font-medium transition-colors ${activeView === 'students' ? 'bg-gray-800 text-white border border-gray-700' : 'hover:bg-gray-800/50 text-gray-400'}`}>
            <UserCheck size={18} /> <span>Students</span>
          </button>
          <button onClick={() => setActiveView('reports')} className={`w-full text-left flex items-center space-x-3 px-3 py-2 rounded font-medium transition-colors ${activeView === 'reports' ? 'bg-gray-800 text-white border border-gray-700' : 'hover:bg-gray-800/50 text-gray-400'}`}>
            <DownloadCloud size={18} /> <span>Reports</span>
          </button>
        </nav>
        <div className="mt-auto">
          <div className="text-xs text-gray-500 uppercase tracking-widest mb-2 font-bold">System Status</div>
          <div className="flex items-center space-x-2 text-success text-sm font-mono">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
            <span>All nodes secure</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto">
        {/* --- VIEW ROUTER --- */}
        {activeView === 'live' && (
          <>
            <header className="flex justify-between items-end">
              <div>
                <h2 className="text-2xl font-bold text-white mb-1">Live Command Center</h2>
                <p className="text-gray-400 text-sm">Monitoring active sessions</p>
              </div>
            </header>

            {/* Analytics Top Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="surface-card flex flex-col justify-center">
                <div className="text-gray-400 text-sm font-bold uppercase mb-1">Total Infractions (24h)</div>
                <div className="text-3xl font-bold text-white">{violations.length}</div>
              </div>
              <div className="surface-card col-span-2 h-32 flex flex-col p-4 shadow-glow-primary">
                <div className="text-gray-400 text-xs font-bold uppercase mb-2">Activity Timeline</div>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={statsData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false}/>
                    <XAxis dataKey="time" stroke="#666" fontSize={10} tickLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#121212', border: '1px solid #333' }} />
                    <Line type="monotone" dataKey="violations" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3, fill: '#3b82f6' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
              {/* Main Grid View */}
              <div className="lg:col-span-2 surface-card flex flex-col">
                <div className="flex justify-between items-center mb-4">
                   <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest">Live Student Grid</h3>
                   <span className="text-[10px] text-gray-500 font-mono italic">Showing {Object.keys(liveFeeds).length} active feeds</span>
                </div>
                
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 flex-1 overflow-y-auto">
                  {Object.keys(liveFeeds).length === 0 ? (
                    <div className="col-span-full flex flex-col items-center justify-center p-12 text-gray-600 border-2 border-dashed border-gray-800 rounded-xl">
                       <Activity className="w-12 h-12 mb-2 opacity-20" />
                       <p className="font-mono text-xs uppercase tracking-tighter">Waiting for live streams...</p>
                    </div>
                  ) : (
                    Object.entries(liveFeeds).map(([id, feed]) => (
                      <div key={id} className="bg-black border border-gray-800 rounded-lg aspect-video relative overflow-hidden group shadow-lg">
                        <img 
                          src={feed.frame.includes(',') ? feed.frame : `data:image/jpeg;base64,${feed.frame}`} 
                          className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity" 
                          alt={feed.name} 
                        />
                        <div className="absolute top-2 left-2 flex items-center space-x-1 text-[10px] text-green-500 bg-black/70 px-2 py-1 rounded font-mono border border-green-900/50">
                          <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></div>
                          <span className="max-w-[80px] truncate">{feed.name}</span>
                        </div>
                        <div className="absolute bottom-2 right-2 text-[8px] text-gray-500 bg-black/50 px-1 rounded">
                           LIVE
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Live Alert Feed */}
              <div className="surface-card flex flex-col relative overflow-hidden shadow-glow-danger border-red-900/50">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-red-600 to-red-400"></div>
                <div className="flex items-center space-x-2 mb-4 mt-2">
                  <ShieldAlert className="text-red-500 w-5 h-5 animate-pulse" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-widest">Real-Time Alerts</h3>
                </div>
                
                <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                  {alerts.length === 0 ? (
                    <div className="text-center text-gray-500 py-8 text-sm italic">No recent infractions.</div>
                  ) : (
                    alerts.map(a => (
                      <div key={a.id} className="bg-red-950/30 border border-red-900/50 p-3 rounded flex flex-col space-y-2">
                        <div className="flex justify-between items-start">
                          <div>
                            <div className="flex justify-between w-full">
                              <span className="text-white font-bold text-sm">{a.student_name}</span>
                              <span className="text-red-400 text-xs font-mono">{a.time}</span>
                            </div>
                            <div className="text-red-300/80 text-xs font-medium uppercase tracking-wider mt-1 flex space-x-1">
                               <AlertTriangle size={12} className="inline flex-shrink-0" /> <span>{a.alerts.join(', ')}</span>
                            </div>
                          </div>
                        </div>
                        {/* Snapshots */}
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <div className="h-16 bg-black rounded border border-red-900/30 overflow-hidden relative">
                             {a.snapshot_url && <img src={`${API_URL}${a.snapshot_url}`} className="w-full h-full object-cover" alt="violation" />}
                          </div>
                        </div>
                        {/* Trust Score */}
                        <div className="mt-2">
                          <div className="flex justify-between text-[10px] text-gray-400 mb-1 font-bold uppercase">
                            <span>Trust Score</span>
                            <span className={a.new_trust_score < 70 ? 'text-red-400' : 'text-warning'}>{a.new_trust_score.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-red-500 h-1.5 transition-all duration-500" style={{width: `${a.new_trust_score}%`}}></div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {activeView === 'students' && (
          <div className="flex-1 surface-card flex flex-col p-6 overflow-hidden">
            <h2 className="text-2xl font-bold text-white mb-6">Database: Enrolled Students</h2>
            <div className="overflow-y-auto flex-1">
               <table className="w-full text-left border-collapse">
                  <thead>
                     <tr className="border-b border-gray-800 text-gray-400 text-sm">
                        <th className="py-3 px-4 font-bold uppercase tracking-wider">System ID</th>
                        <th className="py-3 px-4 font-bold uppercase tracking-wider">Student Name</th>
                        <th className="py-3 px-4 font-bold uppercase tracking-wider">Face Encode Hash</th>
                     </tr>
                  </thead>
                  <tbody>
                     {usersList.length === 0 ? (
                        <tr><td colSpan={3} className="py-8 text-center text-gray-500">No students enrolled yet.</td></tr>
                     ) : (
                        usersList.map(u => (
                           <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
                              <td className="py-4 px-4 font-mono text-primary text-sm">{u.student_id}</td>
                              <td className="py-4 px-4 text-white font-medium">{u.name}</td>
                              <td className="py-4 px-4 text-success text-xs tracking-widest uppercase font-bold flex items-center space-x-2">
                                <Shield className="w-4 h-4" /> <span>Authenticated</span>
                              </td>
                           </tr>
                        ))
                     )}
                  </tbody>
               </table>
            </div>
          </div>
        )}

        {activeView === 'reports' && (
          <div className="flex-1 surface-card flex flex-col p-6 overflow-hidden">
             <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white">Security Audit: Session Reports</h2>
                <button 
                   onClick={() => fetch(`${API_URL}/sessions`).then(res => res.json()).then(setSessionsList)}
                   className="text-xs bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded border border-gray-700 transition-colors"
                >
                   Refresh List
                </button>
             </div>

             <div className="overflow-y-auto flex-1">
                <table className="w-full text-left border-collapse">
                   <thead>
                      <tr className="border-b border-gray-800 text-gray-400 text-sm">
                         <th className="py-3 px-4 font-bold uppercase tracking-wider">Start Time</th>
                         <th className="py-3 px-4 font-bold uppercase tracking-wider">Student</th>
                         <th className="py-3 px-4 font-bold uppercase tracking-wider">violations</th>
                         <th className="py-3 px-4 font-bold uppercase tracking-wider text-right">Action</th>
                      </tr>
                   </thead>
                   <tbody>
                      {sessionsList.length === 0 ? (
                         <tr><td colSpan={4} className="py-8 text-center text-gray-500">No sessions recorded yet. Start an exam to see reports.</td></tr>
                      ) : (
                         sessionsList.map(s => (
                            <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
                               <td className="py-4 px-4 text-gray-300 font-mono text-xs">{new Date(s.start_time).toLocaleString()}</td>
                               <td className="py-4 px-4 text-white">
                                  <div className="font-bold">{s.student_name}</div>
                                  <div className="text-[10px] text-gray-500 font-mono">{s.student_id}</div>
                               </td>
                               <td className="py-4 px-4">
                                  <span className={`text-xs px-2 py-1 rounded-full font-bold ${s.violation_count > 0 ? 'bg-red-950 text-red-500 border border-red-900/50' : 'bg-green-950 text-success border border-green-900/50'}`}>
                                    {s.violation_count} Infractions
                                  </span>
                               </td>
                               <td className="py-4 px-4 text-right">
                                  <button 
                                     onClick={() => window.open(`${API_URL}/generate_pdf_report/${s.id}`)}
                                     className="bg-primary/20 hover:bg-primary/40 text-primary border border-primary/30 px-4 py-2 rounded-lg text-sm font-bold transition-all flex items-center space-x-2 ml-auto"
                                  >
                                     <DownloadCloud size={14} /> <span>Download Audit</span>
                                  </button>
                               </td>
                            </tr>
                         ))
                      )}
                   </tbody>
                </table>
             </div>
          </div>
        )}

      </div>
    </div>
  );
}
