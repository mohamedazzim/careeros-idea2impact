/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';

const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
import { 
  Target, 
  Map, 
  CheckCircle, 
  Calendar, 
  BookOpen, 
  Activity, 
  Loader2, 
  TrendingUp, 
  Plus, 
  Cpu, 
  AlertCircle, 
  CheckSquare, 
  Settings, 
  Clock,
  Sparkles,
  RefreshCw,
  Terminal
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell
} from 'recharts';
import LearningPathsPanel from './learning/LearningPathsPanel';

interface UserPreferences {
  alert_threshold: number;
  notification_email: string;
  quiet_hours_start: string;
  quiet_hours_end: string;
  target_role?: string;
  target_salary?: string;
  target_location?: string;
  experience_level?: string;
  career_stage?: string;
  preferred_work_mode?: string;
  timeline_months?: number;
}

interface Roadmap {
  id: string;
  user_id: string;
  roadmap_type: 'SKILL_DEVELOPMENT' | 'INTERVIEW_PREP' | 'JOB_SEARCH' | 'AI_ENGINEER';
  title: string;
  summary: string;
  status: 'draft' | 'active' | 'completed' | 'archived';
  created_at: string;
  updated_at: string;
  trace_id?: string;
  run_id?: string;
}

interface Task {
  id: string;
  task_uid?: string;
  goal_id: string;
  task_title: string;
  task_description: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'completed';
}

interface Goal {
  id: string;
  roadmap_id: string;
  goal_type: 'weekly' | 'monthly' | 'quarterly' | 'milestone';
  title: string;
  description: string;
  target_date: string;
  status: 'pending' | 'in_progress' | 'completed';
  tasks?: Task[];
}

interface RoadmapProgress {
  roadmap_id?: string;
  title?: string;
  progress_source?: string;
  telemetry_status?: 'not_tracked' | 'partial' | 'tracked';
  completion_percentage: number;
  tasks_completed: number;
  total_tasks: number;
  consistency_score: number;
  recommendation_acceptance: number;
  progress_history?: any[];
  overall_progress?: number;
  active_tasks?: number;
  completed_tasks?: number;
  observability: {
    status?: 'not_tracked' | 'partial' | 'tracked';
    summary?: string;
    averageGenerationTimeMs: number | null;
    averageRefreshTimeMs: number | null;
    goalCompletionRatePercent: number;
    recommendationAcceptancePercent: number;
    totalGenerations: number | null;
    totalRefreshes: number | null;
  };
}

interface Recommendation {
  id: string;
  roadmap_id: string;
  recommendation_type: string;
  content: string;
  created_at: string;
}

const normalizeRoadmapList = (raw: any): Roadmap[] => {
  const list = Array.isArray(raw) ? raw : (raw?.roadmaps || raw?.data || []);
  return list.map((item: any) => ({
    id: item.roadmap_uid || String(item.id),
    user_id: item.user_id,
    roadmap_type: item.roadmap_type || 'AI_ENGINEER',
    title: item.title || `Career Path - ${item.target_role || 'Roadmap'}`,
    summary: item.summary || item.target_role || '',
    status: item.status || 'draft',
    created_at: item.created_at,
    updated_at: item.updated_at,
    trace_id: item.trace_id,
    run_id: item.run_id,
  }));
};

const normalizeRoadmapDetails = (item: any) => ({
  id: item.roadmap_uid || String(item.id),
  user_id: item.user_id,
  roadmap_type: item.roadmap_type || 'AI_ENGINEER',
  title: item.title || `Career Path - ${item.target_role || 'Roadmap'}`,
  summary: item.summary || `Target role: ${item.target_role || 'Career Track'}`,
  status: item.status || 'draft',
  created_at: item.created_at,
  updated_at: item.updated_at,
  trace_id: item.trace_id,
  run_id: item.run_id,
  completion_percentage: item.progress_pct || 0,
  goals: (item.goals || []).map((goal: any) => ({
    id: String(goal.id),
    roadmap_id: item.roadmap_uid || String(item.id),
    goal_type: goal.goal_type || 'milestone',
    title: goal.title || 'Goal',
    description: goal.description || '',
    target_date: goal.target_date || '',
    status: goal.status || 'pending',
    tasks: (goal.tasks || []).map((task: any) => ({
      id: task.task_uid || String(task.id),
      task_uid: task.task_uid || String(task.id),
      goal_id: String(goal.id),
      task_title: task.task_title || task.title || 'Task',
      task_description: task.task_description || task.description || '',
      priority: task.priority || 'medium',
      status: task.status || (task.completed ? 'completed' : 'pending'),
    })),
  })),
  recommendations: (item.recommendations || []).map((rec: any, index: number) => ({
    id: rec.id || `${item.roadmap_uid || item.id}-rec-${index}`,
    roadmap_id: item.roadmap_uid || String(item.id),
    recommendation_type: rec.recommendation_type || rec.type || 'strategy',
    content: rec.content || rec.text || '',
    created_at: rec.created_at || item.updated_at || item.created_at || new Date().toISOString(),
  })),
});

