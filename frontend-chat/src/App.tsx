import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { getAuthSession } from './api/client';
import ChatWindowPage from './pages/ChatWindowPage';
import LoginPage from './pages/LoginPage';
import SessionListPage from './pages/SessionListPage';

function RequireAuth({ children }: { children: JSX.Element }) {
  return getAuthSession() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/chat" element={<RequireAuth><SessionListPage /></RequireAuth>} />
        <Route path="/chat/:sessionId" element={<RequireAuth><ChatWindowPage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
