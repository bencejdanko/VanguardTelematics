import { useEffect, useState } from 'react';

const API = 'http://localhost:8000';

interface Incident {
  id: number;
  timestamp: string;
  event_name: string;
  report: string;
}

export function IncidentPanel() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [hasShown, setHasShown] = useState(false);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API}/incidents?limit=5`);
        if (res.ok) {
          const data = await res.json();
          setIncidents(data);
          if (data.length > 0) setHasShown(true);
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  if (!hasShown) return null;

  return (
    <div style={{
      width: '340px',
      minWidth: '340px',
      height: '100vh',
      overflowY: 'auto',
      background: '#0d0d1a',
      borderLeft: '1px solid #2a2a3e',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #2a2a3e',
        fontFamily: 'monospace',
        fontWeight: 'bold',
        fontSize: '14px',
        color: '#e53e3e',
        letterSpacing: '0.05em',
      }}>
        INCIDENT REPORTS
      </div>

      {incidents.length === 0 ? (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#555',
          fontFamily: 'monospace',
          fontSize: '13px',
        }}>
          No incidents — system nominal
        </div>
      ) : (
        <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {incidents.map((inc) => (
            <div
              key={inc.id}
              style={{
                background: '#13091a',
                border: '1px solid #e53e3e',
                borderRadius: '6px',
                padding: '12px',
              }}
            >
              <div style={{
                fontWeight: 'bold',
                color: '#e53e3e',
                fontFamily: 'monospace',
                fontSize: '12px',
                letterSpacing: '0.05em',
              }}>
                {inc.event_name.toUpperCase()}
              </div>
              <div style={{
                color: '#666',
                fontSize: '11px',
                fontFamily: 'monospace',
                marginBottom: '8px',
              }}>
                {new Date(inc.timestamp).toLocaleString()}
              </div>
              <pre style={{
                whiteSpace: 'pre-wrap',
                color: '#ccc',
                fontSize: '12px',
                fontFamily: 'monospace',
                margin: 0,
                lineHeight: '1.5',
              }}>
                {inc.report}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
