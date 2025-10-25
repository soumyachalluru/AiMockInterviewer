import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "./Welcome.css"; // reuse the same styling

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");
    setLoading(true);

    try {
      const res = await axios.post("http://127.0.0.1:8000/auth/forgot-password", {
        email,
      });
      setMessage(res.data.message);
    } catch (err) {
      if (err.response) setError(err.response.data.detail);
      else setError("Something went wrong. Try again later.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="welcome-container">
      <div className="right-panel">
        <div className="login-card">
          <h2 className="login-title">Forgot Password?</h2>
          <p className="login-subtitle">
            Enter your email and we’ll send a password reset link
          </p>

          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            {message && <p style={{ color: "green" }}>{message}</p>}
            {error && <p style={{ color: "red" }}>{error}</p>}

            <button type="submit" className="login-btn" disabled={loading}>
              {loading ? "Sending..." : "Send Reset Link"}
            </button>

            <div className="signup-link">
              Remembered your password?{" "}
              <a onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
                Back to Login
              </a>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
