import "./App.css";
import Navbar from "./components/Navbar";
import { BrowserRouter, Routes, Route } from "react-router-dom";

function SimulatorPage() {
    return <h1>Simulator</h1>;
}

function DocsPage() {
    return <h1>Dokumentation</h1>;
}

function App() {
    return (
        <BrowserRouter>
            <Navbar />
            <Routes>
                <Route path="/simulator" element={<SimulatorPage />} />
                <Route path="/docs" element={<DocsPage />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;
