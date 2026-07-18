"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { useInterviewWebSocket } from "@/hooks/useWebSocket";
import { useMicrophone, AudioChunk } from "@/hooks/useMicrophone";
import { useVoiceActivityDetection } from "@/hooks/useVoiceActivityDetection";
import { VoiceVisualizer } from "@/components/interview/VoiceVisualizer";
import { AudioPermissionGate } from "@/components/interview/AudioPermissionGate";
import { LiveTranscript } from "@/components/interview/LiveTranscript";
import { InterviewControlBar } from "@/components/interview/InterviewControlBar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type TranscriptEntry = { speaker: "ai" | "user" | "system"; text: string; timestamp: number };
type EvalEntry = { overall_score: number; strengths: string[]; improvements: string[] };

const INTERVIEW_MODES = [
  { key: "technical", label: "Technical", icon: "⚙️" },
  { key: "behavioral", label: "Behavioral", icon: "🗣️" },
  { key: "system_design", label: "System Design", icon: "🏗️" },
  { key: "coding", label: "Coding", icon: "💻" },
  { key: "hr", label: "HR Screen", icon: "📋" },
  { key: "faang", label: "FAANG Sim", icon: "🏢" },
];

export default function LiveInterviewPage() {
  const [phase, setPhase] = useState<"setup" | "live" | "results">("setup");
  const [interviewType, setInterviewType] = useState("technical");
  const [userId, setUserId] = useState("candidate_1");
  const [sessionUid, setSessionUid] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [questionIndex, setQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [draftResponse, setDraftResponse] = useState("");
  const [evaluations, setEvaluations] = useState<EvalEntry[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [scores, setScores] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [lastLatency, setLastLatency] = useState<number | null>(null);

  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const chunkBufferRef = useRef<AudioChunk[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setInterval>>();

  const onWSEvent = useCallback((event: { event: string; data: Record<string, unknown> }) => {
    const t = event.event;
    const d = event.data;
    switch (t) {
      case "question_delivered":
        setCurrentQuestion(d.question as string);
        setQuestionIndex((d.index as number) || 1);
        setTotalQuestions(d.total as number);
        setAiSpeaking(true);
        break;
      case "ai_speaking":
        setAiSpeaking(true);
        setIsProcessing(false);
        break;
      case "ai_thinking":
        setIsProcessing(true);
        setAiSpeaking(false);
        break;
      case "ai_stopped_speaking":
        setAiSpeaking(false);
        break;
      case "interview_completed":
        setPhase("results");
        break;
      case "tts_chunk":
        setLastLatency((d.latency_ms as number) || null);
        break;
    }
  }, []);

  const { connected, send: wsSend } = useInterviewWebSocket(sessionUid, userId, interviewType, onWSEvent);

  const onAudioChunk = useCallback((chunk: AudioChunk) => {
    chunkBufferRef.current.push(chunk);
  }, []);

  const mic = useMicrophone({
    sampleRate: 16000,
    chunkDurationMs: 120,
    onChunk: onAudioChunk,
  });

  const vad = useVoiceActivityDetection({
    silenceTimeoutMs: 1500,
    activationThreshold: 0.15,
    onSpeechStart: () => {
      wsSend && wsSend("user_speech_start", { session_uid: sessionUid });
      if (aiSpeaking) {
        wsSend && wsSend("barge_in", { session_uid: sessionUid });
      }
    },
    onSpeechEnd: (durationMs: number) => {
      const chunks = chunkBufferRef.current.splice(0);
      if (chunks.length > 0 && sessionUid) {
        wsSend && wsSend("audio_chunks", {
          session_uid: sessionUid,
          chunk_count: chunks.length,
          duration_ms: durationMs,
        });
        setPartialTranscript("Processing...");
      }
    },
  });

  useEffect(() => {
    if (mic.audioLevel > 0) {
      vad.processAudioLevel(mic.audioLevel);
    }
  }, [mic.audioLevel, vad]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, partialTranscript]);

  const startInterview = async () => {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/interview/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, interview_type: interviewType, mode: "voice" }),
      });
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setSessionUid(data.session_uid);
      setCurrentQuestion(data.first_question || "");
      setQuestionIndex(1);
      setTotalQuestions(5);
      setPhase("live");
      setTranscript([{
        speaker: "system",
        text: `Voice interview started — ${interviewType} mode. Click the mic to begin.`,
        timestamp: Date.now(),
      }]);
      await mic.request();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const submitTextResponse = async (text: string) => {
    if (!text.trim() || !sessionUid) return;
    setIsProcessing(true);
    setAiSpeaking(false);
    setTranscript((prev) => [...prev, { speaker: "user", text, timestamp: Date.now() }]);
    setPartialTranscript("");
    setDraftResponse("");

    try {
      const res = await fetch(`${API_BASE}/interview/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_uid: sessionUid, transcript: text }),
      });
      const data = await res.json();
      if (data.status === "follow_up" || data.status === "next_question") {
        setCurrentQuestion(data.question);
        setQuestionIndex((prev) => prev + 1);
        setTranscript((prev) => [...prev, { speaker: "ai", text: data.question, timestamp: Date.now() }]);
        setAiSpeaking(true);
        if (data.evaluation) {
          setEvaluations((prev) => [...prev, data.evaluation]);
          setScores((prev) => [...prev, data.evaluation.overall_score]);
        }
      } else if (data.status === "completed") {
        setPhase("results");
      }
    } catch (e) {
      setError((e as Error).message);
    }
    setIsProcessing(false);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between max-w-5xl mx-auto">
          <div>
            <h1 className="text-2xl font-bold text-white">Live AI Interview</h1>
            <p className="text-sm text-gray-400">
              {phase === "setup" ? "Configure" :
               phase === "live" ? `Q${Math.max(questionIndex, 1)}/${totalQuestions}` : "Results"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="text-xs text-gray-500">{connected ? "Live" : "Offline"}</span>
            {lastLatency && (
              <span className="text-xs text-gray-500">{Math.round(lastLatency)}ms</span>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-6">
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 text-sm text-red-300">{error}</div>
        )}

        {phase === "setup" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
            <h2 className="text-xl font-semibold mb-6">Choose Interview Mode</h2>
            <div className="grid grid-cols-3 gap-3 mb-6">
              {INTERVIEW_MODES.map((m) => (
                <button key={m.key} onClick={() => setInterviewType(m.key)}
                  className={`p-4 rounded-lg border text-left transition-all ${
                    interviewType === m.key ? "border-blue-500 bg-blue-900/20 text-white" : "border-gray-800 bg-gray-800/50 text-gray-400 hover:border-gray-600"
                  }`}>
                  <span className="text-2xl">{m.icon}</span>
                  <p className="mt-2 text-sm font-medium">{m.label}</p>
                </button>
              ))}
            </div>
            <div className="mb-4">
              <label className="text-sm text-gray-400 block mb-1">User ID</label>
              <input value={userId} onChange={(e) => setUserId(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <button onClick={startInterview}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition-colors">
              Start Voice Interview
            </button>
          </div>
        )}

        {phase === "live" && (
          <AudioPermissionGate state={mic.state}>
            <div className="grid grid-cols-3 gap-6">
              <div className="col-span-2 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
                <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                  <h2 className="font-semibold">Conversation</h2>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${vad.isSpeaking ? "bg-blue-400 animate-pulse" : "bg-gray-600"}`} />
                    <span className="text-xs text-gray-500">{vad.isSpeaking ? "You're speaking" : aiSpeaking ? "AI speaking" : "Listening..."}</span>
                  </div>
                </div>

                {currentQuestion && (
                  <div className="px-4 py-2 bg-blue-900/10 border-b border-blue-900/20 text-sm text-blue-300">
                    <span className="text-blue-500 font-medium">Q{Math.max(questionIndex, 1)}:</span> {currentQuestion}
                  </div>
                )}

                <LiveTranscript
                  partial={partialTranscript}
                  finalTranscript={transcript.filter(t => t.speaker === "user").map(t => t.text)}
                  isAiSpeaking={aiSpeaking}
                  isUserSpeaking={vad.isSpeaking}
                />

                <div className="border-t border-gray-800 px-4 py-4 space-y-3">
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wide">Text fallback response</label>
                  <textarea
                    value={draftResponse}
                    onChange={(e) => setDraftResponse(e.target.value)}
                    placeholder="Type your response here if voice input is unavailable."
                    className="w-full min-h-[110px] bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
                  />
                  <div className="flex justify-end">
                    <button
                      onClick={() => submitTextResponse(draftResponse)}
                      disabled={!draftResponse.trim() || isProcessing || !sessionUid}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isProcessing ? "Submitting..." : "Submit Response"}
                    </button>
                  </div>
                </div>

                <VoiceVisualizer level={mic.audioLevel} isSpeaking={vad.isSpeaking} />

                <InterviewControlBar
                  micState={mic.state}
                  isSpeaking={vad.isSpeaking}
                  audioLevel={mic.audioLevel}
                  onRequestMic={mic.request}
                  onStopMic={mic.stop}
                  onToggleMute={mic.toggleMute}
                />
              </div>

              <div className="space-y-4">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <h3 className="text-sm font-semibold text-gray-400 mb-2">Scores</h3>
                  {scores.length === 0 ? (
                    <p className="text-sm text-gray-500">No scores yet</p>
                  ) : (
                    <div className="space-y-2">
                      {scores.map((s, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span className="text-gray-400">Q{i + 1}</span>
                          <span className={s >= 70 ? "text-green-400" : s >= 50 ? "text-yellow-400" : "text-red-400"}>{s}%</span>
                        </div>
                      ))}
                      <div className="border-t border-gray-800 pt-2 flex justify-between text-sm font-semibold">
                        <span className="text-gray-300">Avg</span>
                        <span className="text-white">{Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)}%</span>
                      </div>
                    </div>
                  )}
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
                  <div className="flex justify-between text-sm"><span className="text-gray-400">Mic</span><span className={mic.isActive ? "text-green-400" : "text-gray-500"}>{mic.isActive ? "Active" : "Off"}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-gray-400">Speaking</span><span className={vad.isSpeaking ? "text-blue-400" : "text-gray-500"}>{vad.isSpeaking ? "Yes" : "No"}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-gray-400">AI</span><span className={aiSpeaking ? "text-green-400" : isProcessing ? "text-yellow-400" : "text-gray-500"}>{aiSpeaking ? "Speaking" : isProcessing ? "Thinking" : "Ready"}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-gray-400">Questions</span><span className="text-white">{Math.max(questionIndex, 1)}/{totalQuestions}</span></div>
                </div>
              </div>
            </div>
          </AudioPermissionGate>
        )}

        {phase === "results" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
            <div className="text-6xl mb-4">🎯</div>
            <h2 className="text-2xl font-bold text-white mb-2">Interview Complete</h2>
            <p className="text-gray-400 mb-6">Average Score: {Math.round(scores.reduce((a, b) => a + b, 0) / Math.max(scores.length, 1))}%</p>
            <div className="grid grid-cols-2 gap-4 max-w-lg mx-auto text-left">
              {evaluations.slice(-3).map((ev, i) => (
                <div key={i} className="bg-gray-800 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-400 mb-1">{ev.overall_score}%</div>
                  <p className="text-xs text-gray-500 mb-2">Q{scores.length - evaluations.length + i + 1}</p>
                  {ev.strengths?.map((s, j) => <p key={j} className="text-xs text-green-400">+ {s}</p>)}
                  {ev.improvements?.map((s, j) => <p key={j} className="text-xs text-yellow-400">→ {s}</p>)}
                </div>
              ))}
            </div>
            <button onClick={() => { setPhase("setup"); setTranscript([]); setScores([]); setEvaluations([]); mic.stop(); }}
              className="mt-6 px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium">New Interview</button>
          </div>
        )}
      </div>
    </div>
  );
}
