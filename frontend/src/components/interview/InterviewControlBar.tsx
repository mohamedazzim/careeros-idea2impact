"use client";

type InterviewControlBarProps = {
  micState: "idle" | "requesting" | "active" | "error" | "denied";
  isSpeaking: boolean;
  audioLevel: number;
  onRequestMic: () => void;
  onStopMic: () => void;
  onToggleMute: () => void;
};

export function InterviewControlBar({
  micState,
  isSpeaking,
  onRequestMic,
  onStopMic,
  onToggleMute,
}: InterviewControlBarProps) {
  const micActive = micState === "active";

  return (
    <div className="flex items-center justify-center gap-4 p-4 border-t border-gray-800">
      <button
        onClick={micActive ? onStopMic : onRequestMic}
        className={`w-12 h-12 rounded-full flex items-center justify-center transition-all text-lg ${
          micActive
            ? "bg-red-600 hover:bg-red-500 text-white"
            : "bg-blue-600 hover:bg-blue-500 text-white"
        }`}
        title={micActive ? "Stop microphone" : "Start microphone"}
      >
        {micActive ? "⏹" : "🎤"}
      </button>

      {micActive && (
        <button
          onClick={onToggleMute}
          className="w-10 h-10 rounded-full bg-gray-800 hover:bg-gray-700 flex items-center justify-center text-sm transition-all"
          title="Toggle mute"
        >
          🔇
        </button>
      )}

      <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs ${
        micActive
          ? isSpeaking
            ? "bg-blue-900/50 text-blue-300"
            : "bg-gray-800 text-gray-400"
          : "bg-gray-800/50 text-gray-600"
      }`}>
        <div className={`w-2 h-2 rounded-full ${
          micActive ? (isSpeaking ? "bg-blue-400 animate-pulse" : "bg-green-500") : "bg-gray-600"
        }`} />
        {micActive ? (isSpeaking ? "Speaking" : "Listening") : "Mic off"}
      </div>
    </div>
  );
}
