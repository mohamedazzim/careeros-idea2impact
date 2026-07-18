"use client";
import { useEffect, useState } from "react";
import { Brain, Target, Sparkles } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function CareerCoachDashboard() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    const token = localStorage.getItem("careeros_token") || "";
    fetch(`${API_BASE}/career-coach`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.json() : Promise.reject(response.status))
      .then(setData)
      .catch(() => setData({ plans: [], goals: [], recommendations: [] }));
  }, []);
  return (
    <section className="mx-auto max-w-7xl p-4 lg:p-8">
      <h1 className="flex items-center gap-3 text-2xl font-bold"><Brain className="text-cyan-400" />Career Coach Dashboard</h1>
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <Panel icon={<Sparkles className="h-4 w-4" />} title="Coaching Plans" items={data?.plans} empty="No active coaching plans" />
        <Panel icon={<Target className="h-4 w-4" />} title="Career Goals" items={data?.goals} empty="No active career goals" />
        <Panel icon={<Brain className="h-4 w-4" />} title="Recommendations" items={data?.recommendations} empty="No current recommendations" />
      </div>
    </section>
  );
}

function Panel({ icon, title, items, empty }: { icon: React.ReactNode; title: string; items?: any[]; empty: string }) {
  return <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
    <p className="flex items-center gap-2 text-xs font-semibold uppercase text-cyan-300">{icon}{title}</p>
    {items?.length ? items.slice(0, 3).map((item) => <div key={item.id} className="mt-3 border-t border-slate-800 pt-3">
      <p className="text-sm font-medium text-slate-100">{item.title}</p><p className="mt-1 text-xs text-slate-400">{item.description || item.status}</p>
    </div>) : <p className="mt-3 text-xs text-slate-500">{empty}</p>}
  </div>;
}
