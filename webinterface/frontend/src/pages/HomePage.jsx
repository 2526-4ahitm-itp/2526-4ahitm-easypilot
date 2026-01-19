import React, { useState, useEffect, useRef } from 'react';

function HomePage() {
  const [status, setStatus] = useState("Bereit");
  const ws = useRef(null);

  // Verbindung beim Laden der Seite herstellen
  useEffect(() => {
    ws.current = new WebSocket('ws://localhost:8765');
    
    ws.current.onopen = () => setStatus("Verbunden mit Drohne");
    ws.current.onclose = () => setStatus("Verbindung getrennt");
    ws.current.onerror = () => setStatus("Fehler: Python-Skript läuft nicht?");

    return () => {
      if (ws.current) ws.current.close();
    };
  }, []);

  const handleStartMusic = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ command: "start_music" }));
      setStatus("Musik wird abgespielt...");
    } else {
      setStatus("Nicht verbunden!");
    }
  };

  return (
    <div style={{ padding: "40px", textAlign: "center", fontFamily: "sans-serif" }}>
      <h2>Drohnen-Steuerung</h2>
      <div style={{ 
          background: "#f4f4f4", 
          padding: "20px", 
          borderRadius: "10px", 
          display: "inline-block",
          boxShadow: "0 4px 6px rgba(0,0,0,0.1)"
      }}>
        <p>Status: <strong>{status}</strong></p>
        
        {/* Der normale Button */}
        <button 
          onClick={handleStartMusic}
          style={{
            padding: "15px 30px",
            fontSize: "18px",
            backgroundColor: "#0078d4",
            color: "white",
            border: "none",
            borderRadius: "5px",
            cursor: "pointer",
            transition: "background 0.3s"
          }}
          onMouseOver={(e) => e.target.style.backgroundColor = "#005a9e"}
          onMouseOut={(e) => e.target.style.backgroundColor = "#0078d4"}
        >
          Melodie auf Drohne starten
        </button>
      </div>
    </div>
  );
}

export default HomePage;