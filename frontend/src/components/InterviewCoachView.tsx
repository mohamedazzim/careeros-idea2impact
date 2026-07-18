/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useInterviewWebSocket } from '@/hooks/useWebSocket';
import { useMicrophone, AudioChunk } from '@/hooks/useMicrophone';
import ConfirmationDialog from './ui/ConfirmationDialog';
import { formatDateOnly, formatTimeLocal } from '@/lib/datetime';

const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000/api/v1';
import { 
  Plus, 
  Play, 
  Clock, 
  Trash2, 
  BookOpen, 
  TrendingUp, 
  Award, 
  Cpu, 
  Sparkles, 
  Mic, 
  MicOff, 
  CheckCircle2, 
  AlertCircle, 
  ArrowRight,
  History,
  Brain,
  GraduationCap,
  Volume2,
  Calendar,
  X,
  FileText,
  Bookmark,
  Activity,
  UserCheck,
  Wifi,
  WifiOff,
  Zap,
  RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface InterviewCoachViewProps {
  token: string | null;
  activeDocId: string | null;
}

export default function InterviewCoachView({ token }: InterviewCoachViewProps) {
  const [activeScreen, setActiveScreen] = useState<'home' | 'simulator' | 'results'>('home');
  const [jobs, setJobs] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [memories, setMemories] = useState<any[]>([]);
  const [memoryEvents, setMemoryEvents] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [startingSession, setStartingSession] = useState(false);
  const [submittingAnswer, setSubmittingAnswer] = useState(false);
  const [endingSession, setEndingSession] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('technical');
  
  // Simulator State
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<string>('');
  const [userAnswerText, setUserAnswerText] = useState<string>('');
  const [questionCount, setQuestionCount] = useState<number>(1);
  const [totalQuestions, setTotalQuestions] = useState<number>(5);
  const [feedbackHistory, setFeedbackHistory] = useState<any[]>([]);
  const [latestFeedback, setLatestFeedback] = useState<any | null>(null);

  // WebSocket state for real-time interview
  const [wsConnected, setWsConnected] = useState(false);
  const [wsReconnecting, setWsReconnecting] = useState(false);
  const [wsLatency, setWsLatency] = useState<number>(0);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState<string[]>([]);

  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  // WebSocket hook for real-time interview events
  const wsUserId = token ? 'authenticated' : 'anonymous';
  const { connected, reconnecting, events: wsEvents, send: wsSend, sendBinary: wsSendBinary, subscribe: wsSubscribe } =
    useInterviewWebSocket(currentSessionId || '', wsUserId, selectedType);

  const headers = useCallback(() => {
    const config: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (token) {
      config['Authorization'] = `Bearer ${token}`;
    }
    return config;
  }, [token]);

  const fetchJobs = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await fetch(`${baseUrl}/jobs`, { headers: headers(), signal });
      if (res.ok) {
        const data = await res.json();
        const list = data.jobs || [];
        setJobs(list);
        if (list.length > 0) {
          setSelectedJobId(list[0].id);
        }
      }
    } catch (e) {
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (signal?.aborted || (e instanceof DOMException && e.name === 'AbortError')) return;
      console.error('Error fetching jobs selection list', e);
    }
  }, [headers]);

  const refreshHistoryData = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const res = await fetch(`${baseUrl}/interview/history`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error('Error fetching sessions list', e);
    } finally {
      setLoadingHistory(false);
    }
  }, [headers]);

  const refreshMemoryData = useCallback(async () => {
    try {
      const res = await fetch(`${baseUrl}/interview/memory`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setMemories(data.memories || []);
        setMemoryEvents(data.events || []);
      }
    } catch (e) {
      console.error('Error fetching memories state', e);
    }
  }, [headers]);

  const handleWsComplete = useCallback((data: any) => {
    setCurrentSessionId(null);
    refreshHistoryData();
    refreshMemoryData();
    setTimeout(() => {
      setEndingSession(false);
    }, 500);
  }, [refreshHistoryData, refreshMemoryData]);

  // Microphone → WebSocket binary streaming (replaces simulated recording)
  const mic = useMicrophone({
    sampleRate: 16000,
    chunkDurationMs: 100,
    onChunk: useCallback((chunk: AudioChunk) => {
      if (wsSendBinary) wsSendBinary(chunk.data);
    }, [wsSendBinary]),
  });

  // Sync WebSocket state
  useEffect(() => { setWsConnected(connected); }, [connected]);
  useEffect(() => { setWsReconnecting(reconnecting); }, [reconnecting]);

  // Timer simulation
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchJobs(controller.signal);
    return () => controller.abort();
  }, [fetchJobs]);

  // Handle incoming WebSocket events
  useEffect(() => {
    const latest = wsEvents[0];
    if (!latest) return;
    const d = latest.data as any;

    switch (latest.event) {
      case 'connected':
        setWsLatency(Date.now() - (Number(d.timestamp) || Date.now()));
        break;
      case 'heartbeat':
        setWsLatency(Date.now() - (Number(d.ts) || Date.now()));
        break;
      case 'QUESTION_DELIVERED':
        setCurrentQuestion(String(d.question ?? ''));
        setQuestionCount(Number(d.index) || 1);
        setTotalQuestions(Number(d.total) || 5);
        setAiSpeaking(false);
        setUserAnswerText('');
        break;
      case 'AI_THINKING':
        setAiSpeaking(true);
        break;
      case 'AI_SPEAKING':
        setAiSpeaking(true);
        break;
      case 'FEEDBACK_UPDATE':
        setLatestFeedback({
          score: Number(d.overall_score) || 0,
          strengths: Array.isArray(d.strengths) ? d.strengths : [],
          weaknesses: Array.isArray(d.improvements) ? d.improvements : [],
        });
        setAiSpeaking(false);
        break;
      case 'INTERVIEW_COMPLETED':
        handleWsComplete(d);
        break;
      case 'USER_TRANSCRIPT_PARTIAL':
      case 'USER_TRANSCRIPT_FINAL':
        setLiveTranscript((prev: string[]) => {
          const txt = String(d.transcript ?? '');
          const next = [...prev, txt];
          return next.length > 20 ? next.slice(-20) : next;
        });
        break;
    }
  }, [wsEvents, handleWsComplete]);

  useEffect(() => {
    if (activeScreen === 'simulator') {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => setElapsedSeconds(prev => prev + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [activeScreen]);

  // Report View State
  const [viewedReportId, setViewedReportId] = useState<string | null>(null);
  const [viewedSession, setViewedSession] = useState<any | null>(null);
  const [viewedMessages, setViewedMessages] = useState<any[]>([]);
  const [viewedFeedbacks, setViewedFeedbacks] = useState<any[]>([]);
  const [reportActiveTab, setReportActiveTab] = useState<'blueprint' | 'qa'>('blueprint');

  // Launch interview via WebSocket (replaces HTTP polling)
  const handleStartInterview = async () => {
    if (!selectedJobId) return;
    setStartingSession(true);
    setLatestFeedback(null);
    setFeedbackHistory([]);
    setQuestionCount(1);
    setLiveTranscript([]);
    try {
      const res = await fetch(`${baseUrl}/interview/start`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          user_id: wsUserId,
          interview_type: selectedType,
          mode: 'voice',
          job_id: selectedJobId,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setCurrentSessionId(data.session_uid);
        setCurrentQuestion(data.first_question || '');
        setUserAnswerText('');
        setActiveScreen('simulator');
      }
    } catch (e) {
      console.error('Failed to start interview', e);
    } finally {
      setStartingSession(false);
    }
  };

  // Submit answer through the persisted HTTP path.
  const handleSubmitMessage = async () => {
    if (!currentSessionId || !userAnswerText.trim()) return;
    setSubmittingAnswer(true);
    try {
      const res = await fetch(`${baseUrl}/interview/respond`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          session_uid: currentSessionId,
          transcript: userAnswerText,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'next_question') {
          setCurrentQuestion(data.question || '');
          setQuestionCount(prev => prev + 1);
        } else if (data.status === 'completed') {
          handleWsComplete(data);
        }
      }
      const feedback = { question: currentQuestion, answer: userAnswerText };
      setFeedbackHistory(prev => [...prev, feedback]);
      setUserAnswerText('');
    } catch (e) {
      console.error('Submit failed', e);
    } finally {
      setSubmittingAnswer(false);
    }
  };

  // Terminate & Compile report
  const handleEndInterview = async () => {
    const targetSessionId = currentSessionId;
    if (!targetSessionId) return;
    setEndingSession(true);
    try {
      const res = await fetch(`${baseUrl}/interview/end?session_uid=${targetSessionId}`, {
        method: 'POST',
        headers: headers()
      });

      if (res.ok) {
        // Give 2 seconds to simulate Celery workers compiling memories and reports
        setTimeout(() => {
          handleViewReport(targetSessionId);
          setCurrentSessionId(null);
          refreshHistoryData();
          refreshMemoryData();
          setEndingSession(false);
        }, 2200);
      } else {
        setEndingSession(false);
      }
    } catch (e) {
      console.error('Error ending interview coach simulator:', e);
      setEndingSession(false);
    }
  };

  // View specific summary PDF/Markdown blueprint
  const handleViewReport = async (sessionId: string) => {
    setLoadingReport(true);
    setViewedReportId(sessionId);
    try {
      const res = await fetch(`${baseUrl}/interview/report/${sessionId}`, { headers: headers() });
      if (res.ok) {
        const data = await res.json();
        setViewedSession(data);
        setViewedMessages(data.messages || []);
        setViewedFeedbacks(data.feedbacks || []);
        setActiveScreen('results');
      }
    } catch (e) {
      console.error('Error rendering session report details:', e);
    } finally {
      setLoadingReport(false);
    }
  };

  // Delete log history item
  const handleDeleteSession = async (sessionId: string) => {
    setDeleteTargetId(sessionId);
    setShowDeleteConfirm(true);
  };

  const executeDeleteSession = async () => {
    const sessionId = deleteTargetId;
    setShowDeleteConfirm(false);
    setDeleteTargetId(null);
    if (!sessionId) return;
    try {
      const res = await fetch(`${baseUrl}/interview/session/${sessionId}`, {
        method: 'DELETE',
        headers: headers()
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.session_uid !== sessionId));
        refreshMemoryData();
      }
    } catch (e) {
      console.error('Could not delete target session record:', e);
    }
  };

  // Calculations for KPI Display
  const calculateOverallAverage = () => {
    const completed = sessions.filter(s => s.status === 'completed' && s.overall_score !== undefined);
    if (completed.length === 0) return 0;
    const total = completed.reduce((acc, s) => acc + (s.overall_score || 0), 0);
    return Math.round(total / completed.length);
  };

  const formatTimer = (totSec: number) => {
    const mins = Math.floor(totSec / 60);
    const secs = totSec % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-8" id="interview-coach-view">
      
      {/* Title block */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 text-white rounded-3xl p-6 sm:p-8 relative overflow-hidden shadow-xl">
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-br from-indigo-500/10 to-emerald-500/5 blur-3xl pointer-events-none rounded-full" />
        <div className="space-y-2 relative z-10">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase bg-indigo-500/30 text-indigo-200 border border-indigo-500/20 rounded-md px-2 py-0.5 font-bold tracking-wider">
              Interview Intelligence
            </span>
            <span className="text-[10px] font-mono uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/20 rounded-md px-2 py-0.5 font-bold tracking-wider">
              Memory Connected
            </span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-display font-black tracking-tight flex items-center gap-3">
            <Brain className="h-8 w-8 text-indigo-400" />
            Interview Coach & Career Memory
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 max-w-xl font-normal leading-relaxed">
            Practice role-play sessions calibrated to targeted job requirements. CareerOS tracks persistent weakness trends in postgres, adapting future questions dynamically.
          </p>
        </div>
        <div className="flex items-center gap-3 relative z-10 shrink-0">
          <button 
            onClick={() => setActiveScreen('home')}
            className={`px-4 py-2 font-display text-xs font-semibold rounded-xl border transition-all ${activeScreen === 'home' ? 'bg-indigo-600 border-indigo-500 text-white shadow-md' : 'bg-slate-800 hover:bg-slate-755 border-slate-700 text-slate-200'}`}
          >
            Coach Dashboard
          </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        
        {/* SCREEN 1: INTERVIEW HOME / DASHBOARD */}
        {activeScreen === 'home' && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="grid grid-cols-1 lg:grid-cols-3 gap-8"
          >
            
            {/* LEFT / CENTER CORE: START PANEL & RECENT CONSTATATIONS */}
            <div className="lg:col-span-2 space-y-8">
              
              {/* Core KPI metrics display */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-white border border-slate-200/50 p-4 rounded-2xl shadow-xs">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-xs font-medium uppercase font-mono tracking-tight">Avg Grid Rating</span>
                    <TrendingUp className="h-4 w-4 text-emerald-500" />
                  </div>
                  <p className="text-3xl font-display font-bold text-slate-900 mt-2">
                    {calculateOverallAverage() > 0 ? `${calculateOverallAverage()}%` : 'N/A'}
                  </p>
                  <p className="text-[10px] text-slate-400 font-sans mt-1">Weighted average readiness</p>
                </div>

                <div className="bg-white border border-slate-200/50 p-4 rounded-2xl shadow-xs">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-xs font-medium uppercase font-mono tracking-tight">Memory Traits</span>
                    <Brain className="h-4 w-4 text-indigo-505" />
                  </div>
                  <p className="text-3xl font-display font-bold text-slate-950 mt-2">{memories.length}</p>
                  <p className="text-[10px] text-slate-400 font-sans mt-1">Compounded insights stored</p>
                </div>

                <div className="bg-white border border-slate-200/50 p-4 rounded-2xl shadow-xs">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-xs font-medium uppercase font-mono tracking-tight">Simulations</span>
                    <Activity className="h-4 w-4 text-orange-500" />
                  </div>
                  <p className="text-3xl font-display font-bold text-slate-900 mt-2">{sessions.length}</p>
                  <p className="text-[10px] text-slate-400 font-sans mt-1">Conducted interview sessions</p>
                </div>

                <div className="bg-white border border-slate-200/50 p-4 rounded-2xl shadow-xs">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-xs font-medium uppercase font-mono tracking-tight">Active Plan</span>
                    <GraduationCap className="h-4 w-4 text-indigo-500" />
                  </div>
                  <p className="text-3xl font-display font-bold text-slate-900 mt-2">
                    {sessions.filter(s => s.status === 'ongoing').length > 0 ? 'Active' : 'Ready'}
                  </p>
                  <p className="text-[10px] text-slate-400 font-sans mt-1">Interviewer loop state</p>
                </div>
              </div>

              {/* Configure and start an interview box */}
              <div className="bg-white rounded-3xl border border-slate-220/60 p-6 shadow-sm space-y-6">
                <div className="flex items-center gap-2 border-b border-slate-100 pb-4">
                  <Cpu className="h-5 w-5 text-indigo-650" />
                  <div>
                    <h3 className="text-base font-bold text-slate-900">Start Interview Coach Simulator</h3>
                    <p className="text-xs text-slate-400">Setup dynamic variables and launch the 5-question evaluation graph.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-700 tracking-tight block">Target Matching Job</label>
                    <select 
                      value={selectedJobId}
                      onChange={(e) => setSelectedJobId(e.target.value)}
                      className="w-full text-xs p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-indigo-500 focus:outline-none transition-all"
                    >
                      {jobs.map((job) => (
                        <option key={job.id} value={job.id}>
                          {job.title} ({job.company})
                        </option>
                      ))}
                      {jobs.length === 0 && (
                        <option value="">No jobs found. Access Opportunity list first.</option>
                      )}
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-700 tracking-tight block">Interviewer focus profile</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: 'technical', label: 'Tech Code' },
                        { id: 'behavioral', label: 'Behavioral' },
                        { id: 'ai_engineer', label: 'AI Engineer' }
                      ].map((type) => (
                        <button
                          key={type.id}
                          type="button"
                          onClick={() => setSelectedType(type.id)}
                          className={`p-2.5 text-center text-xs font-medium rounded-xl border transition-all ${selectedType === type.id ? 'bg-indigo-50 border-indigo-500 text-indigo-700' : 'bg-slate-50 border-slate-200 hover:bg-slate-100/60 text-slate-600'}`}
                        >
                          {type.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 bg-slate-50 border border-slate-150/40 rounded-2xl">
                  <div className="flex items-center gap-3 text-xs text-slate-500">
                    <Plus className="h-4 w-4 text-emerald-500 shrink-0" />
                    <span>Memory-Injected: Calibration will query weakness attributes to test past improvement.</span>
                  </div>
                  <button 
                    onClick={handleStartInterview}
                    disabled={startingSession || !selectedJobId}
                    className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-display text-xs font-semibold rounded-xl transition-all shadow-md disabled:opacity-50"
                  >
                    {startingSession ? 'Structuring...' : (
                      <>
                        <Play className="h-4 w-4" />
                        Launch Session
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Past Interviews list view */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <History className="h-4 w-4 text-slate-500" />
                    Recent Interview Sessions & Run History
                  </h3>
                  <button 
                    onClick={refreshHistoryData} 
                    className="text-xs text-indigo-650 font-semibold hover:underline"
                  >
                    Refresh Logs
                  </button>
                </div>

                {loadingHistory ? (
                  <div className="text-center py-8 text-xs text-slate-500">Loading history logs from platform...</div>
                ) : sessions.length === 0 ? (
                  <div className="bg-dashed border border-slate-200 rounded-2xl p-8 text-center text-slate-400">
                    <p className="text-xs">No sessions completed yet. Start one above.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {sessions.map((session) => (
                      <div 
                        key={session.session_uid} 
                        className="bg-white border border-slate-205/60 p-5 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all hover:border-slate-300"
                      >
                        <div className="space-y-1">
                          <p className="text-xs font-mono font-bold text-indigo-505 uppercase tracking-tight">{session.interview_type} Calibration</p>
                          <h4 className="text-sm font-bold text-slate-905">{session.job_title}</h4>
                          <div className="flex items-center gap-4 text-xs text-slate-400 font-normal">
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3.5 w-3.5" />
                              {formatDateOnly(session.started_at)}
                            </span>
                            <span>{session.difficulty} difficulty</span>
                            <span>{session.total_questions} questions</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-4 justify-between sm:justify-end border-t sm:border-t-0 pt-3 sm:pt-0">
                          {session.status === 'ongoing' ? (
                            <span className="text-xs font-mono font-semibold bg-amber-50 border border-amber-100 text-amber-700 rounded-lg px-2 py-1 flex items-center gap-1.5">
                              <span className="h-1.5 w-1.5 bg-amber-500 rounded-full animate-pulse" />
                              Ongoing
                            </span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono font-bold bg-indigo-50 border border-indigo-100 text-indigo-700 rounded-lg px-2 py-1">
                                Score: {typeof session.overall_score === 'number' ? `${session.overall_score}%` : 'Not available'}
                              </span>
                            </div>
                          )}

                          <div className="flex items-center gap-2">
                            {session.status === 'completed' && (
                              <button 
                                onClick={() => handleViewReport(session.session_uid)}
                                className="px-3.5 py-1.5 border border-slate-200 hover:bg-slate-50 text-slate-700 font-sans text-xs font-semibold rounded-lg transition-all"
                              >
                                View Syllabus Report
                              </button>
                            )}
                            <button 
                              onClick={() => handleDeleteSession(session.session_uid)}
                              className="p-1.5 text-slate-300 hover:text-rose-600 rounded-lg transition-all"
                              title="Delete Record"
                            >
                              <Trash2 className="h-4.5 w-4.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Live transcript panel (WebSocket-driven) */}
              {liveTranscript.length > 0 && (
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 max-h-32 overflow-y-auto space-y-1">
                  <span className="text-[9px] font-mono uppercase text-slate-400 block mb-1">Live Transcript</span>
                  {liveTranscript.map((t, i) => (
                    <p key={i} className="text-[10px] text-slate-600 italic leading-snug">{t}</p>
                  ))}
                </div>
              )}

            </div>

            {/* RIGHT SIDEBAR: PERSISTENT CAREER MEMORY VAULT */}
            <div className="space-y-8">
              <div className="bg-slate-900 text-slate-100 rounded-3xl border border-slate-800 p-6 shadow-md space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-indigo-400" />
                    <h3 className="text-sm font-bold text-white">Career Memory Vault</h3>
                  </div>
                  <button 
                    onClick={refreshMemoryData}
                    className="text-[10px] text-indigo-305 hover:underline"
                  >
                    Refresh
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Compounded Strengths</h4>
                    {memories.filter(m => m.memory_type === 'strength').length === 0 ? (
                      <p className="text-xs text-slate-500 italic">Complete sessions to identify strengths</p>
                    ) : (
                      <div className="space-y-2">
                        {memories.filter(m => m.memory_type === 'strength').map((m, idx) => (
                          <div key={idx} className="bg-slate-800/60 p-2.5 rounded-xl text-xs flex items-start gap-2 border border-emerald-500/10">
                            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                            <span>{m.content}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Observed Improvement Gaps</h4>
                    {memories.filter(m => m.memory_type === 'weakness').length === 0 ? (
                      <p className="text-xs text-slate-500 italic">No system design weaknesses stored yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {memories.filter(m => m.memory_type === 'weakness').map((m, idx) => (
                          <div key={idx} className="bg-slate-800/60 p-2.5 rounded-xl text-xs flex items-start gap-2 border border-rose-500/10">
                            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
                            <span>{m.content}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Memory Audit Log</h4>
                    <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                      {memoryEvents.map((e, idx) => (
                        <div key={idx} className="bg-slate-800/30 p-2.5 rounded-xl text-[11px] space-y-1 border border-slate-800">
                          <div className="flex items-center justify-between text-slate-400">
                            <span className="font-mono uppercase text-[9px] text-indigo-300">
                              {e.event_type.replace(/_/g, ' ')}
                            </span>
                            <span>{formatTimeLocal(e.created_at)}</span>
                          </div>
                          <p className="text-slate-202 leading-snug">{e.summary}</p>
                        </div>
                      ))}
                      {memoryEvents.length === 0 && (
                        <p className="text-xs text-slate-500 italic">No events generated.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </motion.div>
        )}

        {/* SCREEN 2: ACTIVE SIMULATOR PAGE */}
        {activeScreen === 'simulator' && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="grid grid-cols-1 lg:grid-cols-3 gap-8"
          >
            
            {/* CORE INTERACTIVE CONSOLE */}
            <div className="lg:col-span-2 bg-white rounded-3xl border border-indigo-150/50 p-6 sm:p-8 shadow-md space-y-6">
              
              {/* Header metrics bar with WebSocket status */}
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <div className="flex items-center gap-3">
                  <div className={`h-2 w-2 rounded-full animate-pulse ${wsConnected ? 'bg-emerald-500' : wsReconnecting ? 'bg-amber-500' : 'bg-rose-500'}`} />
                  <span className="text-xs font-mono font-bold text-slate-500 uppercase">Interactive Roleplay</span>
                  {/* Connection indicator */}
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded flex items-center gap-1 ${
                    wsConnected ? 'bg-emerald-50 text-emerald-700' : 
                    wsReconnecting ? 'bg-amber-50 text-amber-700' : 'bg-rose-50 text-rose-700'
                  }`}>
                    {wsConnected ? <Wifi className="h-3 w-3" /> : wsReconnecting ? <RefreshCw className="h-3 w-3 animate-spin" /> : <WifiOff className="h-3 w-3" />}
                    {wsConnected ? 'Live' : wsReconnecting ? 'Reconnecting' : 'Offline'}
                  </span>
                  {wsConnected && wsLatency > 0 && (
                    <span className="text-[9px] font-mono text-slate-400">
                      <Zap className="h-3 w-3 inline" /> {wsLatency}ms
                    </span>
                  )}
                  {aiSpeaking && (
                    <span className="text-[9px] font-mono bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded animate-pulse">
                      AI Speaking...
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-slate-600">
                  <span className="bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-md font-bold">
                    Question {questionCount} of {totalQuestions}
                  </span>
                  <span>|</span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {formatTimer(elapsedSeconds)}
                  </span>
                </div>
              </div>

              {/* Coach Query Box */}
              <div className="bg-slate-900 text-slate-100 p-6 rounded-2xl border border-slate-850 relative space-y-4">
                <div className="absolute top-3 right-3 shrink-0 flex items-center gap-1 font-mono text-[9px] bg-slate-800/80 px-2 py-0.5 rounded text-indigo-300">
                  <Cpu className="h-3 w-3" />
                  AI Interviewer Coach
                </div>
                <div className="flex items-start gap-3">
                  <p className="text-sm font-semibold text-white leading-relaxed font-mono">
                    &quot;{currentQuestion}&quot;
                  </p>
                </div>
              </div>

              {/* Answer Box Input */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-700">Write or speak your granular answer</label>
                  <span className="text-xs text-slate-400 font-mono">{userAnswerText.length} characters</span>
                </div>
                <textarea
                  value={userAnswerText}
                  onChange={(e) => setUserAnswerText(e.target.value)}
                  placeholder="Focus on specific technology choices, outline tradeoffs, structure responses using state-concurrency or performance details directly."
                  className="w-full h-44 p-4 border border-slate-202 rounded-2xl focus:ring-1 focus:ring-indigo-550 focus:outline-none text-xs leading-relaxed font-mono text-slate-800"
                />
              </div>

              {/* Voice controls & Actions drawer */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-100 pt-5">
                
                {/* Voice controls — real microphone */}
                <div className="flex items-center gap-4 w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={mic.isActive ? mic.stop : mic.request}
                    className={`flex items-center justify-center h-10 w-10 rounded-xl transition-all ${mic.isActive ? 'bg-rose-500 text-white animate-pulse' : 'bg-indigo-50 hover:bg-indigo-100 text-indigo-700'}`}
                    title={mic.isActive ? 'Stop Recording' : 'Start Microphone'}
                  >
                    {mic.isActive ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                  </button>

                  <div className="flex items-center gap-0.5 h-6">
                    {Array.from({ length: 15 }).map((_, idx) => {
                      const level = mic.isActive ? Math.floor(mic.audioLevel * 24) + 4 : 2;
                      return (
                        <span
                          key={idx}
                          style={{ height: `${level}px` }}
                          className={`w-1 rounded-full transition-all ${mic.isActive ? 'bg-rose-400' : 'bg-slate-200'}`}
                        />
                      );
                    })}
                  </div>

                  {mic.isActive && (
                    <span className="text-[10px] font-mono font-medium text-rose-500 animate-pulse uppercase tracking-tight">Recording...</span>
                  )}
                  {mic.state === 'requesting' && (
                    <span className="text-[10px] font-mono text-amber-500">Accessing mic...</span>
                  )}
                  {mic.state === 'denied' && (
                    <span className="text-[10px] font-mono text-rose-500">Mic denied</span>
                  )}
                </div>

                {/* Submitting buttons */}
                <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
                  <button 
                    onClick={handleEndInterview}
                    disabled={endingSession}
                    className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 font-sans text-xs font-semibold rounded-xl transition-all"
                  >
                    Skip to Report
                  </button>
                  <button 
                    onClick={handleSubmitMessage}
                    disabled={submittingAnswer || !userAnswerText.trim()}
                    className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-display text-xs font-semibold rounded-xl transition-all shadow-md disabled:bg-slate-100 disabled:text-slate-400 disabled:shadow-none"
                  >
                    {submittingAnswer ? 'Calibrating...' : (
                      <>
                        Submit Response
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </div>

              </div>

            </div>

            {/* RIGHT SIDEBAR: LAST ANSWER FEEDBACK TOAST */}
            <div className="space-y-6">
              <div className="bg-slate-50 border border-slate-200/60 p-5 rounded-3xl space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-700 uppercase tracking-wide border-b border-slate-200/40 pb-2">
                  <Volume2 className="h-4 w-4 text-indigo-550" />
                  Realtime Micro-Coach feedback
                </div>

                {latestFeedback ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3 bg-white p-3 border border-slate-200/50 rounded-2xl shadow-2xs">
                      <div className="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center font-mono font-bold text-indigo-700 text-xs">
                        {latestFeedback.score}%
                      </div>
                      <div>
                        <p className="text-xs font-bold text-slate-800">Answer Grade</p>
                        <p className="text-[10px] text-slate-400">Holistic rating matching resume</p>
                      </div>
                    </div>

                    <div className="space-y-2 text-[11px] leading-relaxed">
                      <p className="font-semibold text-slate-700 font-mono">Strengths identified:</p>
                      <ul className="list-disc pl-4 text-slate-600 space-y-1">
                        {latestFeedback.strengths?.map((s: string, idx: number) => (
                          <li key={idx}>{s}</li>
                        ))}
                      </ul>

                      <p className="font-semibold text-slate-700 font-mono mt-3">Improvement Areas:</p>
                      <ul className="list-disc pl-4 text-slate-600 space-y-1">
                        {latestFeedback.weaknesses?.map((w: string, idx: number) => (
                          <li key={idx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No answered submissions evaluated yet on this session.</p>
                )}
              </div>
            </div>

          </motion.div>
        )}

        {/* SCREEN 3: DETAILED SYLLABUS REPORT RESULTS VIEW */}
        {activeScreen === 'results' && viewedSession && (
          <motion.div 
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="space-y-8"
          >
            
            {/* Header info card */}
            <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-6 shadow-sm">
              <div className="space-y-2">
                <span className="text-[10px] font-mono uppercase bg-indigo-50 border border-indigo-150 text-indigo-700 rounded-md px-2 py-0.5 font-bold tracking-wider">
                  Session Performance Blueprint
                </span>
                <h3 className="text-xl font-bold text-slate-900">{viewedSession.job_title || 'Interview Session'} Syllabus</h3>
                <p className="text-xs text-slate-500 font-normal leading-relaxed">
                  Conducted on {formatDateOnly(viewedSession.started_at, 'recently')} for role profile at {viewedSession.company_name || 'the company'}
                </p>
              </div>

              {/* Dynamic overall rating displays */}
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <span className="text-[10px] font-mono uppercase text-slate-400 block tracking-wider">Overall Coach Matrix</span>
                  <p className="text-3xl font-display font-black text-indigo-700">{viewedSession.overall_score || 75}%</p>
                </div>
                <div className="h-10 w-[1px] bg-slate-200" />
                <button 
                  onClick={() => setActiveScreen('home')}
                  className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 font-sans text-xs font-semibold rounded-xl transition-all"
                >
                  Return to Panel
                </button>
              </div>
            </div>

            {/* Tab section for results toggling */}
            <div className="flex items-center gap-2 border-b border-slate-200/50 pb-2">
              <button
                onClick={() => setReportActiveTab('blueprint')}
                className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${reportActiveTab === 'blueprint' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-900'}`}
              >
                Comprehensive Study Blueprint
              </button>
              <button
                onClick={() => setReportActiveTab('qa')}
                className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${reportActiveTab === 'qa' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-900'}`}
              >
                Granular Transcripts Evaluation
              </button>
            </div>

            {reportActiveTab === 'blueprint' && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* PDF Study Roadmap syllabus display */}
                <div className="lg:col-span-2 bg-white border border-slate-201/80 p-6 sm:p-8 rounded-3xl shadow-xs space-y-6">
                  <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                    <FileText className="h-5 w-5 text-indigo-600 shrink-0" />
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">Custom Evaluation & Syllabus details</h4>
                      <p className="text-[11px] text-slate-400 font-normal">Generated from the persisted interview session record.</p>
                    </div>
                  </div>

                  {/* Render content structured elegantly using pre values or list lines mapping */}
                  <div className="text-xs leading-relaxed text-slate-700 space-y-4 font-normal max-h-[600px] overflow-y-auto pr-2">
                    {viewedSession.report_content ? (
                      viewedSession.report_content.split('\n').map((line: string, index: number) => {
                        if (line.startsWith('##')) {
                          return <h4 key={index} className="text-xs font-mono font-bold uppercase tracking-tight text-indigo-600 pt-3 border-b border-indigo-50/60 pb-1">{line.replace(/##/g, '').trim()}</h4>;
                        }
                        if (line.startsWith('#')) {
                          return <h3 key={index} className="text-sm font-bold text-slate-900 border-l-2 border-indigo-600 pl-2 py-0.5">{line.replace(/#/g, '').trim()}</h3>;
                        }
                        if (line.startsWith('-') || line.startsWith('*')) {
                          return <li key={index} className="ml-4 list-disc text-slate-600">{line.replace(/^[-*]/g, '').trim()}</li>;
                        }
                        return <p key={index} className="leading-relaxed font-sans mt-1 text-slate-700">{line}</p>;
                      })
                    ) : (
                      <div className="space-y-4 p-4">
                        <p className="text-sm font-semibold text-slate-700">Interview Session Summary</p>
                        <p className="text-xs text-slate-600">Overall Score: {viewedSession.overall_score || 'N/A'}%</p>
                        <p className="text-xs text-slate-600">Questions Answered: {viewedFeedbacks.length}</p>
                        <p className="text-xs text-slate-400 italic mt-4">Detailed blueprint content will be generated by the evaluation pipeline. Review the Q&A transcript tab for per-question breakdown.</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Performance dimensions stats lists */}
                <div className="space-y-6">
                  <div className="bg-slate-50 border border-slate-200/60 rounded-3xl p-6 space-y-4">
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-widest flex items-center gap-2 border-b border-slate-205 pb-2">
                      <Bookmark className="h-4 w-4" />
                      Dimension breakdown Scores
                    </h4>
                    
                    {viewedFeedbacks.length === 0 ? (
                      <p className="text-xs text-slate-400 italic">No dimension metrics found.</p>
                    ) : (
                      <div className="space-y-4">
                        {[
                          { label: 'Technical Accuracy Logic', key: 'technical_score', color: 'bg-emerald-500' },
                          { label: 'Grammar & Communication flow', key: 'communication_score', color: 'bg-indigo-500' },
                          { label: 'Delivery Confidence Assertiveness', key: 'confidence_score', color: 'bg-orange-500' },
                          { label: 'Prompt Relevance & Directness', key: 'relevance_score', color: 'bg-purple-500' }
                        ].map((dim, idx) => {
                          const scores = viewedFeedbacks
                            .map((feedback) => feedback[dim.key] ?? feedback.score)
                            .filter((score): score is number => typeof score === 'number' && Number.isFinite(score));
                          const avg = scores.length > 0
                            ? Math.round(scores.reduce((total, score) => total + score, 0) / scores.length)
                            : null;
                          return (
                            <div key={idx} className="space-y-2">
                              <div className="flex items-center justify-between text-xs font-sans">
                                <span className="text-slate-605 font-medium">{dim.label}</span>
                                <span className="font-bold text-slate-805">{avg === null ? 'Not available' : `${avg}%`}</span>
                              </div>
                              <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                                <div style={{ width: `${avg ?? 0}%` }} className={`h-full ${dim.color} rounded-full`} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

              </div>
            )}

            {reportActiveTab === 'qa' && (
              <div className="space-y-6">
                {viewedMessages.filter(m => m.role === 'user').map((userMsg: any, idx: number) => {
                  const correlatedFeedback = viewedFeedbacks.find(f => f.question_id === userMsg.id || f.id === userMsg.id);
                  const relatedIndex = viewedMessages.findIndex(m => m.id === userMsg.id);
                  const questionMsg = relatedIndex > 0 ? viewedMessages[relatedIndex - 1] : null;

                  return (
                    <div key={userMsg.id} className="bg-white border border-slate-200/60 rounded-3xl p-5 sm:p-6 space-y-4">
                      
                      <div className="flex items-center justify-between border-b border-slate-50 pb-2">
                        <span className="text-xs font-mono font-bold text-slate-400">TURN {idx + 1} DIRECT LOG</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono bg-indigo-50 text-indigo-700 border border-indigo-100 px-2 py-0.5 rounded font-bold">
                            Skill Level: {typeof userMsg.overall_score === 'number' ? `${userMsg.overall_score}%` : 'Not available'}
                          </span>
                        </div>
                      </div>

                      {questionMsg && (
                        <div className="bg-slate-50 border border-slate-100 p-4 rounded-xl">
                          <p className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-1">Coach Question</p>
                          <p className="text-xs text-slate-700 italic leading-relaxed">&quot;{questionMsg.message}&quot;</p>
                        </div>
                      )}

                      <div className="space-y-1">
                        <p className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-1">Your Granular Answer</p>
                        <p className="text-xs text-slate-800 font-mono leading-relaxed bg-indigo-50/10 p-4 rounded-xl border border-indigo-50/40">
                          {userMsg.message}
                        </p>
                      </div>

                      {userMsg.technical_score && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
                          <div className="p-3 border border-slate-100 rounded-xl bg-slate-50/50">
                            <span className="text-[9px] text-slate-400 font-mono uppercase block">Technical</span>
                            <span className="text-xs font-bold text-slate-800">{userMsg.technical_score}%</span>
                          </div>
                          <div className="p-3 border border-slate-100 rounded-xl bg-slate-50/50">
                            <span className="text-[9px] text-slate-400 font-mono uppercase block">Communication</span>
                            <span className="text-xs font-bold text-slate-800">{userMsg.communication_score}%</span>
                          </div>
                          <div className="p-3 border border-slate-100 rounded-xl bg-slate-50/50">
                            <span className="text-[9px] text-slate-400 font-mono uppercase block">Confidence</span>
                            <span className="text-xs font-bold text-slate-800">{userMsg.confidence_score}%</span>
                          </div>
                          <div className="p-3 border border-slate-100 rounded-xl bg-slate-50/50">
                            <span className="text-[9px] text-slate-400 font-mono uppercase block">Relevance</span>
                            <span className="text-xs font-bold text-slate-800">{userMsg.relevance_score}%</span>
                          </div>
                        </div>
                      )}

                    </div>
                  );
                })}
              </div>
            )}

          </motion.div>
        )}

      </AnimatePresence>

      <ConfirmationDialog
        open={showDeleteConfirm}
        title="Delete Interview Session"
        message="Are you sure you want to delete this session? This will remove related memory events. This action cannot be undone."
        confirmLabel="Delete Session"
        variant="danger"
        onConfirm={executeDeleteSession}
        onCancel={() => { setShowDeleteConfirm(false); setDeleteTargetId(null); }}
      />

    </div>
  );
}
