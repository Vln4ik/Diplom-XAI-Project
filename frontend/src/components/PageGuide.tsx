import { useEffect } from "react";

import { type PageGuideData, usePageGuide } from "./PageGuideContext";

export function PageGuide({ eyebrow = "Подсказка по разделу", title, summary, blocks }: PageGuideData) {
  const { setGuide } = usePageGuide();

  useEffect(() => {
    const guide = { eyebrow, title, summary, blocks };
    setGuide(guide);
    return () => setGuide(null);
  }, [blocks, eyebrow, setGuide, summary, title]);

  return null;
}
