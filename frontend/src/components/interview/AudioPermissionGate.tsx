"use client";
import { ReactNode } from "react";

export function AudioPermissionGate({
  state,
  children,
}: {
  state: "idle" | "requesting" | "active" | "error" | "denied";
  children: ReactNode;
}) {
  if (state === "idle") {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
        <div className="text-3xl mb-3 mx-auto w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center">
          🎤
        </div>
        <p className="text-sm text-gray-400">Microphone access required for voice mode</p>
      </div>
    );
  }

  if (state === "requesting") {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
        <div className="animate-pulse text-lg text-gray-400">Requesting microphone access...</div>
      </div>
    );
  }

  if (state === "denied") {
    return (
      <>
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 text-center mb-4">
          <p className="text-red-400 font-medium mb-1">Microphone access denied</p>
          <p className="text-sm text-red-500/70">Continuing in text-assisted mode so the interview can still run.</p>
        </div>
        {children}
      </>
    );
  }

  if (state === "error") {
    return (
      <>
        <div className="bg-yellow-900/20 border border-yellow-800 rounded-xl p-4 text-center mb-4">
          <p className="text-yellow-400 font-medium mb-1">Microphone error</p>
          <p className="text-sm text-yellow-500/70">Continuing in text-assisted mode so the interview can still run.</p>
        </div>
        {children}
      </>
    );
  }

  return <>{children}</>;
}
