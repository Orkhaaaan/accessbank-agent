import { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import OperatorDashboard from './components/OperatorDashboard';

const API_BASE = import.meta.env.VITE_API_URL || '';

export default function App() {
  const [view, setView] = useState('chat');

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="logo">AB</span>
          <div>
            <h1>AccessBank AI Support</h1>
            <p>Müştəri dəstəyi agenti</p>
          </div>
        </div>
        <nav>
          <button
            type="button"
            className={view === 'chat' ? 'active' : ''}
            onClick={() => setView('chat')}
          >
            Söhbət
          </button>
          <button
            type="button"
            className={view === 'dashboard' ? 'active' : ''}
            onClick={() => setView('dashboard')}
          >
            Operator paneli
          </button>
        </nav>
      </header>
      <main>
        {view === 'chat' ? (
          <ChatInterface apiBase={API_BASE} />
        ) : (
          <OperatorDashboard apiBase={API_BASE} />
        )}
      </main>
      <style>{`
        .app { min-height: 100vh; display: flex; flex-direction: column; }
        .app-header {
          background: var(--ab-dark);
          color: white;
          padding: 1rem 2rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .brand { display: flex; gap: 1rem; align-items: center; }
        .logo {
          background: var(--ab-orange);
          width: 48px; height: 48px;
          border-radius: 12px;
          display: flex; align-items: center; justify-content: center;
          font-weight: 700; font-size: 1.1rem;
        }
        .brand h1 { font-size: 1.25rem; font-weight: 600; }
        .brand p { font-size: 0.85rem; opacity: 0.7; }
        nav { display: flex; gap: 0.5rem; }
        nav button {
          background: transparent;
          border: 1px solid rgba(255,255,255,0.3);
          color: white;
          padding: 0.5rem 1rem;
          border-radius: 8px;
        }
        nav button.active { background: var(--ab-orange); border-color: var(--ab-orange); }
        main { flex: 1; padding: 1.5rem 2rem; max-width: 1400px; margin: 0 auto; width: 100%; }
      `}</style>
    </div>
  );
}
