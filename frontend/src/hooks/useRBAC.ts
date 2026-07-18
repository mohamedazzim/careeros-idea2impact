import { useMemo } from 'react';
import { UserRole, canAccess, getNavSections } from '../lib/rbac';

interface UseRBACReturn {
  role: UserRole | null;
  canAccess: (path: string) => boolean;
  isAdmin: boolean;
  isRecruiter: boolean;
  navItems: Array<{ href: string; label: string; icon?: string }>;
}

export function useRBAC(role: UserRole | null): UseRBACReturn {
  return useMemo(() => ({
    role,
    canAccess: (path: string) => canAccess(path, role),
    isAdmin: role === 'Admin',
    isRecruiter: role === 'Recruiter' || role === 'Admin',
    navItems: getNavSections(role).flatMap((section) => section.items),
  }), [role]);
}
