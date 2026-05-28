import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export type GuideBlock = {
  title: string;
  points: string[];
};

export type PageGuideData = {
  eyebrow?: string;
  title: string;
  summary: string;
  blocks: GuideBlock[];
};

type PageGuideContextValue = {
  guide: PageGuideData | null;
  setGuide: (guide: PageGuideData | null) => void;
};

const PageGuideContext = createContext<PageGuideContextValue | null>(null);

export function PageGuideProvider({ children }: { children: ReactNode }) {
  const [guide, setGuide] = useState<PageGuideData | null>(null);
  const value = useMemo(() => ({ guide, setGuide }), [guide]);

  return <PageGuideContext.Provider value={value}>{children}</PageGuideContext.Provider>;
}

export function usePageGuide() {
  const context = useContext(PageGuideContext);
  if (!context) {
    throw new Error("usePageGuide must be used within PageGuideProvider");
  }
  return context;
}
