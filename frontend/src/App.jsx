import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Welcome from './pages/Welcome';
import SelectRole from './pages/SelectRole';
import Interview from './pages/Interview';
import Signup from "./pages/Signup";
import ForgotPassword from "./pages/ForgotPassword";



function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/select-role" element={<SelectRole />} />
        <Route path="/interview" element={<Interview />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
      </Routes>
    </Router>
  );
}

export default App;
