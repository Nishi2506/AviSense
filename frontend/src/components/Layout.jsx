import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';

export default function Layout() {
  return (
    <div className="bg-surface-container-lowest min-h-screen text-on-surface">
      <Sidebar />
      <div className="pl-80">
        <Header />
        <main className="relative pt-14 w-full min-h-screen bg-surface-container-lowest px-gutter-desktop py-space-lg">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

