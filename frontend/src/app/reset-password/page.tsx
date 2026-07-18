"use client";
import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setStatus("error");
      setMessage("Passwords do not match.");
      return;
    }
    if (password.length < 12) {
      setStatus("error");
      setMessage("Password must be at least 12 characters.");
      return;
    }
    setStatus("loading");
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus("success");
        setMessage("Password reset successfully!");
      } else {
        setStatus("error");
        setMessage(data.detail || "Reset failed. The link may have expired.");
      }
    } catch {
      setStatus("error");
      setMessage("Network error. Please try again.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-slate-800/50 border border-slate-700 rounded-xl p-8">
        <h1 className="text-xl font-bold text-white mb-2">Reset Password</h1>
        {status === "success" ? (
          <div role="alert" className="bg-emerald-900/50 border border-emerald-700 rounded-lg p-4 text-emerald-200 text-sm">
            {message}
            <Link href="/login" className="block mt-3 text-indigo-400 hover:text-indigo-300">Go to login</Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {!token && <p className="text-amber-400 text-sm mb-4">No reset token provided. Please use the link from your email.</p>}
            <label htmlFor="new-password" className="block text-sm text-slate-300 mb-1">New Password</label>
            <input
              id="new-password"
              type="password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none mb-3"
            />
            <label htmlFor="confirm-password" className="block text-sm text-slate-300 mb-1">Confirm Password</label>
            <input
              id="confirm-password"
              type="password"
              required
              minLength={12}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none mb-4"
            />
            {status === "error" && <p role="alert" className="text-red-400 text-sm mb-4">{message}</p>}
            <button type="submit" disabled={status === "loading"} className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition">
              {status === "loading" ? "Resetting..." : "Reset Password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
