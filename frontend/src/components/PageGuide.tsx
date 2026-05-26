type GuideBlock = {
  title: string;
  points: string[];
};

type Props = {
  eyebrow?: string;
  title: string;
  summary: string;
  blocks: GuideBlock[];
};

export function PageGuide({ eyebrow = "Подсказка по разделу", title, summary, blocks }: Props) {
  return (
    <section className="page-guide">
      <div className="page-guide-header">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{summary}</p>
      </div>
      <div className="page-guide-grid">
        {blocks.map((block) => (
          <article key={block.title} className="guide-card">
            <h3>{block.title}</h3>
            <ul>
              {block.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}
