/** Soft drifting colour behind the page. Purely decorative. */
export function Aurora() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute -left-40 -top-40 h-[34rem] w-[34rem] animate-drift rounded-full bg-purple-soft opacity-80 blur-3xl" />
      <div className="absolute -right-32 top-1/4 h-[30rem] w-[30rem] animate-drift rounded-full bg-gold-soft opacity-90 blur-3xl [animation-delay:-8s]" />
      <div className="absolute bottom-[-12rem] left-1/3 h-[32rem] w-[32rem] animate-drift rounded-full bg-purple-soft opacity-60 blur-3xl [animation-delay:-15s]" />
    </div>
  );
}
