import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import Layout from './components/Layout';
import StartPage from './pages/StartPage';
import LiveMonitoring from './pages/LiveMonitoring';
import AlertHistory from './pages/AlertHistory';
import HowItWorks from './pages/HowItWorks';
import Results from './pages/Results';
import Settings from './pages/Settings';

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<StartPage />} />
            <Route path="start" element={<StartPage />} />
            <Route path="start-page" element={<StartPage />} />
            
            <Route path="live" element={<LiveMonitoring />} />
            <Route path="live-monitoring" element={<LiveMonitoring />} />
            
            <Route path="alerts" element={<AlertHistory />} />
            <Route path="alert-history" element={<AlertHistory />} />
            
            <Route path="how-it-works" element={<HowItWorks />} />
            <Route path="hiw" element={<HowItWorks />} />
            
            <Route path="results" element={<Results />} />
            <Route path="result" element={<Results />} />
            
            <Route path="settings" element={<Settings />} />
            
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}

