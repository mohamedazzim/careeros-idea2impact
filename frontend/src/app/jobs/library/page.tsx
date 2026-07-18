"use client";

import { useCareerOS } from '@/hooks/useCareerOS';
import JobLibraryView from '@/components/JobLibraryView';

export default function JobLibraryPage() {
  const { token } = useCareerOS();
  return <JobLibraryView token={token} />;
}
