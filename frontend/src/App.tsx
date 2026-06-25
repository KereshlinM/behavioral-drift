import { useState } from "react";
import Overview from "./pages/Overview";
import Users from "./pages/Users";
import Webhooks from "./pages/Webhooks";

type Page = "overview" | "users" | "webhooks";

const NAV: { id: Page; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "users", label: "Users" },
  { id: "webhooks", label: "Webhooks" },
];

function ApiKeyModal({ onSave }: { onSave: (key: string) => void }) {
  const [key, setKey] = useState("");
  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 600 }}>Behavioral Drift</h2>
        <p className="muted" style={{ margin: "0 0 20px", fontSize: 14 }}>
          Enter your API key to access the dashboard.
        </p>
        <input
          className="form-input"
          placeholder="dk_..."
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && key.trim() && onSave(key.trim())}
          autoFocus
        />
        <button
          className="btn btn-primary"
          style={{ marginTop: 12, width: "100%" }}
          onClick={() => key.trim() && onSave(key.trim())}
          disabled={!key.trim()}
        >
          Continue
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(() => localStorage.getItem("drift_api_key"));
  const [page, setPage] = useState<Page>("overview");

  if (!apiKey) {
    return (
      <ApiKeyModal
        onSave={(key) => {
          localStorage.setItem("drift_api_key", key);
          setApiKey(key);
          window.location.reload();
        }}
      />
    );
  }

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">◎</span>
          <span className="logo-text">drift</span>
        </div>
        <div className="sidebar-nav">
          {NAV.map(({ id, label }) => (
            <button
              key={id}
              className={`nav-item ${page === id ? "active" : ""}`}
              onClick={() => setPage(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="sidebar-footer">
          <button
            className="nav-item"
            onClick={() => {
              localStorage.removeItem("drift_api_key");
              window.location.reload();
            }}
          >
            Sign out
          </button>
        </div>
      </nav>
      <main className="main-content">
        {page === "overview" && <Overview />}
        {page === "users" && <Users />}
        {page === "webhooks" && <Webhooks />}
      </main>
    </div>
  );
}
