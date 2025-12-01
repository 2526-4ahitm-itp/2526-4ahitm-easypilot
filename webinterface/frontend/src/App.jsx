import React from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import HomePage from './pages/HomePage';
import ModelPage from './pages/ModelPage';

function App() {
  return (
    <div className="App">
      <nav className="main-nav">
        <Link to="/">Home</Link>
        <Link to="/model">3D Modell</Link>
      </nav>

      <div className="content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/model" element={<ModelPage />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;