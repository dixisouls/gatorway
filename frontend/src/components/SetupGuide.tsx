import { Sparkle } from "./ui/Sparkle";

const copy = {
  transcript: { title: "Every credit counts.", text: "Your transcript gives your plan a starting point. We’ll recognize the courses you’ve already taken.", note: "An unofficial SFSU transcript works. Just save it as a PDF." },
  program: { title: "A clear destination.", text: "Your program’s published roadmap is the foundation. Find your degree, then choose the roadmap that fits.", note: "Use the filters to explore undergraduate, graduate, minor, and certificate programs." },
  interest: { title: "Room for your curiosity.", text: "A degree is more than its requirements. Tell us what you want to explore, and we’ll find electives that connect.", note: "A topic, a career, or a big idea. You can change your interest and refresh your picks later." },
};

export function SetupGuide({ step }: { step: keyof typeof copy }) {
  const content = copy[step];
  return (
    <aside className="setup-guide">
      <div className="guide-illustration" aria-hidden="true">
        <span className="guide-orbit orbit-one" /><span className="guide-orbit orbit-two" />
        <span className="guide-center"><Sparkle size={28} /></span>
        <span className="guide-node node-one">✓</span><span className="guide-node node-two">↗</span>
      </div>
      <p className="eyebrow">A plan that fits you</p>
      <h2>{content.title}</h2>
      <p>{content.text}</p>
      <ol className="guide-path"><li><span>✓</span> Your progress</li><li><span>↗</span> Your direction</li><li><span>✦</span> Your possibilities</li></ol>
      <p className="guide-note">{content.note}</p>
    </aside>
  );
}
