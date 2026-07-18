interface Tab {
  id: string;
  label: string;
}

interface TabBarProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

export default function TabBar({ tabs, activeTab, onTabChange }: TabBarProps) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-slate-700 mb-4" aria-label="Section tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-controls={`tabpanel-${tab.id}`}
          onClick={() => onTabChange(tab.id)}
          onKeyDown={(e) => {
            const idx = tabs.findIndex(t => t.id === activeTab);
            if (e.key === 'ArrowRight') {
              e.preventDefault();
              const next = (idx + 1) % tabs.length;
              onTabChange(tabs[next].id);
            } else if (e.key === 'ArrowLeft') {
              e.preventDefault();
              const prev = (idx - 1 + tabs.length) % tabs.length;
              onTabChange(tabs[prev].id);
            }
          }}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 rounded-t ${
            activeTab === tab.id
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
