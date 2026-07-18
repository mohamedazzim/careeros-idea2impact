import './globals.css';
import { Suspense } from 'react';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LoadingState } from '@/components/LoadingState';
import AppShell from '@/components/AppShell';
import FloatingRagChatbot from '@/components/rag/FloatingRagChatbot';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">
        <ErrorBoundary>
          <AppShell>
            <Suspense fallback={<LoadingState message="Loading page..." fullPage />}>
              {children}
            </Suspense>
          </AppShell>
          <FloatingRagChatbot />
        </ErrorBoundary>
      </body>
    </html>
  )
}
