export type UserRole = 'Admin' | 'User' | 'Recruiter' | 'Moderator';

export interface AuthUser {
  sub: string;
  role: UserRole;
  email?: string;
  full_name?: string;
}

const PUBLIC_ROUTES = ['/login', '/forgot-password', '/reset-password'];

const ADMIN_ROUTES = ['/ops', '/troubleshoot', '/skill-graph'];
const RECRUITER_ROUTES = ['/approvals'];
export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some(r => pathname === r || pathname.startsWith(r));
}

export function canAccess(pathname: string, role: UserRole | null): boolean {
  if (!role) return isPublicRoute(pathname);

  if (ADMIN_ROUTES.some(route => pathname.startsWith(route))) {
    return (role as string) === 'Admin';
  }

  if (RECRUITER_ROUTES.some(route => pathname.startsWith(route))) {
    return (role as string) === 'Admin' || (role as string) === 'Recruiter';
  }

  return true;
}

export type NavSection = {
  title: string;
  items: Array<{ href: string; label: string; icon?: string }>;
};

export function getNavSections(role: UserRole | null): NavSection[] {
  const primary: NavSection = {
    title: 'Main',
    items: [
    { href: '/dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
    { href: '/jobs', label: 'Jobs', icon: 'Briefcase' },
    { href: '/packages', label: 'Packages', icon: 'Package' },
    { href: '/knowledge', label: 'Knowledge', icon: 'BookOpen' },
    { href: '/account', label: 'Account', icon: 'User' },
    ],
  };

  const featureItems: NavSection['items'] = [
    { href: '/roadmap', label: 'Roadmap', icon: 'Map' },
    { href: '/interview', label: 'Interview', icon: 'Mic' },
    { href: '/coach', label: 'Coach', icon: 'GraduationCap' },
    { href: '/command-center', label: 'Command Center', icon: 'Activity' },
    { href: '/preferences', label: 'Preferences', icon: 'Settings' },
    { href: '/demo-rag', label: 'Demo RAG', icon: 'BookOpen' },
    { href: '/opportunities', label: 'Opportunities', icon: 'Zap' },
    { href: '/orchestration', label: 'Orchestration', icon: 'GitBranch' },
  ];

  if (role === 'Admin' || role === 'Recruiter') {
    featureItems.push({ href: '/approvals', label: 'Approvals', icon: 'CheckCircle' });
    featureItems.push({ href: '/evaluation', label: 'Evaluation', icon: 'BarChart' });
  }

  const sections: NavSection[] = [primary, { title: 'Future Enhance Sections', items: featureItems }];

  if (role === 'Admin') {
    sections.push({
      title: 'Admin',
      items: [
        { href: '/ops', label: 'Ops Center', icon: 'Shield' },
        { href: '/skill-graph', label: 'Skill Graph', icon: 'GitBranch' },
      ],
    });
  }

  return sections;
}