export default function CareerRoadmapView() {
  const authHeaders = useCallback((withJson: boolean = false) => {
    const token = typeof window !== 'undefined' ? (localStorage.getItem('careeros_token') || '') : '';
    const nextHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    if (withJson) {
      nextHeaders['Content-Type'] = 'application/json';
    }
    return nextHeaders;
  }, []);

  const roadmapTypeToTargetRole: Record<Roadmap['roadmap_type'], string> = {
    AI_ENGINEER: 'AI Engineer',
    SKILL_DEVELOPMENT: 'Skill Development',
    INTERVIEW_PREP: 'Interview Prep',
    JOB_SEARCH: 'Job Search',
  };

  // Local States
  const [preferences, setPreferences] = useState<UserPreferences>({
    alert_threshold: 85,
    notification_email: 'candidate@example.com',
    quiet_hours_start: '22:00',
    quiet_hours_end: '08:00',
    target_role: 'AI Engineer',
    target_salary: '$180,000/yr',
    target_location: 'San Francisco, CA (Hybrid)',
    experience_level: 'Senior',
    career_stage: 'Mid-Career',
    preferred_work_mode: 'hybrid',
    timeline_months: 12
  });

  const [activeTab, setActiveTab] = useState<'roadmap' | 'learning' | 'analytics'>('roadmap');
  const [roadmaps, setRoadmaps] = useState<Roadmap[]>([]);
  const [activeRoadmap, setActiveRoadmap] = useState<(Roadmap & { goals: Goal[]; recommendations: Recommendation[]; completion_percentage: number }) | null>(null);
  const [progressAnalytics, setProgressAnalytics] = useState<RoadmapProgress | null>(null);
  
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isUpdatingTask, setIsUpdatingTask] = useState<string | null>(null);
  const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Create Custom Roadmap Options
  const [selectedGenType, setSelectedGenType] = useState<Roadmap['roadmap_type']>('AI_ENGINEER');

  // Input preferences form variables
  const [prefTargetRole, setPrefTargetRole] = useState('');
  const [prefTargetSalary, setPrefTargetSalary] = useState('');
  const [prefTargetLoc, setPrefTargetLoc] = useState('');
  const [prefTimeline, setPrefTimeline] = useState('12');
  const autoSyncedRoadmapRef = useRef(false);

  const fetchRoadmapDetails = useCallback(async (id: string) => {
    try {
      const detailsRes = await fetch(`${baseUrl}/roadmaps/${id}`, { headers: authHeaders() });
      if (detailsRes.ok) {
        const val = await detailsRes.json();
        setActiveRoadmap(normalizeRoadmapDetails(val));
      }
    } catch (err) {
      console.error('Error fetching roadmap details:', err);
    }
  }, [authHeaders]);

  const fetchProgressAnalytics = useCallback(async () => {
    try {
      const progRes = await fetch(`${baseUrl}/roadmaps/progress`, { headers: authHeaders() });
      if (progRes.ok) {
        const prog = await progRes.json();
        setProgressAnalytics(prog);
      }
    } catch (err) {
      console.error('Error getting progress analytics:', err);
    }
  }, [authHeaders]);

  // Fetch all starting items
  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Fetch User preferences
      const prefRes = await fetch(`${baseUrl}/user/preferences`, { headers: authHeaders() });
      if (prefRes.ok) {
        const val = await prefRes.json();
        const careerExtras = val.extra || {};
        setPreferences({ ...val, ...careerExtras });
        setPrefTargetRole(careerExtras.target_role || val.target_role || 'AI Engineer');
        setPrefTargetSalary(careerExtras.target_salary || val.target_salary || '$180,000/yr');
        setPrefTargetLoc(careerExtras.target_location || val.target_location || 'San Francisco, CA (Hybrid)');
        setPrefTimeline(String(careerExtras.timeline_months || val.timeline_months || 12));
      }

      // 2. Fetch all roadmaps list
      const rmListRes = await fetch(`${baseUrl}/roadmaps`, { headers: authHeaders() });
      if (rmListRes.ok) {
        const raw = await rmListRes.json();
        const list = normalizeRoadmapList(raw);
        setRoadmaps(list);
        
        // Find first active roadmap and load its hydration details
        const active = list.find(r => r.status === 'active') || list[0];
        if (active) {
          await fetchRoadmapDetails(active.id);
        }
      }

      // 3. Fetch progress analytics
      await fetchProgressAnalytics();
    } catch (err) {
      console.error('Error hydrating Roadmap view details:', err);
    } finally {
      setIsLoading(false);
    }
  }, [authHeaders, fetchProgressAnalytics, fetchRoadmapDetails]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  useEffect(() => {
    if (!isPreferencesOpen) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsPreferencesOpen(false);
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isPreferencesOpen]);

  const refreshRoadmaps = useCallback(async () => {
    const rmListRes = await fetch(`${baseUrl}/roadmaps`, { headers: authHeaders() });
    if (!rmListRes.ok) {
      return [];
    }
    const raw = await rmListRes.json();
    const list = normalizeRoadmapList(raw);
    setRoadmaps(list);
    return list;
  }, [authHeaders]);

  const pollForRoadmap = useCallback(async (roadmapId?: string) => {
    const maxAttempts = 20;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const list = await refreshRoadmaps();
      const target = roadmapId
        ? list.find((roadmap) => roadmap.id === roadmapId)
        : list[0];
      if (!target) {
        continue;
      }
      await fetchRoadmapDetails(target.id);
      await fetchProgressAnalytics();
      return true;
    }
    return false;
  }, [fetchProgressAnalytics, fetchRoadmapDetails, refreshRoadmaps]);

  // Mark task toggled
  const handleToggleTask = async (taskUid: string, currentStatus: Task['status']) => {
    setIsUpdatingTask(taskUid);
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed';
    try {
      const patchRes = await fetch(`${baseUrl}/roadmaps/tasks/${taskUid}`, {
        method: 'PATCH',
        headers: authHeaders(true),
        body: JSON.stringify({ completed: newStatus === 'completed' })
      });

      if (patchRes.ok) {
        // Hydrate details back
        if (activeRoadmap) {
          await fetchRoadmapDetails(activeRoadmap.id);
        }
        await fetchProgressAnalytics();
      }
    } catch (err) {
      console.error('Task status update failed:', err);
    } finally {
      setIsUpdatingTask(null);
    }
  };

  // Generate a brand new roadmap
  const handleGenerateRoadmap = async () => {
    setIsSyncing(true);
    setFeedbackMsg(null);
    try {
      const genRes = await fetch(`${baseUrl}/roadmaps/generate`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({
          blueprint_type: selectedGenType,
          target_role: preferences.target_role || roadmapTypeToTargetRole[selectedGenType],
          target_location: prefTargetLoc || preferences.target_location || '',
          target_timeline: `${prefTimeline || preferences.timeline_months || 12} months`,
          target_salary: prefTargetSalary || preferences.target_salary || '',
        })
      });

      if (genRes.ok) {
        const generated = await genRes.json();
        setFeedbackMsg({
          type: 'success',
          text: `LangGraph Multi-Agent pipeline scheduled! Building a "${roleAwareBlueprintLabel(selectedGenType)}" for ${preferences.target_role || roadmapTypeToTargetRole[selectedGenType]} in Celery background queues...`
        });
        const roadmapId = generated.roadmap_uid || generated.id;
        if (roadmapId) {
          await fetchRoadmapDetails(roadmapId);
        }
        const resolved = await pollForRoadmap(roadmapId);
        if (!resolved && roadmapId) {
          setFeedbackMsg({
            type: 'error',
            text: 'Roadmap generation completed on the API, but the refreshed roadmap list did not arrive in time.'
          });
        }
        setIsSyncing(false);

      } else {
        const errText = await genRes.text();
        setFeedbackMsg({ type: 'error', text: errText || 'Failed to initialize graph pipeline.' });
        setIsSyncing(false);
      }
    } catch (err) {
      setFeedbackMsg({ type: 'error', text: 'Network failure initiating CareerOS AI agents.' });
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    if (isLoading || isSyncing) return;
    const currentRole = (preferences.target_role || '').trim().toLowerCase();
    if (!currentRole || autoSyncedRoadmapRef.current) return;
    const roadmapText = `${activeRoadmap?.title || ''} ${activeRoadmap?.summary || ''}`.toLowerCase();
    if (roadmapText.includes(currentRole)) return;
    autoSyncedRoadmapRef.current = true;
    void handleGenerateRoadmap();
  }, [activeRoadmap?.summary, activeRoadmap?.title, isLoading, isSyncing, preferences.target_role]);

  useEffect(() => {
    autoSyncedRoadmapRef.current = false;
  }, [preferences.target_role]);

  // Recalculate/manual refresh trigger
  const handleManualRefresh = async () => {
    setIsSyncing(true);
    setFeedbackMsg(null);
    try {
      const refreshRes = await fetch(`${baseUrl}/roadmaps/regenerate`, {
        method: 'POST',
        headers: authHeaders(),
      });

      if (refreshRes.ok) {
        setFeedbackMsg({
          type: 'success',
          text: 'CareerOS Celery thread triggered: Recalculating task ratios and tracking event updates.'
        });
        const resolved = await pollForRoadmap(activeRoadmap?.id);
        if (!resolved && activeRoadmap) {
          await fetchRoadmapDetails(activeRoadmap.id);
          await fetchProgressAnalytics();
        }
        setIsSyncing(false);
      } else {
        setIsSyncing(false);
      }
    } catch (err) {
      setIsSyncing(false);
    }
  };

  // Update User Preference profiles values
  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedbackMsg(null);
    try {
      const upPrefs = {
        ...preferences,
        extra: {
          target_role: prefTargetRole,
          target_salary: prefTargetSalary,
          target_location: prefTargetLoc,
          timeline_months: parseInt(prefTimeline),
          experience_level: preferences.experience_level || 'Senior',
          career_stage: preferences.career_stage || 'Mid-Career',
          preferred_work_mode: preferences.preferred_work_mode || 'hybrid',
        }
      };

      const putRes = await fetch(`${baseUrl}/user/preferences`, {
        method: 'PUT',
        headers: authHeaders(true),
        body: JSON.stringify(upPrefs)
      });

      if (putRes.ok) {
        const saved = await putRes.json();
        const savedExtras = saved.extra || {};
        setPreferences({ ...saved, ...savedExtras });
        setIsPreferencesOpen(false);
        setFeedbackMsg({ type: 'success', text: 'Career targets updated! Auto-recalc will calibrate learning paths based on these variables during next run.' });
      } else {
        setFeedbackMsg({ type: 'error', text: 'Failed to serialize career specifications to profile database.' });
      }
    } catch (err) {
      setFeedbackMsg({ type: 'error', text: 'Failed connecting to database profiles gateway.' });
    }
  };

  const currentCompletion = progressAnalytics?.completion_percentage ?? progressAnalytics?.overall_progress ?? 0;
  const currentConsistency = progressAnalytics?.consistency_score ?? currentCompletion;
  const currentVelocity = progressAnalytics?.observability?.goalCompletionRatePercent ?? currentCompletion;
  const telemetryStatus = progressAnalytics?.telemetry_status ?? progressAnalytics?.observability?.status ?? 'not_tracked';
  const telemetryTracked = telemetryStatus === 'tracked' && typeof progressAnalytics?.observability?.totalGenerations === 'number' && (progressAnalytics.observability.totalGenerations ?? 0) > 0;
  const telemetrySummary = progressAnalytics?.observability?.summary || 'Generation timing and refresh counts are not persisted yet.';
  const roadmapScopeLabel = preferences.target_role
    ? `${preferences.target_role} Milestone Plan`
    : 'Role-Specific Milestone Plan';
  const roadmapScopeSubtitle = preferences.target_role
    ? `Milestones tailored for ${preferences.target_role}, ${preferences.target_location || 'your target market'}, and your timeline.`
    : 'Milestones tailored to the active role, location, and timeline preferences.';
  const roleAwareBlueprintLabel = (type: Roadmap['roadmap_type']) => {
    const role = (preferences.target_role || '').toLowerCase();
    if (type === 'AI_ENGINEER') {
      if (role.includes('flutter') || role.includes('dart') || role.includes('mobile')) return 'Flutter Full Stack Roadmap';
      if (role.includes('java')) return 'Java Full Stack Roadmap';
      if (role.includes('full stack')) return 'Full Stack Roadmap';
      if (role.includes('devops') || role.includes('platform')) return 'DevOps / Platform Roadmap';
      if (role.includes('data')) return 'Data Science / Analytics Roadmap';
      return 'AI / MLOps Roadmap';
    }
    if (type === 'SKILL_DEVELOPMENT') {
      return `${preferences.target_role || 'Target Role'} Skill Development`;
    }
    if (type === 'INTERVIEW_PREP') {
      return `${preferences.target_role || 'Target Role'} Interview Prep`;
    }
    return `${preferences.target_role || 'Target Role'} Job Search`;
  };

  // Derived chart series from live progress data
  const chartData = [
    { name: 'Start', progress: 0, consistency: 0, velocity: 0 },
    { name: 'Week 1', progress: Math.round(currentCompletion * 0.25), consistency: Math.round(currentConsistency * 0.25), velocity: Math.round(currentVelocity * 0.25) },
    { name: 'Week 2', progress: Math.round(currentCompletion * 0.5), consistency: Math.round(currentConsistency * 0.5), velocity: Math.round(currentVelocity * 0.5) },
    { name: 'Week 3', progress: Math.round(currentCompletion * 0.75), consistency: Math.round(currentConsistency * 0.75), velocity: Math.round(currentVelocity * 0.75) },
    { name: 'Current', progress: currentCompletion, consistency: currentConsistency, velocity: currentVelocity },
  ];

  const barChartData = [
    { task: 'Tasks Completed', rate: progressAnalytics?.total_tasks ? Math.round((progressAnalytics.tasks_completed / progressAnalytics.total_tasks) * 100) : 0 },
    { task: 'Tasks Remaining', rate: progressAnalytics?.total_tasks ? Math.round(((progressAnalytics.total_tasks - progressAnalytics.tasks_completed) / progressAnalytics.total_tasks) * 100) : 0 },
    { task: 'Active Roadmaps', rate: roadmaps.filter(r => r.status === 'active').length > 0 ? 100 : 0 },
    { task: 'Recommendations', rate: activeRoadmap?.recommendations?.length ? Math.min(activeRoadmap.recommendations.length * 25, 100) : 0 },
  ];

  const colors = ['#6366f1', '#4f46e5', '#4338ca', '#312e81'];
  const safeDate = (value?: string | null) => {
    if (!value) return 'TBD';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'TBD' : parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  useEffect(() => {
    const role = preferences.target_role || '';
    const salary = preferences.target_salary || '';
    const location = preferences.target_location || '';
    const timeline = preferences.timeline_months != null ? String(preferences.timeline_months) : '';

    setPrefTargetRole(role);
    setPrefTargetSalary(salary);
    setPrefTargetLoc(location);
    setPrefTimeline(timeline || '12');
  }, [preferences.target_role, preferences.target_salary, preferences.target_location, preferences.timeline_months]);

  return (
    <div className="space-y-6" id="career-roadmap-view">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-2xl p-6 shadow-md border border-indigo-900/30">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-xs font-semibold text-indigo-300 border border-indigo-500/30 flex items-center gap-1">
              <Sparkles className="h-3.5 w-3.5" />
              AI Career Operating System
            </span>
          </div>
          <h1 className="text-2xl font-bold font-display tracking-tight mt-1 text-white">Career Roadmap Agent</h1>
          <p className="text-slate-300 text-xs max-w-xl">
            Analyze Knowledge Hub, Career Memory, and live market expectations through LangGraph orchestration to dynamically compose daily goals, training programs, and project milestones.
          </p>
        </div>

        <div className="mt-4 md:mt-0 flex gap-2">
          <button 
            id="btn-settings"
            onClick={() => setIsPreferencesOpen(true)}
            className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 active:scale-95 transition text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 cursor-pointer shadow-sm shadow-indigo-600/20"
          >
            <Settings className="h-4 w-4" />
            Set Career Goals
          </button>
          
          <button
            id="btn-manual-sync"
            onClick={handleManualRefresh}
            disabled={isSyncing}
            className="px-4 py-2 bg-slate-800 border border-slate-700 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-xl flex items-center gap-1.5 cursor-pointer transition"
          >
            {isSyncing ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh Stats
          </button>
        </div>
      </div>

      {feedbackMsg && (
        <div className={`p-4 rounded-xl border flex items-start gap-2.5 ${feedbackMsg.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-rose-50 text-rose-800 border-rose-200'} text-xs animate-fade-in`}>
          {feedbackMsg.type === 'success' ? <CheckSquare className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" /> : <AlertCircle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />}
          <div>
            <p className="font-semibold">{feedbackMsg.type === 'success' ? 'Agent Pipeline Active' : 'Operation Halted'}</p>
            <p className="mt-0.5">{feedbackMsg.text}</p>
          </div>
        </div>
      )}

      {/* 2. Top-Level Metric Gauges in Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Overall Progress</p>
            <h3 className="text-3xl font-bold font-mono text-slate-900 tracking-tight">
              {progressAnalytics ? `${progressAnalytics.completion_percentage}%` : '—'}
            </h3>
            <p className="text-slate-500 text-[10px] flex items-center gap-1">
              <span className="text-indigo-600 font-bold font-mono">
                {progressAnalytics ? `${progressAnalytics.tasks_completed} / ${progressAnalytics.total_tasks}` : '—'}
              </span> tasks completed
            </p>
          </div>
          <div className="relative h-14 w-14 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="28" cy="28" r="24" className="stroke-slate-100" strokeWidth="4" fill="transparent" />
              <circle 
                cx="28" 
                cy="28" 
                r="24" 
                className="stroke-indigo-600 transition-all duration-500" 
                strokeWidth="4" 
                fill="transparent" 
                strokeDasharray={150.7} 
                strokeDashoffset={150.7 - (150.7 * (progressAnalytics?.completion_percentage ?? 0)) / 100} 
              />
            </svg>
            <span className="absolute text-xs font-bold font-mono text-indigo-700">{progressAnalytics?.completion_percentage ?? 0}%</span>
          </div>
        </div>

        <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Target Role Profile</p>
            <h4 className="text-sm font-semibold text-slate-900 tracking-tight truncate max-w-[160px]">
              {preferences.target_role || 'AI Engineer'}
            </h4>
            <p className="text-slate-500 text-[10px] flex items-center gap-1 mt-1 font-mono">
              Timeline: {preferences.timeline_months ?? 12} Mos | {preferences.target_salary || '$180,000/yr'}
            </p>
          </div>
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
            <Target className="h-5 w-5" />
          </div>
        </div>

        <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Consistency Score</p>
            <h3 className="text-3xl font-bold font-mono text-emerald-600 tracking-tight">
              {progressAnalytics ? `${progressAnalytics.consistency_score}%` : '—'}
            </h3>
            <p className="text-slate-500 text-[10px] flex items-center gap-1">
              <span className="text-emerald-600 font-bold">Stable</span> target completion velocity
            </p>
          </div>
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
            <TrendingUp className="h-5 w-5" />
          </div>
        </div>

        <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Roadmap Telemetry</p>
            <h3 className="text-3xl font-bold font-mono text-indigo-900 tracking-tight">
              {telemetryTracked ? `${Math.min(100, Math.round(progressAnalytics?.observability?.goalCompletionRatePercent ?? currentCompletion))}%` : 'Not tracked'}
            </h3>
            <p className="text-slate-500 text-[10px] flex items-center gap-1 font-mono text-[9px]">
              {telemetryTracked
                ? `Latency: ${progressAnalytics?.observability?.averageGenerationTimeMs ?? '—'}ms | ${progressAnalytics?.observability?.totalGenerations ?? '—'} runs`
                : 'Timing telemetry is not persisted yet'}
            </p>
          </div>
          <div className="p-3 bg-slate-50 text-slate-600 rounded-xl">
            <Cpu className="h-5 w-5" />
          </div>
        </div>
      </div>

      {/* 3. Sub-navigation tabs */}
      <div className="flex border-b border-slate-100">
        <button
          onClick={() => setActiveTab('roadmap')}
          className={`px-5 py-3 text-xs font-semibold flex items-center gap-2 border-b-2 cursor-pointer transition ${activeTab === 'roadmap' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
        >
          <Map className="h-4 w-4" />
          Roadmap Plan Checklist
        </button>
        <button
          onClick={() => setActiveTab('learning')}
          className={`px-5 py-3 text-xs font-semibold flex items-center gap-2 border-b-2 cursor-pointer transition ${activeTab === 'learning' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
        >
          <BookOpen className="h-4 w-4" />
          Curated Training Curricular
        </button>
        <button
          onClick={() => setActiveTab('analytics')}
          className={`px-5 py-3 text-xs font-semibold flex items-center gap-2 border-b-2 cursor-pointer transition ${activeTab === 'analytics' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-900'}`}
        >
          <Activity className="h-4 w-4" />
          Velocity Analytics & Logs
        </button>
      </div>

      {/* 4. Active tab container display */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left main area columns */}
        <div className="lg:col-span-8 space-y-6">
          {isLoading ? (
            <div className="bg-white border border-slate-100 rounded-2xl p-12 text-center flex flex-col items-center justify-center space-y-4">
              <Loader2 className="h-8 w-8 text-indigo-600 animate-spin" />
              <p className="text-slate-500 text-xs font-medium">Synchronizing roadmap context schemas...</p>
            </div>
          ) : activeTab === 'roadmap' ? (
            <div className="space-y-6">
              
              {/* Active Roadmap Intro Card */}
              <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-xs space-y-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="px-2 py-0.5 text-[9px] font-bold uppercase rounded-md bg-indigo-50 border border-indigo-100 text-indigo-600">Active Role Plan</span>
                    <h2 className="text-lg font-bold font-display text-slate-950 mt-1">{activeRoadmap?.title || 'No active roadmap selected'}</h2>
                  </div>
                  
                  <span className="text-[10px] font-mono text-slate-400">
                    ID: {activeRoadmap?.id}
                  </span>
                </div>
                
                <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 p-3 rounded-xl">{activeRoadmap?.summary}</p>
              </div>

              {/* Weekly/Monthly/Quarterly Goals Timeline */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 uppercase tracking-wide">
                  <Calendar className="h-4 w-4 text-indigo-500" />
                  {roadmapScopeLabel}
                </h3>
                <p className="text-[11px] text-slate-500 -mt-2">{roadmapScopeSubtitle}</p>

                {activeRoadmap?.goals?.map((goal, idx) => (
                  <div key={goal.id} className="bg-white border border-slate-100 rounded-2xl shadow-xs overflow-hidden">
                    {/* Goal Header banner */}
                    <div className="bg-slate-50/70 border-b border-slate-100 px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-start gap-2.5">
                        <span className={`px-2 py-0.5 mt-0.5 text-[8px] uppercase font-bold rounded-md border ${
                          goal.goal_type === 'weekly' ? 'bg-indigo-50 border-indigo-100 text-indigo-700' :
                          goal.goal_type === 'monthly' ? 'bg-sky-50 border-sky-100 text-sky-700' :
                          goal.goal_type === 'quarterly' ? 'bg-emerald-50 border-emerald-100 text-emerald-700' :
                          'bg-indigo-900 border-indigo-950 text-white'
                        }`}>
                          {goal.goal_type}
                        </span>
                        
                        <div>
                          <h4 className="text-xs font-bold text-slate-950">{goal.title}</h4>
                          <p className="text-[10px] text-slate-500 mt-0.5">{goal.description}</p>
                        </div>
                      </div>

                      <div className="text-[10px] text-slate-500 font-mono flex items-center gap-1.5 flex-shrink-0 bg-white border border-slate-100 px-2.5 py-1 rounded-lg">
                        <Clock className="h-3 w-3 text-slate-400" />
                        Target: {safeDate(goal.target_date)}
                      </div>
                    </div>

                    {/* Goal Tasks checklist list */}
                    <div className="divide-y divide-slate-100 text-xs">
                      {goal.tasks && goal.tasks.length > 0 ? (
                        goal.tasks.map(task => (
                          <div key={task.id} className="p-4 flex items-start gap-3 hover:bg-slate-50/40 transition">
                            <button
                              onClick={() => handleToggleTask(task.task_uid || task.id, task.status)}
                              disabled={isUpdatingTask === (task.task_uid || task.id)}
                              className="mt-0.5 shrink-0 hover:scale-105 active:scale-95 transition cursor-pointer"
                            >
                              {isUpdatingTask === (task.task_uid || task.id) ? (
                                <Loader2 className="h-4.5 w-4.5 animate-spin text-indigo-500" />
                              ) : task.status === 'completed' ? (
                                <div className="h-4.5 w-4.5 rounded-md bg-indigo-600 border border-indigo-600 flex items-center justify-center text-white">
                                  <CheckCircle className="h-3.5 w-3.5 text-white stroke-[3.5]" />
                                </div>
                              ) : (
                                <div className="h-4.5 w-4.5 rounded-md border border-slate-300 hover:border-indigo-500 bg-white" />
                              )}
                            </button>

                            <div className="space-y-0.5 flex-1">
                              <div className="flex items-center gap-2">
                                <span className={`font-semibold ${task.status === 'completed' ? 'line-through text-slate-400' : 'text-slate-900'}`}>
                                  {task.task_title}
                                </span>
                                
                                <span className={`px-1.5 py-0.2 text-[8px] uppercase font-bold rounded-md ${
                                  task.priority === 'high' ? 'bg-rose-50 text-rose-600 border border-rose-100' :
                                  task.priority === 'medium' ? 'bg-amber-50 text-amber-600 border border-amber-100' :
                                  'bg-slate-100 text-slate-600 border border-slate-200'
                                }`}>
                                  {task.priority}
                                </span>
                              </div>
                              <p className="text-slate-500 text-[11px] leading-relaxed">{task.task_description}</p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="p-4 text-center text-[11px] text-slate-400">
                          No specific execution routines assigned to this stage.
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : activeTab === 'learning' ? (
            <div className="space-y-6">
              <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-xs space-y-4">
                <LearningPathsPanel
                  compact
                  title="Verified Learning Paths"
                  subtitle="Real free learning resources mapped to your live skill gaps."
                  limit={6}
                  emptyMessage="No verified learning resources are available yet for the current gaps."
                />
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Analytics visual recharts widgets */}
              <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-xs space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-950 flex items-center gap-2">
                    <TrendingUp className="h-4.5 w-4.5 text-indigo-500" />
                    Speed and Consistency Velocity logs
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-1">Measures goal completion rates and task execution durations over active weekly schedules.</p>
                </div>

                <div className="h-68 w-full text-xs font-sans">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                      <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                      <Tooltip />
                      <Line type="monotone" dataKey="progress" name="Completed %" stroke="#6366f1" strokeWidth={3} activeDot={{ r: 8 }} />
                      <Line type="monotone" dataKey="consistency" name="Consistency Score" stroke="#10b981" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Bar distribution checklist */}
                <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-xs space-y-4">
                  <h4 className="text-xs font-bold text-slate-950 uppercase tracking-widest text-slate-500">Milestone Task Completion Rates</h4>
                  
                  <div className="h-50 w-full text-xs">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barChartData}>
                        <XAxis dataKey="task" stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <Tooltip />
                        <Bar dataKey="rate" fill="#4f46e5" radius={[4, 4, 0, 0]}>
                          {barChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Telemetry diagnostics stats block */}
                <div className="bg-white border border-slate-100 rounded-2xl p-6 shadow-xs space-y-4 flex flex-col justify-between">
                  <div className="space-y-1.5">
                    <h4 className="text-xs font-bold text-slate-950 uppercase tracking-widest text-slate-500">Roadmap Diagnostics</h4>
                    <p className="text-[11px] text-slate-500 leading-relaxed">Progress completion is computed from stored roadmap tasks. Timing telemetry is not yet persisted.</p>
                  </div>

                  <div className="space-y-3 font-mono text-[10px] bg-slate-950 text-slate-300 p-4 rounded-xl border border-slate-800">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                      <span className="text-slate-400">Average Generation Latency:</span>
                      <span className="text-indigo-400 font-bold">
                        {progressAnalytics?.observability?.averageGenerationTimeMs != null
                          ? `${progressAnalytics.observability.averageGenerationTimeMs} ms`
                          : 'not tracked'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                      <span className="text-slate-400">Calculated Goal Completion:</span>
                      <span className="text-emerald-400 font-bold">{progressAnalytics?.observability?.goalCompletionRatePercent ?? 0}%</span>
                    </div>
                    <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
                      <span className="text-slate-400">Tracked Generation Runs:</span>
                      <span className="text-indigo-400 font-bold">
                        {progressAnalytics?.observability?.totalGenerations != null
                          ? progressAnalytics.observability.totalGenerations
                          : 'not tracked'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Telemetry State:</span>
                      <span className="text-emerald-400 font-bold flex items-center gap-1">
                        <span className={`h-1.5 w-1.5 rounded-full ${telemetryTracked ? 'bg-emerald-500 animate-pulse' : 'bg-slate-500'}`} />
                        {telemetryStatus.toUpperCase()}
                      </span>
                    </div>
                    <div className="pt-2 border-t border-slate-800 text-slate-500 leading-relaxed">
                      {telemetrySummary}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right sidebars/action column */}
        <div className="lg:col-span-4 space-y-6">
          
          {/* Create custom blueprint agent manager */}
          <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs space-y-4">
            <div>
              <h3 className="text-xs font-bold text-slate-950 uppercase tracking-widest text-slate-500">New Agent Blueprint</h3>
              <p className="text-[11px] text-slate-500 mt-1">Instruct the LangGraph orchestrator to generate a completely new custom roadmap blueprint from database parameters.</p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-wider mb-1.5">Select Pipeline Type</label>
                <select
                  value={selectedGenType}
                  onChange={(e) => setSelectedGenType(e.target.value as any)}
                  className="w-full text-xs p-2.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl focus:border-indigo-500 outline-none transition"
                >
                  <option value="AI_ENGINEER">{roleAwareBlueprintLabel('AI_ENGINEER')}</option>
                  <option value="SKILL_DEVELOPMENT">{roleAwareBlueprintLabel('SKILL_DEVELOPMENT')}</option>
                  <option value="INTERVIEW_PREP">{roleAwareBlueprintLabel('INTERVIEW_PREP')}</option>
                  <option value="JOB_SEARCH">{roleAwareBlueprintLabel('JOB_SEARCH')}</option>
                </select>
              </div>

              <button
                id="btn-generate-blueprint"
                onClick={handleGenerateRoadmap}
                disabled={isSyncing}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 disabled:opacity-50 transition text-white text-xs font-bold rounded-xl flex items-center justify-center gap-1.5 shadow-sm shadow-indigo-600/20 cursor-pointer"
              >
                {isSyncing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Compiling Graph Node Outputs...
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4" />
                    Compile Selected Blueprint
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Actionable Recommendations list from database */}
          <div className="bg-white border border-slate-100 rounded-2xl p-5 shadow-xs space-y-4">
            <h3 className="text-xs font-bold text-slate-950 uppercase tracking-widest text-slate-500">AI Coaching Advices</h3>
            
            <div className="space-y-3">
              {activeRoadmap?.recommendations && activeRoadmap.recommendations.length > 0 ? (
                activeRoadmap.recommendations.map(rec => (
                  <div key={rec.id} className="p-3 bg-indigo-50/50 border border-indigo-100/50 rounded-xl flex items-start gap-2.5 text-[11px] leading-relaxed text-indigo-950">
                    <Sparkles className="h-4 w-4 text-indigo-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-[10px] text-indigo-800 uppercase tracking-wider">{rec.recommendation_type}</p>
                      <p className="mt-0.5">{rec.content}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center p-3 text-slate-400 text-xs">
                  Awaiting profile context matches to formulate advices.
                </div>
              )}
            </div>
          </div>

          {/* Observability Traces Audit Logs drawer */}
          <div className="bg-slate-950 border border-slate-900 rounded-2xl p-5 shadow-md space-y-3 text-slate-100">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-indigo-400 flex items-center gap-1.5">
                <Terminal className="h-4 w-4 text-indigo-500" />
                LangSmith Tracing Coordinates
              </h4>
              <span className="text-[8px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-1.5 py-0.2 rounded-full font-bold">
                AUDITED
              </span>
            </div>

            <div className="space-y-1.5 font-mono text-[9px] text-slate-400 leading-normal">
              <p><span className="text-indigo-400">Active Trace ID:</span> {activeRoadmap?.trace_id || '—'}</p>
              <p><span className="text-indigo-400">Run Node ID:</span> {activeRoadmap?.run_id || '—'}</p>
              <p><span className="text-slate-500">Pipeline nodes:</span> context → profile → market_filter → gap_analysis → blueprint_generate → build_certification_tasks → db_persist</p>
            </div>
          </div>
        </div>
      </div>

      {/* 5. User career profiles specs input form drawer (Modal Backdrop) */}
      {isPreferencesOpen && (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fade-in"
          id="settings-modal bg"
          onClick={() => setIsPreferencesOpen(false)}
          role="presentation"
        >
          <div
            className="bg-white border border-slate-100 rounded-2xl p-6 w-full max-w-md shadow-xl space-y-4 animate-scale-up"
            id="settings-modal block"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="career-profile-dialog-title"
          >
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-slate-950 flex items-center gap-2" id="career-profile-dialog-title">
                <Settings className="h-4.5 w-4.5 text-indigo-500" />
                Configure Career Profile Rules
              </h3>
              <button 
                type="button"
                aria-label="Close preferences modal"
                onClick={() => setIsPreferencesOpen(false)}
                className="text-slate-400 hover:text-slate-700 text-xs font-bold bg-slate-50 hover:bg-slate-100 px-2 py-1 rounded transition cursor-pointer"
              >
                Close
              </button>
            </div>

            <form onSubmit={handleSavePreferences} className="space-y-4 text-xs select-none">
              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-wider">Target Position Title</label>
                <input
                  type="text"
                  required
                  value={prefTargetRole}
                  onChange={(e) => setPrefTargetRole(e.target.value)}
                  placeholder="e.g. Senior Machine Learning Pipelines Engineer"
                  className="w-full p-2.5 border border-slate-200 outline-none rounded-xl focus:border-indigo-500 text-xs transition"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-wider">Target Salary P.A.</label>
                <input
                  type="text"
                  required
                  value={prefTargetSalary}
                  onChange={(e) => setPrefTargetSalary(e.target.value)}
                  placeholder="e.g. $195,000/yr"
                  className="w-full p-2.5 border border-slate-200 outline-none rounded-xl focus:border-indigo-500 text-xs transition"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-wider">Target Workspace Location</label>
                <input
                  type="text"
                  required
                  value={prefTargetLoc}
                  onChange={(e) => setPrefTargetLoc(e.target.value)}
                  placeholder="e.g. San Francisco, CA (Hybrid)"
                  className="w-full p-2.5 border border-slate-200 outline-none rounded-xl focus:border-indigo-500 text-xs transition"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-wider">Target Execution Stage Timeline (Months)</label>
                <select
                  value={prefTimeline}
                  onChange={(e) => setPrefTimeline(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 outline-none rounded-xl focus:border-indigo-500 text-xs bg-white transition"
                >
                  <option value="3">3 Months (Intensive Bootup)</option>
                  <option value="6">6 Months (Strategic Pivot)</option>
                  <option value="12">12 Months (Full Evolution)</option>
                  <option value="24">24 Months (Executive Transformation)</option>
                </select>
              </div>

              <button
                type="submit"
                className="w-full py-2.5 mt-4 bg-indigo-600 hover:bg-indigo-700 active:scale-95 transition text-white text-xs font-bold rounded-xl flex items-center justify-center gap-1 shadow-sm shadow-indigo-600/20 cursor-pointer"
              >
                <CheckCircle className="h-4 w-4" />
                Commit Specifications to Profile
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
