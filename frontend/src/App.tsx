import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import AdminDashboard from './components/AdminDashboard';
import StudentPortal from './components/StudentPortal';
import { ShieldCheck, User } from 'lucide-react';

function Landing() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl w-full">
        <Link to="/student" className="surface-card flex flex-col items-center justify-center space-y-4 hover:border-primary transition-colors group cursor-pointer h-64">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center group-hover:scale-110 transition-transform shadow-glow-primary">
            <User className="w-8 h-8 text-primary" />
          </div>
          <h2 className="text-2xl font-bold text-white">Student Portal</h2>
          <p className="text-gray-400 text-center px-4">Take your exam securely with AI proctoring.</p>
        </Link>
        <Link to="/admin" className="surface-card flex flex-col items-center justify-center space-y-4 hover:border-success transition-colors group cursor-pointer h-64">
          <div className="w-16 h-16 rounded-full bg-success/20 flex items-center justify-center group-hover:scale-110 transition-transform shadow-glow-success">
            <ShieldCheck className="w-8 h-8 text-success" />
          </div>
          <h2 className="text-2xl font-bold text-white">Admin Dashboard</h2>
          <p className="text-gray-400 text-center px-4">Monitor all active sessions in real-time.</p>
        </Link>
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/student" element={<StudentPortal />} />
        <Route path="/admin" element={<AdminDashboard />} />
      </Routes>
    </Router>
  );
}

export default App;
