"use client";
import { useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sent" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("sent");
        setMessage("If an account exists with that email, a reset link has been generated.");
      } else {
        setStatus("error");
        setMessage(data.detail || "An error occurred.");
      }
    } catch {
      setStatus("error");
      setMessage("Network error. Please try again.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-slate-800/50 border border-slate-700 rounded-xl p-8">
        <h1 className="text-xl font-bold text-white mb-2">Forgot Password</h1>
        <p className="text-sm text-slate-400 mb-6">Enter your email to receive a password reset link.</p>
        {status === "sent" ? (
          <div role="alert" className="bg-emerald-900/50 border border-emerald-700 rounded-lg p-4 text-emerald-200 text-sm">
            {message}
            <Link href="/login" className="block mt-3 text-indigo-400 hover:text-indigo-300">Return to login</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label htmlFor="email" className="block text-sm text-slate-300 mb-1">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none mb-4"
              autoFocus
            />
            {status === "error" && <p role="alert" className="text-red-400 text-sm mb-4">{message}</p>}
            <button type="submit" className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition">
              Send Reset Link
            </button>
            <Link href="/login" className="block text-center text-sm text-slate-400 hover:text-indigo-400 mt-4">Back to login</Link>
          </form>
        )}
      </div>
    </div>
  );
}
