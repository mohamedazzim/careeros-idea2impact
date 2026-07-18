/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useCallback } from 'react';
import { formatDateOnly, formatDateTimeLocal, formatTimeLocal } from '@/lib/datetime';

const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || '/api/v1';
import { 
  Check, 
  X, 
  Edit2, 
  Play, 
  Clock, 
  HelpCircle, 
  User, 
  MessageSquare, 
  ListFilter, 
  AlertTriangle, 
  ArrowRight, 
  RefreshCw, 
  BarChart2, 
  Bell, 
  FileText, 
  ShieldCheck,
  Sparkles,
  Info,
  Calendar,
  Layers,
  Send,
  Plus
} from 'lucide-react';
import { Approval, ApprovalAction, ApprovalHistory, ApprovalComment, ApprovalTemplate, ApprovalType, ApprovalStatus } from '../types';

interface HumanApprovalCenterViewProps {
  token?: string;
}

export default function HumanApprovalCenterView({ token }: HumanApprovalCenterViewProps) {
  // Safe authentication token mapping
  const activeToken = token || '';

  // State Management
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [stats, setStats] = useState<any>({
    pending: 0,
    approved: 0,
    rejected: 0,
    executed: 0,
    total: 0,
    approvalRate: 0,
    rejectionRate: 0,
    averageReviewTime: '0s',
    executionRate: 0
  });

  const [loading, setLoading] = useState(true);
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'approved' | 'rejected' | 'executed'>('all');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>('ALL');
  
  // Detail sidebar or view sub-elements
  const [selectedApprovalDetails, setSelectedApprovalDetails] = useState<{
    history: ApprovalHistory[];
    comments: ApprovalComment[];
    actions: ApprovalAction[];
  } | null>(null);

  // Creation forms and feedback helpers
  const [commentInput, setCommentInput] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [editContentText, setEditContentText] = useState('');
  const [auditNotes, setAuditNotes] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // New Draft Creation Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDraftType, setNewDraftType] = useState<ApprovalType>('LINKEDIN_POST');
  const [newDraftTitle, setNewDraftTitle] = useState('');
  const [newDraftSummary, setNewDraftSummary] = useState('');
  const [newDraftContent, setNewDraftContent] = useState('');

  // In-app notifications
  const [notifications, setNotifications] = useState<any[]>([]);
  const [showNotificationsDropdown, setShowNotificationsDropdown] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const [actionError, setActionError] = useState<string | null>(null);

  // Load overall workspace assets
  const loadWorkspaceData = useCallback(async () => {
    try {
      setLoading(true);
      const headers = { 'Authorization': `Bearer ${activeToken}`, 'Content-Type': 'application/json' };

      // 1. Load list
      const listRes = await fetch(`${baseUrl}/approvals`, { headers });
      const listJson = await listRes.json();
      if (listJson.approvals) {
        setApprovals(listJson.approvals);
      }

      // 2. Load stats
      const statsRes = await fetch(`${baseUrl}/approvals/stats`, { headers });
      const statsJson = await statsRes.json();
      setStats(statsJson);

      // 3. Load notifications
      const notifsRes = await fetch(`${baseUrl}/approvals/notifications`, { headers });
      const notifsJson = await notifsRes.json();
      if (notifsJson.notifications) {
        setNotifications(notifsJson.notifications);
        setUnreadCount(notifsJson.notifications.filter((n: any) => !n.read).length);
      }
    } catch (err) {
      console.error('Failed to load human approval center workspace assets', err);
    } finally {
      setLoading(false);
    }
  }, [activeToken]);

  useEffect(() => {
    loadWorkspaceData();
  }, [loadWorkspaceData]);

  // Handle explicit refresh
  const triggerRefresh = async () => {
    setIsRefreshing(true);
    await loadWorkspaceData();
    setIsRefreshing(false);
  };

  // Fetch individual item's audit tracking traces
  const fetchApprovalDetails = async (id: string, selectImmediately = false) => {
    try {
      const headers = { 'Authorization': `Bearer ${activeToken}` };
      const detailRes = await fetch(`${baseUrl}/approvals/${id}`, { headers });
      const detailJson = await detailRes.json();
      if (detailJson.approval) {
        setSelectedApprovalDetails({
          history: detailJson.history || [],
          comments: detailJson.comments || [],
          actions: detailJson.actions || []
        });
        if (selectImmediately) {
          setSelectedApproval(detailJson.approval);
          setEditContentText(detailJson.approval.payload_json.content);
          setEditMode(false);
          setAuditNotes('');
        }
      }
    } catch (error) {
      console.error('Failed to load audit specifications', error);
    }
  };

  // Click on active list row
  const handleSelectApproval = (item: Approval) => {
    fetchApprovalDetails(item.id, true);
  };

  // Submit Comments
  const submitComment = async () => {
    if (!selectedApproval || !commentInput.trim()) return;
    try {
      const headers = { 
        'Authorization': `Bearer ${activeToken}`,
        'Content-Type': 'application/json'
      };
      const res = await fetch(`${baseUrl}/approvals/${selectedApproval.id}/comment`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ comment: commentInput })
      });
      if (res.ok) {
        setCommentInput('');
        fetchApprovalDetails(selectedApproval.id);
      }
    } catch (err) {
      console.error('Failed to write comment', err);
    }
  };

  // Process Approval Action (Approve, Reject, Execute)
  const processApprovalAction = async (action: 'approve' | 'reject' | 'execute') => {
    if (!selectedApproval) return;
    try {
      const headers = { 
        'Authorization': `Bearer ${activeToken}`,
        'Content-Type': 'application/json'
      };
      const res = await fetch(`${baseUrl}/approvals/${selectedApproval.id}/${action}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ notes: auditNotes })
      });
      const data = await res.json();
      if (res.ok) {
        setAuditNotes('');
        setActionError(null);
        await loadWorkspaceData();
        // Refresh details
        fetchApprovalDetails(selectedApproval.id, true);
      } else {
        setActionError(data.error || `Failed to ${action} draft`);
      }
    } catch (e) {
      console.error('Action execution failed', e);
      setActionError('Action execution failed due to network error');
    }
  };

  // Save edits onto the pending content
  const saveEdits = async () => {
    if (!selectedApproval) return;
    try {
      const headers = { 
        'Authorization': `Bearer ${activeToken}`,
        'Content-Type': 'application/json'
      };
      const res = await fetch(`${baseUrl}/approvals/${selectedApproval.id}/edit`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ content: editContentText })
      });
      if (res.ok) {
        setEditMode(false);
        await loadWorkspaceData();
        fetchApprovalDetails(selectedApproval.id, true);
      }
    } catch (error) {
      console.error('Failed to update content', error);
    }
  };

  // Create an immediate custom approval draft item for review
  const handleCreateDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDraftTitle || !newDraftContent) return;

    try {
      const headers = { 
        'Authorization': `Bearer ${activeToken}`,
        'Content-Type': 'application/json'
      };
      const response = await fetch(`${baseUrl}/approvals`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          approval_type: newDraftType,
          title: newDraftTitle,
          summary: newDraftSummary || `Candidate requested custom compiled ${newDraftType}`,
          content: newDraftContent
        })
      });

      if (response.ok) {
        setShowCreateModal(false);
        setNewDraftTitle('');
        setNewDraftSummary('');
        setNewDraftContent('');
        await loadWorkspaceData();
      }
    } catch (error) {
      console.error('Failed to create custom gate draft', error);
    }
  };

  // Mark all notifications read
  const markNotificationsRead = async () => {
    try {
      const headers = { 'Authorization': `Bearer ${activeToken}` };
      await fetch(`${baseUrl}/approvals/notifications/read`, { method: 'POST', headers });
      setUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (error) {
      console.error('Failed to mark read', error);
    }
  };

  // Filters application
  const filteredApprovals = approvals.filter(item => {
    // Tab filters mapping
    const tabMatch = activeTab === 'all' || item.status === activeTab;
    // Type filters mapping
    const typeMatch = selectedTypeFilter === 'ALL' || item.approval_type === selectedTypeFilter;
    return tabMatch && typeMatch;
  });

  const getStatusBadge = (status: ApprovalStatus) => {
    switch (status) {
      case 'pending':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
          <Clock className="w-3.5 h-3.5 animate-pulse" /> Pending Review
        </span>;
      case 'approved':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
          <Check className="w-3.5 h-3.5" /> Approved
        </span>;
      case 'rejected':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200">
          <X className="w-3.5 h-3.5" /> Rejected
        </span>;
      case 'executed':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-800 border border-indigo-200">
          <Play className="w-3.5 h-3.5" /> Executed
        </span>;
      case 'archived':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-200">
          Archived
        </span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-50 text-slate-800 border border-slate-200">
          {status}
        </span>;
    }
  };

  const getApprovalTypeBadge = (type: ApprovalType) => {
    switch (type) {
      case 'LINKEDIN_POST':
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-blue-50 text-blue-700 border border-blue-100">LinkedIn Post</span>;
      case 'RECRUITER_MESSAGE':
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-teal-50 text-teal-700 border border-teal-100">Recruiter DM</span>;
      case 'HIRING_MANAGER_MESSAGE':
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-violet-50 text-violet-700 border border-violet-100">Hiring Mgr msg</span>;
      case 'APPLICATION_PACKAGE':
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-orange-50 text-orange-700 border border-orange-100">App Package</span>;
      case 'EMAIL':
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-100 text-slate-700">Outbound Email</span>;
      case 'PHONE_ALERT':
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-amber-50 text-amber-700">Phone Alert</span>;
      default:
        return <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-100 text-slate-700">{type}</span>;
    }
  };

  return (
    <div className="space-y-6" id="human_approval_workspace">
      {/* Dynamic Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-emerald-50 border border-emerald-200">
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
            </span>
            <h1 className="text-xl font-display font-bold text-slate-900 tracking-tight" id="header_title_approval">
              Human-in-the-Loop Approval Center
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-xl">
            Enterprise Governance Protocol: All AI outbound tasks (LinkedIn posts, Recruiter reaches, applications) enter this secure queue. No automated publish occurs without explicit human audit.
          </p>
        </div>

        <div className="flex items-center gap-2 self-stretch md:self-auto justify-end">
          {/* Notifications Center */}
          <div className="relative">
            <button 
              onClick={() => {
                setShowNotificationsDropdown(!showNotificationsDropdown);
                if (!showNotificationsDropdown && unreadCount > 0) {
                  markNotificationsRead();
                }
              }}
              className="relative p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors flex items-center justify-center text-slate-600"
              title="State Alerts History"
              id="notif_bell_btn"
            >
              <Bell className="w-4.5 h-4.5" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white leading-none">
                  {unreadCount}
                </span>
              )}
            </button>

            {/* Notifications Dropdown */}
            {showNotificationsDropdown && (
              <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto bg-white border border-slate-200/80 rounded-xl shadow-lg z-50 py-2 divide-y divide-slate-100 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="px-4 py-2 flex justify-between items-center bg-slate-50">
                  <span className="text-xs font-bold text-slate-700">Agent Output Alerts</span>
                  <span className="text-[10px] bg-slate-200/60 px-1.5 py-0.5 rounded text-slate-500 font-mono">Celery Sync</span>
                </div>
                {notifications.length === 0 ? (
                  <div className="px-4 py-6 text-center text-xs text-slate-400">
                    No recent pipeline gate interrupts registered!
                  </div>
                ) : (
                  notifications.map(n => (
                    <div key={n.id} className={`px-4 py-2.5 hover:bg-slate-50 transition-colors ${!n.read ? 'bg-amber-50/20' : ''}`}>
                      <div className="flex justify-between items-start">
                        <p className="text-xs font-semibold text-slate-800">{n.title}</p>
                        <span className="text-[9px] text-slate-400">{formatTimeLocal(n.created_at)}</span>
                      </div>
                      <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <button
            onClick={triggerRefresh}
            className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-all flex items-center gap-1.5 text-xs font-medium"
            id="refresh_btn_approval"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3.5 py-1.5 rounded-xl bg-slate-900 border border-slate-950 hover:bg-slate-800 text-white font-medium text-xs transition-all flex items-center gap-1.5 shadow-sm"
            id="new_simulation_btn"
          >
            <Plus className="w-4 h-4" />
            Build Outbound Draft
          </button>
        </div>
      </div>

      {/* Analytics Dashboard Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" id="stats_dashboard_grid">
        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs hover:border-slate-300 transition-all">
          <div className="flex justify-between items-start">
            <span className="text-slate-400 text-xs font-medium tracking-tight">Pending Review</span>
            <span className="p-1 px-2 rounded-sm bg-amber-50 text-amber-600 font-mono text-[10px] border border-amber-100">Safety Hold</span>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-display text-slate-900">{stats.pending}</span>
            <span className="text-[10px] text-slate-500">active hooks</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs hover:border-slate-300 transition-all">
          <div className="flex justify-between items-start">
            <span className="text-slate-400 text-xs font-medium tracking-tight">Approved Rate</span>
            <span className="p-1 px-2 rounded-sm bg-emerald-50 text-emerald-600 font-mono text-[10px] border border-emerald-100">Quality</span>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-display text-slate-900">{stats.approvalRate}%</span>
            <span className="text-[10px] text-slate-500">cumulative</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs hover:border-slate-300 transition-all">
          <div className="flex justify-between items-start">
            <span className="text-slate-400 text-xs font-medium tracking-tight">Rejection Rate</span>
            <span className="p-1 px-2 rounded-sm bg-rose-50 text-rose-600 font-mono text-[10px] border border-rose-100">Refinements</span>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-display text-slate-900">{stats.rejectionRate}%</span>
            <span className="text-[10px] text-slate-500">rejected draft</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs hover:border-slate-300 transition-all">
          <div className="flex justify-between items-start">
            <span className="text-slate-400 text-xs font-medium tracking-tight">Execution Success</span>
            <span className="p-1 px-2 rounded-sm bg-indigo-50 text-indigo-600 font-mono text-[10px] border border-indigo-100">Outbound</span>
          </div>
          <div className="mt-2.5 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-display text-slate-900">{stats.executionRate}%</span>
            <span className="text-[10px] text-slate-500">dispatched lists</span>
          </div>
        </div>
      </div>

      {/* Main Workspace Layout (Two columns: Left Queue list, Right Detail Workspace) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6" id="workspace_main_elements">
        
        {/* Left Hand: Filtered Queue Panel */}
        <div className="xl:col-span-5 space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
            
            {/* Tab controls */}
            <div className="border-b border-slate-100">
              <div className="flex p-2 gap-1 overflow-x-auto select-none scrollbar-none">
                {(['all', 'pending', 'approved', 'rejected', 'executed'] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize whitespace-nowrap transition-all ${activeTab === tab ? 'bg-slate-900 text-white' : 'text-slate-504 hover:text-slate-700 hover:bg-slate-50'}`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            {/* Filter controls */}
            <div className="p-3 bg-slate-50 border-b border-slate-100 flex flex-wrap gap-2 items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium font-sans">
                <ListFilter className="w-3.5 h-3.5 text-slate-400" />
                Channels Filter
              </div>
              <select
                value={selectedTypeFilter}
                onChange={(e) => setSelectedTypeFilter(e.target.value)}
                className="bg-white border border-slate-200 text-xs rounded-lg px-2 py-1 text-slate-700 focus:ring-1 focus:ring-slate-900 focus:outline-none"
              >
                <option value="ALL">All Outbound Actions</option>
                <option value="LINKEDIN_POST">LinkedIn Posts</option>
                <option value="RECRUITER_MESSAGE">Recruiter Chats</option>
                <option value="HIRING_MANAGER_MESSAGE">Hiring Mgr DMs</option>
                <option value="APPLICATION_PACKAGE">Application Packages</option>
              </select>
            </div>

            {/* List entries */}
            <div className="divide-y divide-slate-100 max-h-[580px] overflow-y-auto" id="governed_approvals_list">
              {loading ? (
                <div className="p-8 text-center text-xs text-slate-400">
                  Loading secure queue...
                </div>
              ) : filteredApprovals.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-400 space-y-2">
                  <Info className="w-8 h-8 mx-auto stroke-1" />
                  <p>No outbound triggers match filter criteria.</p>
                </div>
              ) : (
                filteredApprovals.map(item => (
                  <div
                    key={item.id}
                    onClick={() => handleSelectApproval(item)}
                    className={`p-4 cursor-pointer transition-all flex flex-col gap-2 border-l-4 ${selectedApproval?.id === item.id ? 'bg-slate-50/80 border-slate-900' : 'hover:bg-slate-50/50 border-transparent'}`}
                  >
                    <div className="flex justify-between items-start gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          {getApprovalTypeBadge(item.approval_type)}
                          <span className="text-[10px] text-slate-400 font-mono">ID: {item.id}</span>
                        </div>
                        <h3 className="text-xs font-bold text-slate-800 line-clamp-1 mt-1">
                          {item.title}
                        </h3>
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        {getStatusBadge(item.status)}
                        <span className="text-[9px] text-slate-400 font-mono">
                          {formatDateOnly(item.created_at)}
                        </span>
                      </div>
                    </div>

                    <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5 font-sans leading-relaxed">
                      {item.summary}
                    </p>

                    <div className="flex justify-between items-center text-[10px] text-slate-400 border-t border-slate-100/50 pt-2 mt-1">
                      <span className="flex items-center gap-1">
                        <User className="w-3 h-3" /> Gen by: <strong className="text-slate-500 font-medium">{item.payload_json.generated_by || 'Unknown'}</strong>
                      </span>
                      {item.payload_json.metadata?.confidence && (
                        <span className="bg-slate-100 text-slate-600 text-[9px] px-1.5 py-0.2 rounded font-mono font-bold">
                          AI confidence: {item.payload_json.metadata.confidence}%
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="p-3 bg-slate-50 border-t border-slate-100 text-center">
              <span className="text-[10px] text-slate-400 font-mono">
                Total Loaded Gate Intercepts: {approvals.length} records
              </span>
            </div>
          </div>
        </div>

        {/* Right Hand: Detailed Workspace Panel split into segments */}
        <div className="xl:col-span-7">
          {selectedApproval ? (
            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden flex flex-col" id="approval_detail_space">
              
              {/* Card Header information */}
              <div className="p-5 border-b border-slate-100 bg-slate-50/50">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {getApprovalTypeBadge(selectedApproval.approval_type)}
                      <span className="text-[10px] bg-slate-100 px-2 py-0.5 rounded font-mono text-slate-500">Status: {selectedApproval.status.toUpperCase()}</span>
                    </div>
                    <h2 className="text-sm font-display font-bold text-slate-900 tracking-tight">
                      {selectedApproval.title}
                    </h2>
                  </div>

                  <div className="shrink-0">
                    {getStatusBadge(selectedApproval.status)}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-200/60 text-[10px] text-slate-500 font-sans">
                  <div>
                    <span className="text-slate-400">Interrupt State ID</span>
                    <p className="font-mono text-slate-700 mt-0.5 font-bold">{selectedApproval.id}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">LangSmith Trace ID</span>
                    <p className="font-mono text-slate-700 mt-0.5 font-bold">{selectedApproval.payload_json.trace_id || 'untraced'}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Interruption Timestamp</span>
                    <p className="font-mono text-slate-700 mt-0.5">{formatDateTimeLocal(selectedApproval.created_at)}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">Model Provider Target</span>
                    <p className="font-mono text-slate-700 mt-0.5">{selectedApproval.payload_json.metadata?.model || 'Unavailable'}</p>
                  </div>
                </div>
              </div>

              {/* Central draft representation & edit block */}
              <div className="p-5 space-y-4 flex-1">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5 font-display">
                    <FileText className="w-4 h-4 text-slate-500" />
                    AI-Generated Draft Payload Action Content
                  </span>
                  {selectedApproval.status === 'pending' && (
                    <button
                      onClick={() => {
                        setEditMode(!editMode);
                        if (!editMode) setEditContentText(selectedApproval.payload_json.content);
                      }}
                      className="px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-50 text-[10px] font-bold text-slate-600 transition-all flex items-center gap-1"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                      {editMode ? 'Cancel Edit' : 'Edit Draft'}
                    </button>
                  )}
                </div>

                {editMode ? (
                  <div className="space-y-3">
                    <textarea
                      value={editContentText}
                      onChange={(e) => setEditContentText(e.target.value)}
                      rows={8}
                      className="w-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-slate-900 focus:outline-none"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setEditMode(false)}
                        className="px-3 py-1 text-xs font-semibold rounded-lg bg-white border border-slate-200 hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={saveEdits}
                        className="px-3 py-1 text-xs font-semibold rounded-lg bg-slate-900 text-white border border-slate-950 hover:bg-slate-800"
                        id="save_edits_btn"
                      >
                        Save Draft Updates
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="relative group bg-slate-900 rounded-xl p-4 border border-slate-950 shadow-inner max-h-72 overflow-y-auto">
                    <div className="absolute top-2 right-2 bg-slate-800 hover:bg-slate-700 text-[10px] font-mono font-bold text-slate-400 border border-slate-700 px-1.5 py-0.5 rounded pointer-events-none select-none">
                      UTF-8 PLAIN
                    </div>
                    <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap leading-relaxed select-text pr-8">
                      {selectedApproval.payload_json.content || 'None'}
                    </pre>
                  </div>
                )}

                {/* AI Safety Explanation Box */}
                <div className="p-3.5 rounded-xl bg-orange-50/40 border border-orange-100 flex gap-2.5 text-xs text-amber-900/90 leading-relaxed font-sans">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Interrupt Trigger Summary:</span> The Outbound Execution pipeline halted because this message is bound to execute an external publish event. Human verification blocks any unapproved actions.
                  </div>
                </div>

                {/* Actions Panel (Approve, Reject, Execute) */}
                {selectedApproval.status === 'pending' && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-xs font-bold text-slate-700 block">
                        Add Audit Evaluation Notes (Optional logger context)
                      </label>
                      <input
                        type="text"
                        placeholder="e.g., Looks aligned with stripe qualifications. Standard draft safe."
                        value={auditNotes}
                        onChange={(e) => setAuditNotes(e.target.value)}
                        className="w-full text-xs p-2 bg-white border border-slate-200 rounded-lg focus:ring-1 focus:ring-slate-900 focus:outline-none"
                      />
                    </div>

                    <div className="flex flex-col sm:flex-row gap-2 justify-end items-end sm:items-center">
                      {actionError && (
                        <div className="text-xs text-rose-600 font-semibold mr-auto">
                          {actionError}
                        </div>
                      )}
                      <button
                        onClick={() => processApprovalAction('reject')}
                        className="px-4 py-2 font-display font-bold text-xs rounded-xl bg-rose-50 hover:bg-rose-100/80 border border-rose-200 text-rose-800 transition-all flex items-center gap-1.5 shadow-xs"
                        id="reject_draft_btn"
                      >
                        <X className="w-4 h-4" /> Reject Draft
                      </button>

                      <button
                        onClick={() => processApprovalAction('approve')}
                        className="px-4 py-2 font-display font-bold text-xs rounded-xl bg-emerald-600 hover:bg-emerald-500 border border-emerald-700 text-white transition-all flex items-center gap-1.5 shadow-sm"
                        id="approve_draft_btn"
                      >
                        <Check className="w-4 h-4" /> Approve Draft
                      </button>
                    </div>
                  </div>
                )}

                {selectedApproval.status === 'approved' && (
                  <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-xs font-bold text-slate-800">Approved for Dispatch</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">This asset passed candidate verification gate. It is primed for outbound transmission lines.</p>
                    </div>
                    <button
                      onClick={() => processApprovalAction('execute')}
                      className="px-4 py-2 font-display font-bold text-xs rounded-xl bg-slate-900 border border-slate-950 hover:bg-slate-800 text-white transition-all flex items-center gap-1.5 shadow-sm shrink-0"
                      id="execute_action_btn"
                    >
                      <Play className="w-3.5 h-3.5" /> Execute & Send
                    </button>
                  </div>
                )}

                {selectedApproval.status === 'executed' && (
                  <div className="bg-indigo-50/50 border border-indigo-100 p-3.5 rounded-xl flex items-start gap-2.5 text-xs text-indigo-900 leading-relaxed font-sans">
                    <Sparkles className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold">Transmission Complete:</span> This outbound item was successfully processed by background worker tasks on the celery channel. Relayed seamlessly to outer API vectors.
                    </div>
                  </div>
                )}
              </div>

              {/* History Audit Log Trails + Comments Split Tabs */}
              <div className="border-t border-slate-100 p-5 bg-slate-50/40">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  
                  {/* Audit Logs Trail */}
                  <div className="space-y-3">
                    <span className="text-xs font-bold text-slate-700 block tracking-tight font-display">
                      Immutable Audit Trail Logs
                    </span>
                    <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                      {selectedApprovalDetails?.history.length === 0 ? (
                        <p className="text-[11px] text-slate-400">No logs registered yet.</p>
                      ) : (
                        selectedApprovalDetails?.history.map(h => (
                          <div key={h.id} className="p-2.5 rounded-lg bg-white border border-slate-100 text-[10px] font-sans leading-relaxed space-y-1 shadow-2xs">
                            <div className="flex justify-between items-center text-[9px] text-slate-400 font-mono">
                              <span>By: {h.changed_by}</span>
                              <span>{formatDateTimeLocal(h.created_at)}</span>
                            </div>
                            <p className="text-slate-700">
                              State update: <strong className="font-semibold text-slate-800 font-mono capitalize">{h.old_status}</strong> <ArrowRight className="inline w-3 h-3 mx-0.5 text-slate-400" /> <strong className="font-semibold text-slate-900 font-mono capitalize">{h.new_status}</strong>
                            </p>
                            {h.reason && <p className="text-slate-500 bg-slate-50 p-1 rounded italic text-[9px]">{h.reason}</p>}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Dynamic Comments System */}
                  <div className="space-y-3 flex flex-col justify-between">
                    <div>
                      <span className="text-xs font-bold text-slate-700 block tracking-tight font-display">
                        Governance Advisory Comments
                      </span>
                      <div className="space-y-2 mt-2 max-h-32 overflow-y-auto pr-1">
                        {selectedApprovalDetails?.comments.length === 0 ? (
                          <p className="text-[11px] text-slate-400">No review comments recorded for this audit.</p>
                        ) : (
                          selectedApprovalDetails?.comments.map(c => (
                            <div key={c.id} className="p-2 rounded-lg bg-slate-100 border border-slate-200/40 text-[10px] font-sans">
                              <span className="font-medium text-slate-600 block text-[9px]">{c.user_id} @ {formatTimeLocal(c.created_at)}</span>
                              <p className="text-slate-700 mt-0.5">{c.comment}</p>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    <div className="flex gap-1.5 mt-3 pt-2">
                      <input
                        type="text"
                        placeholder="Add review feedback..."
                        value={commentInput}
                        onChange={(e) => setCommentInput(e.target.value)}
                        className="flex-1 text-xs p-1.5 bg-white border border-slate-200 rounded-lg focus:ring-1 focus:ring-slate-900 focus:outline-none"
                      />
                      <button
                        onClick={submitComment}
                        className="px-2.5 py-1.5 bg-slate-900 border border-slate-950 text-white rounded-lg hover:bg-slate-800 transition-colors flex items-center justify-center shrink-0"
                      >
                        <Send className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                </div>
              </div>

            </div>
          ) : (
            <div className="bg-slate-50/50 rounded-2xl border-2 border-dashed border-slate-200 p-24 text-center space-y-3">
              <ShieldCheck className="w-12 h-12 text-slate-300 mx-auto" />
              <div className="space-y-1">
                <p className="text-xs font-bold text-slate-700 font-display">Governance Detail Canvas</p>
                <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
                  Select an outbound item from target approvals queue leftward to inspect generation structures, details, traces, and trigger manual override decisions.
                </p>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* Creation Modal for Simulating Outbound Action creation */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200/80 rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="px-5 py-4 bg-slate-50 border-b border-slate-100 flex justify-between items-center">
              <span className="text-xs font-bold text-slate-800 font-display flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-emerald-600" />
                Simulate Agent Outbound Interrupt
              </span>
              <button 
                onClick={() => setShowCreateModal(false)}
                className="p-1 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateDraft} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700 block">Outbound Channel Action Type</label>
                <select
                  value={newDraftType}
                  onChange={(e) => setNewDraftType(e.target.value as ApprovalType)}
                  className="w-full bg-white border border-slate-200 text-xs rounded-xl p-2.5 focus:ring-1 focus:ring-slate-900 focus:outline-none"
                >
                  <option value="LINKEDIN_POST">LINKEDIN_POST (Syllabus summary post)</option>
                  <option value="RECRUITER_MESSAGE">RECRUITER_MESSAGE (Inbound/outbound dm)</option>
                  <option value="HIRING_MANAGER_MESSAGE">HIRING_MANAGER_MESSAGE (Direct follow up)</option>
                  <option value="APPLICATION_PACKAGE">APPLICATION_PACKAGE (Package review)</option>
                  <option value="EMAIL">EMAIL (Outreach direct message)</option>
                  <option value="PHONE_ALERT">PHONE_ALERT (Emergency notification)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700 block">Draft Title name</label>
                <input
                  type="text"
                  placeholder="e.g., LinkedIn outreach template Stripe position"
                  value={newDraftTitle}
                  onChange={(e) => setNewDraftTitle(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-1 focus:ring-slate-900 focus:outline-none"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700 block">Summary context description</label>
                <input
                  type="text"
                  placeholder="e.g., Custom generated context matching striped recruiter priorities"
                  value={newDraftSummary}
                  onChange={(e) => setNewDraftSummary(e.target.value)}
                  className="w-full text-xs p-2.5 border border-slate-200 rounded-xl focus:ring-1 focus:ring-slate-900 focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700 block">AI Generated Outreach Body Content</label>
                <textarea
                  placeholder="Provide simulated draft message text here..."
                  value={newDraftContent}
                  onChange={(e) => setNewDraftContent(e.target.value)}
                  rows={5}
                  className="w-full text-xs font-mono p-2.5 border border-slate-200 rounded-xl focus:ring-1 focus:ring-slate-900 focus:outline-none"
                  required
                />
              </div>

              <div className="flex gap-2 justify-end pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-xs font-semibold rounded-xl bg-white border border-slate-200 hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-900 text-white hover:bg-slate-800 border border-slate-950 transition-colors"
                >
                  Confirm & Interrupt Outbound
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
