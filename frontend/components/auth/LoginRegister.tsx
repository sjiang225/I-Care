"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { login, register, type AuthUser } from "@/lib/auth";
import BrandMark from "@/components/BrandMark";

export default function LoginRegister({
  onSuccess,
  onClose,
}: {
  onSuccess: (user: AuthUser) => void;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const user =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, name);
      onSuccess(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-overlay" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>
        <div className="auth-head">
          <BrandMark size={48} />
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p>Save your conversations and track how you&apos;re feeling over time.</p>
        </div>

        <form onSubmit={submit} className="auth-form">
          {mode === "register" && (
            <input
              className="auth-input"
              placeholder="Your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
          <input
            className="auth-input"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="auth-input"
            type="password"
            placeholder="Password (min 6 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <div className="auth-error">{error}</div>}
          <button className="auth-submit" disabled={busy}>
            {busy
              ? "Please wait…"
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login" ? (
            <>
              New here?{" "}
              <button onClick={() => setMode("register")}>Create an account</button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button onClick={() => setMode("login")}>Sign in</button>
            </>
          )}
        </div>

        <p className="auth-note">
          A prototype account. Please don&apos;t reuse a sensitive password.
        </p>
      </div>
    </div>
  );
}
