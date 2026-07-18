/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { User, UserPreferences, KnowledgeDoc, AnalysisRun } from '../types';
import { clearAuthSession, decodeTokenExpiry } from '@/lib/auth-session';

// Safe standard storage module to prevent "The operation is insecure" exception inside sandboxed/cross-origin frames
const safeStorage = {
  getItem: (key: string): string | null => {
    if (typeof window === 'undefined') {
      return null;
    }
    try {
      return localStorage.getItem(key);
    } catch (e) {
      console.warn('[Storage] Read error or blocked storage in sandboxed frame:', e);
      return null;
    }
  },
  setItem: (key: string, value: string): void => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      localStorage.setItem(key, value);
    } catch (e) {
      console.warn('[Storage] Write error or blocked storage in sandboxed frame:', e);
    }
  },
  removeItem: (key: string): void => {
    if (typeof window === 'undefined') {
      return;
    }
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn('[Storage] Remove error or blocked storage in sandboxed frame:', e);
    }
  }
};

const ACTIVE_DOC_STORAGE_KEY = 'careeros_active_doc_id';

export function useCareerOS() {
  const requestController = useRef<AbortController | null>(null);
  if (typeof window !== 'undefined' && !requestController.current) {
    requestController.current = new AbortController();
  }
  const [token, setToken] = useState<string | null>(() => safeStorage.getItem('careeros_token'));
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  
  const [documents, setDocuments] = useState<KnowledgeDoc[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(() => safeStorage.getItem(ACTIVE_DOC_STORAGE_KEY));
  const [preferences, setPreferences] = useState<UserPreferences>({
    alert_threshold: 85,
    notification_email: '',
    quiet_hours_start: '22:00',
    quiet_hours_end: '08:00'
  });

  const [activeRun, setActiveRun] = useState<AnalysisRun | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState<'hub' | 'jobs' | 'packages' | 'dashboard' | 'preferences' | 'interview'>('jobs');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  // Phase 3 App Packages
  const [packages, setPackages] = useState<any[]>([]);
  const [isGeneratingPackage, setIsGeneratingPackage] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const clearMessages = () => {
    setErrorMsg(null);
    setSuccessMsg(null);
  };

  useEffect(() => {
    if (!activeDocId) {
      safeStorage.removeItem(ACTIVE_DOC_STORAGE_KEY);
      return;
    }
    safeStorage.setItem(ACTIVE_DOC_STORAGE_KEY, activeDocId);
  }, [activeDocId]);

  const isSelectableResume = useCallback((doc: KnowledgeDoc | null | undefined) => {
    if (!doc) return false;
    if (!(doc.status === 'indexed' || doc.status === 'analyzed')) return false;
    return doc.is_selectable !== false;
  }, []);

  const headers = useCallback(() => {
    const defaultHeaders: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (token) {
      defaultHeaders['Authorization'] = `Bearer ${token}`;
    }
    return defaultHeaders;
  }, [token]);

  const normalizeAnalysisRun = useCallback((docId: string, runId: string, run: any): AnalysisRun => {
    const results = run?.results || {};
    const explainability = results.alignment_explainability || undefined;
    const overallScore = Number(explainability?.overall_score ?? results.overall_score ?? 0);
    const findings = Array.isArray(results.detail?.bullet_quality?.findings) ? results.detail.bullet_quality.findings : [];
    const components = Array.isArray(explainability?.components) ? explainability.components : [];
    const recommendations = [
      ...(Array.isArray(explainability?.improvement_suggestions) ? explainability.improvement_suggestions : []),
      !explainability && results.keyword_density < 70 ? 'Increase keyword coverage for the target role.' : null,
      !explainability && results.experience_depth < 70 ? 'Strengthen impact bullets with measurable outcomes.' : null,
      results.action_verb_strength < 70 ? 'Use stronger action verbs in key experience bullets.' : null,
      findings[0] || null,
    ].filter((item): item is string => Boolean(item));
    const strengths = components.length > 0
      ? components
          .filter((component: any) => Number(component.score || 0) >= 70)
          .map((component: any) => ({
            id: `${runId}-${component.key}-strength`,
            title: component.label,
            impact: Number(component.score || 0) >= 85 ? 'high' : 'medium',
            description: `${component.score}% score contributed ${component.contribution}/${component.max_contribution}. Evidence: ${(component.matched || component.evidence || []).slice(0, 3).join(', ') || 'No explicit evidence listed.'}`,
          }))
      : [
          {
            id: `${runId}-ats`,
            title: 'ATS compatibility',
            impact: (results.ats_compatibility || 0) >= 80 ? 'high' : 'medium',
            description: `Current ATS compatibility score is ${results.ats_compatibility || 0}.`,
          },
          {
            id: `${runId}-verbs`,
            title: 'Action verb strength',
            impact: (results.action_verb_strength || 0) >= 70 ? 'high' : 'medium',
            description: `Action verb strength is ${results.action_verb_strength || 0}.`,
          },
        ];
    const gaps = components.length > 0
      ? components
          .filter((component: any) => Number(component.score || 0) < 70 || (component.missing || []).length > 0)
          .map((component: any) => ({
            id: `${runId}-${component.key}-gap`,
            category: component.label,
            severity: Number(component.score || 0) < 40 ? 'high' as const : 'medium' as const,
            description: (component.missing || []).join(', ') || `${component.label} scored ${component.score}%.`,
            suggestion: recommendations.find((rec) => rec.toLowerCase().includes(String(component.key).split('_')[0])) || 'Add explicit evidence for this requirement and rerun analysis.',
          }))
      : findings.map((finding: string, index: number) => ({
          id: `${runId}-gap-${index}`,
          category: 'Resume quality',
          severity: 'medium' as const,
          description: finding,
          suggestion: recommendations[index] || 'Revise the related section and rerun analysis.',
        }));

    return {
      id: runId,
      doc_id: docId,
      job_description: run?.job_description || results.job_description || '',
      status: run?.status || 'idle',
      created_at: run?.started_at || new Date().toISOString(),
      error: run?.error || undefined,
      match_result: {
        match_score: overallScore,
        grade: explainability?.grade || (overallScore >= 85 ? 'A' : overallScore >= 70 ? 'B' : overallScore >= 55 ? 'C' : 'D'),
        summary: explainability
          ? `Weighted JD alignment from ${components.length} components. Formula: ${explainability.formula}. Resume quality baseline was ${results.resume_quality_score ?? overallScore}%.`
          : `ATS compatibility ${results.ats_compatibility || 0}, keyword density ${results.keyword_density || 0}, experience depth ${results.experience_depth || 0}.`,
        strengths,
        gaps,
        recommendations: recommendations.length > 0 ? recommendations : ['Review the detected weak areas and rerun analysis after edits.'],
        explainability,
        resume_quality_score: results.resume_quality_score,
      },
    };
  }, []);

  const apiClient = useCallback(async (endpoint: string, options: RequestInit = {}) => {
    // @ts-ignore
    const baseUrl = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000/api/v1';
    const finalHeaders = { ...headers(), ...options.headers };
    
    // Resilient fetch with retry logic for transient network failures
    let lastError: Error | null = null;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const response = await fetch(`${baseUrl}${endpoint}`, {
          ...options,
          headers: finalHeaders,
          signal: options.signal || requestController.current?.signal,
        });
        if ((response.status === 401 || response.status === 403) && !endpoint.startsWith('/auth/logout')) {
          await logout();
        }
        return response;
      } catch (error) {
        lastError = error as Error;
        if (lastError.name === 'AbortError' || requestController.current?.signal.aborted) {
          throw lastError;
        }
        if (attempt < 3) {
          await new Promise(resolve => setTimeout(resolve, 500 * attempt)); // Exponential backoff: 500ms, 1000ms
        }
      }
    }
    console.warn(`[API] Request failed after 3 attempts: ${endpoint}`, lastError);
    throw lastError;
  }, [headers]);

  const getApiErrorMessage = useCallback((data: any, status: number, fallback: string) => {
    if (status === 409) {
      return 'Account already exists. Please sign in.';
    }
    if (Array.isArray(data?.detail)) {
      const first = data.detail[0];
      const field = Array.isArray(first?.loc) ? first.loc.filter((part: any) => part !== 'body').join('.') : '';
      const message = first?.msg || first?.message;
      if (field && message) return `${field}: ${message}`;
      if (message) return message;
    }
    if (typeof data?.detail === 'string') return data.detail;
    if (typeof data?.message === 'string') return data.message;
    if (typeof data?.error === 'string') return data.error;
    return fallback;
  }, []);

  useEffect(() => {
    return () => requestController.current?.abort();
  }, []);

  const logout = useCallback(async () => {
    // Revoke tokens on server (fire-and-forget)
    try {
      await apiClient('/auth/logout', { method: 'POST' });
    } catch (_) {
      // Ignore network errors during logout
    }
    clearAuthSession();
    setToken(null);
    setCurrentUser(null);
    setUserRole(null);
    setDocuments([]);
    setActiveDocId(null);
    setActiveRun(null);
  }, [apiClient]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const tokenValue = safeStorage.getItem('careeros_token');
    const expiresAt = decodeTokenExpiry(tokenValue);
    if (!tokenValue || !expiresAt) return;

    const delay = expiresAt - Date.now();
    if (delay <= 0) {
      void logout();
      return;
    }

    const timeout = window.setTimeout(() => {
      void logout();
    }, delay);

    return () => window.clearTimeout(timeout);
  }, [logout, token]);

  const fetchUser = useCallback(async () => {
    try {
      const res = await apiClient('/auth/me');
      if (res.ok) {
        const u = await res.json();
        setCurrentUser(u);
        if (u.role) setUserRole(u.role);
      } else {
        logout();
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      console.error('Error fetching user', e);
    }
  }, [apiClient, logout]);

  const fetchPreferences = useCallback(async () => {
    try {
      const res = await apiClient('/user/preferences');
      if (res.ok) {
        const p = await res.json();
        setPreferences(p);
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      console.error('Error fetching preferences', e);
    }
  }, [apiClient]);

  const updatePreferences = async (newPrefs: Partial<UserPreferences>) => {
    try {
      const res = await apiClient('/user/preferences', {
        method: 'PUT',
        body: JSON.stringify(newPrefs)
      });
      if (res.ok) {
        const updated = await res.json();
        setPreferences(updated);
        setSuccessMsg('Preferences updated successfully!');
        return true;
      }
    } catch (e) {
      setErrorMsg('Failed to update preferences.');
    }
    return false;
  };

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await apiClient('/knowledge');
      if (res.ok) {
        const data = await res.json();
        const nextDocs = data.documents || [];
        setDocuments(nextDocs);
        const selectableDocs = nextDocs.filter((doc: KnowledgeDoc) => isSelectableResume(doc));
        if (selectableDocs.length === 0) {
          if (activeDocId) {
            setActiveDocId(null);
          }
        } else if (!activeDocId || !selectableDocs.some((doc: KnowledgeDoc) => doc.id === activeDocId)) {
          setActiveDocId(selectableDocs[0].id);
        }
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      console.error('Error loading documents', e);
    }
  }, [activeDocId, apiClient, isSelectableResume]);

  const fetchDocumentById = useCallback(async (docId: string) => {
    try {
      const res = await apiClient(`/knowledge/${docId}`);
      if (!res.ok) {
        return null;
      }
      const doc = await res.json();
      setDocuments((prev) => {
        const idx = prev.findIndex((d) => d.id === docId);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = { ...next[idx], ...doc };
          return next;
        }
        return [doc, ...prev];
      });
      return doc as KnowledgeDoc;
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return null;
      console.error('Error loading document detail', e);
      return null;
    }
  }, [apiClient]);

  const register = async (email: string, passwordString: string) => {
    clearMessages();
    try {
      const res = await apiClient('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: passwordString })
      });
      const data = await res.json();
      if (res.ok) {
        safeStorage.setItem('careeros_token', data.access_token);
        document.cookie = `careeros_token=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
        setToken(data.access_token);
        setSuccessMsg('Account registered successfully!');
        return true;
      } else {
        const message = getApiErrorMessage(data, res.status, 'Failed to register account');
        setErrorMsg(message);
        return message;
      }
    } catch (e) {
      const message = 'Network error occurred during registration.';
      setErrorMsg(message);
      return message;
    }
    return false;
  };

  const login = async (email: string, passwordString: string) => {
    clearMessages();
    try {
      const res = await apiClient('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: passwordString })
      });
      const data = await res.json();
      if (res.ok) {
        safeStorage.setItem('careeros_token', data.access_token);
        document.cookie = `careeros_token=${data.access_token}; path=/; max-age=86400; SameSite=Lax`;
        setToken(data.access_token);
        setSuccessMsg('Logged in successfully!');
        return true;
      } else {
        const message = getApiErrorMessage(data, res.status, 'Invalid credentials');
        setErrorMsg(message);
        return message;
      }
    } catch (e) {
      const message = 'Network error occurred during login.';
      setErrorMsg(message);
      return message;
    }
    return false;
  };

  const uploadResume = async (filename: string, content: string, fileBase64?: string) => {
    clearMessages();
    setIsUploading(true);
    try {
      const res = await apiClient('/knowledge/upload', {
        method: 'POST',
        body: JSON.stringify({ filename, content, doc_type: 'resume', file_base64: fileBase64 })
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg('Resume registered! Extraction and PII Masking pipeline triggered.');
        setActiveDocId(data.docId);
        // Start polling documents list to check indexing completion
        await pollDocState(data.docId);
        return data.docId;
      } else {
        setErrorMsg(data.error || 'Upload failed');
      }
    } catch (e) {
      setErrorMsg('Failed to process upload due to server error.');
    } finally {
      setIsUploading(false);
    }
    return null;
  };

  const deleteDoc = async (docId: string) => {
    try {
      const res = await apiClient(`/knowledge/${docId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setSuccessMsg('Document deleted from hub.');
        if (activeDocId === docId) {
          setActiveDocId(null);
        }
        fetchDocuments();
      }
    } catch (e) {
      setErrorMsg('Deletion failed.');
    }
  };

  const triggerRAGAnalysis = async (docId: string, jdText: string) => {
    clearMessages();
    setIsAnalyzing(true);
    try {
      const res = await apiClient(`/knowledge/${docId}/analyze`, {
        method: 'POST',
        body: JSON.stringify({ job_description: jdText })
      });
      const data = await res.json();
      if (res.ok) {
        // Poll for the analysis runs
        pollAnalysisRun(docId, data.runId);
        return true;
      } else {
        setErrorMsg(data.error || 'Analysis start failed.');
        setIsAnalyzing(false);
      }
    } catch (e) {
      setErrorMsg('Failed to run alignment pipeline.');
      setIsAnalyzing(false);
    }
    return false;
  };

  // Poll Document Pipeline state
  const pollDocState = async (docId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await apiClient(`/knowledge/${docId}`);
        if (res.ok) {
          const doc: KnowledgeDoc = await res.json();
          // Merge to documents list
          setDocuments(prev => {
            const idx = prev.findIndex(d => d.id === docId);
            if (idx >= 0) {
              const copy = [...prev];
              copy[idx] = doc;
              return copy;
            } else {
              return [doc, ...prev];
            }
          });

          if (doc.status === 'analyzed' || doc.status === 'failed') {
            clearInterval(interval);
          }
        }
      } catch (err) {
        console.error('Error polling doc status:', err);
      }

      if (attempts > 30) {
        clearInterval(interval); // Timeout after 1 minute
      }
    }, 2000);
  };

  // Poll Analysis pipeline state
  const pollAnalysisRun = async (docId: string, runId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await apiClient(`/knowledge/${docId}/score`);
        if (res.ok) {
          const data = await res.json();
          const targetRun = data.runs?.find((r: any) => r.runId === runId);
          if (targetRun) {
            setActiveRun(normalizeAnalysisRun(docId, runId, targetRun));
            if (targetRun.status === 'completed' || targetRun.status === 'failed') {
              clearInterval(interval);
              setIsAnalyzing(false);
              if (targetRun.status === 'completed') {
                setSuccessMsg('RAG alignment score calculated successfully!');
              } else {
                setErrorMsg(targetRun.error || 'Alignment pipeline failed.');
              }
            }
          }
        }
      } catch (err) {
        console.error('Error polling score status:', err);
      }

      if (attempts > 40) {
        clearInterval(interval);
        setIsAnalyzing(false);
        setErrorMsg('Analysis timed out.');
      }
    }, 2500);
  };

  // Phase 3 Package Operations
  const fetchPackages = useCallback(async () => {
    try {
      const res = await apiClient('/packages');
      if (res.ok) {
        const data = await res.json();
        setPackages(data.packages || []);
      }
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return;
      console.error('Failed to load packages', e);
    }
  }, [apiClient]);

  // Auto load User, Docs & Packages on load
  useEffect(() => {
    if (token) {
      fetchUser();
      fetchPreferences();
      fetchDocuments();
      fetchPackages();
    } else {
      // Unauthenticated state resets
      setCurrentUser(null);
      setDocuments([]);
      setActiveDocId(null);
      setPackages([]);
    }
  }, [token, fetchUser, fetchPreferences, fetchDocuments, fetchPackages]);

  const generatePackage = async (jobId: string | number) => {
    const coercedJobId = jobId != null ? String(jobId).trim() : '';
    if (!coercedJobId) {
      setErrorMsg('Please select a job before generating a package.');
      return null;
    }
    setIsGeneratingPackage(true);
    setErrorMsg(null);
    try {
      const res = await apiClient('/packages/generate', {
        method: 'POST',
        body: JSON.stringify({ job_id: coercedJobId })
      });
      if (!res.ok) {
        throw new Error('Could not trigger package generation pipeline.');
      }
      const data = await res.json();
      setSuccessMsg('Package drafting initiated under background LangGraph thread!');
      setActiveTab('packages');
      await fetchPackages();
      return data.package_id;
    } catch (e: any) {
      setErrorMsg(e.message || 'Package generation failed.');
      return null;
    } finally {
      setIsGeneratingPackage(false);
    }
  };

  const deletePackage = async (id: string) => {
    try {
      const res = await apiClient(`/packages/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setSuccessMsg('Package deleted successfully.');
        await fetchPackages();
      }
    } catch (e) {
      console.error('Error deleting package:', e);
    }
  };

  const regeneratePackage = async (id: string) => {
    try {
      const res = await apiClient(`/packages/${id}/regenerate`, {
        method: 'POST'
      });
      if (res.ok) {
        setSuccessMsg('Pipeline regeneration re-triggered successfully.');
        await fetchPackages();
      }
    } catch (e) {
      console.error('Error regenerating package:', e);
    }
  };

  return {
    token,
    currentUser,
    userRole,
    documents,
    activeDocId,
    setActiveDocId,
    preferences,
    updatePreferences,
    activeRun,
    setActiveRun,
    isUploading,
    isAnalyzing,
    activeTab,
    setActiveTab,
    errorMsg,
    setErrorMsg,
    successMsg,
    setSuccessMsg,
    clearMessages,
    register,
    login,
    logout,
    uploadResume,
    deleteDoc,
    fetchDocumentById,
    triggerRAGAnalysis,
    pollAnalysisRun,
    refreshDocs: fetchDocuments,
    
    // Phase 3 outputs
    packages,
    isGeneratingPackage,
    fetchPackages,
    generatePackage,
    deletePackage,
    regeneratePackage
  };
}
