"use client";
import HumanApprovalCenterView from '@/components/HumanApprovalCenterView';
import { useCareerOS } from '@/hooks/useCareerOS';

export default function ApprovalsPage() {
  const { token } = useCareerOS();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <HumanApprovalCenterView token={token || undefined} />
    </div>
  );
}
