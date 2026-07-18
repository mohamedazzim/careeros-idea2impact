"use client";

import { useCareerOS } from '@/hooks/useCareerOS';
import AlertRecordsView from '@/components/AlertRecordsView';

export default function JobAlertsPage() {
  const { token } = useCareerOS();
  return <AlertRecordsView token={token} />;
}
