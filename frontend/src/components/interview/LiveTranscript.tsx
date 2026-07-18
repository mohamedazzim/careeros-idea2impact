"use client";

type LiveTranscriptProps = {
  partial: string;
  finalTranscript: string[];
  isAiSpeaking: boolean;
  isUserSpeaking: boolean;
  confidence?: number;
  connectionStatus?: "connected" | "reconnecting" | "disconnected";
};

export function LiveTranscript({
  partial,
  finalTranscript,
  isAiSpeaking,
  isUserSpeaking,
  confidence = 0,
  connectionStatus = "connected",
}: LiveTranscriptProps) {
  return (
    <div className="h-96 overflow-y-auto p-4 space-y-3">
      {finalTranscript.length === 0 && !partial && (
        <div className="text-center text-gray-500 mt-16">
          <div className="text-4xl mb-3">🎙️</div>
          <p className="text-sm">Start speaking — your transcript will appear here in real-time</p>
        </div>
      )}

      {finalTranscript.map((text, i) => (
        <div key={i} className="flex justify-start">
          <div className="max-w-[85%] px-4 py-2 rounded-xl text-sm bg-gray-800 text-gray-200">
            <p>{text}</p>
          </div>
        </div>
      ))}

      {partial && isUserSpeaking && (
        <div className="flex justify-end">
          <div className="max-w-[85%] px-4 py-2 rounded-xl text-sm bg-blue-600/50 text-white italic border border-blue-500/30">
            <p>{partial}</p>
            <div className="flex gap-1 mt-1">
              <div className="w-1 h-1 bg-blue-300 rounded-full animate-pulse" />
              <div className="w-1 h-1 bg-blue-300 rounded-full animate-pulse" style={{ animationDelay: "150ms" }} />
              <div className="w-1 h-1 bg-blue-300 rounded-full animate-pulse" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        </div>
      )}

      {isAiSpeaking && (
        <div className="flex items-center gap-2 px-4 py-1">
          <div className="flex gap-1">
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" style={{ animationDelay: "150ms" }} />
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" style={{ animationDelay: "300ms" }} />
          </div>
          <span className="text-xs text-gray-500">AI is responding...</span>
        </div>
      )}

      {confidence > 0 && (
        <div className="flex items-center gap-2 px-4 py-1 text-xs">
          <span className="text-gray-500">Transcript confidence:</span>
          <div className="flex-1 max-w-[100px] h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                confidence >= 0.8 ? "bg-emerald-500" : confidence >= 0.5 ? "bg-amber-500" : "bg-red-500"
              }`}
              style={{ width: `${(confidence * 100).toFixed(0)}%` }}
            />
          </div>
          <span className={`font-mono ${
            confidence >= 0.8 ? "text-emerald-400" : confidence >= 0.5 ? "text-amber-400" : "text-red-400"
          }`}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
      )}

      {connectionStatus !== "connected" && (
        <div className={`flex items-center gap-2 px-4 py-1 text-xs ${
          connectionStatus === "reconnecting" ? "text-amber-400" : "text-red-400"
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            connectionStatus === "reconnecting" ? "bg-amber-500 animate-pulse" : "bg-red-500"
          }`} />
          {connectionStatus === "reconnecting" ? "Reconnecting..." : "Connection lost"}
        </div>
      )}
    </div>
  );
}
