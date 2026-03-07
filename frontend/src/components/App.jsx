/**
 * App.jsx - Main application component with routing
 */

import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from '../hooks/useAuth.jsx';
import AdminDashboard from './AdminDashboard.jsx';
import AuthScreen from './AuthScreen.jsx';
import Dashboard from './Dashboard.jsx';
import Editor from './Editor.jsx';
import FlightRecorder from './FlightRecorder.jsx';
import DemoPatterns from './DemoPatterns.jsx';
import Playground from './Playground.jsx';

function AuthenticatedRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    return <AuthScreen />;
  }

  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/a/:aideId" element={<Editor />} />
      <Route path="/flight-recorder" element={<FlightRecorder />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function AppRoutes() {
  const location = useLocation();

  // Public routes (no auth required)
  if (location.pathname.startsWith('/demo')) {
    return <DemoPatterns />;
  }
  if (location.pathname.startsWith('/playground')) {
    return <Playground />;
  }

  return <AuthenticatedRoutes />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
