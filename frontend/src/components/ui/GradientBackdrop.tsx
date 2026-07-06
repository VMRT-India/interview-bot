export function GradientBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[color:var(--color-base)]">
      <div
        className="blob blob-a h-[42vw] w-[42vw] bg-[color:var(--color-accent)]"
        style={{ top: "-10%", left: "-8%" }}
      />
      <div
        className="blob blob-b h-[38vw] w-[38vw] bg-fuchsia-500"
        style={{ top: "20%", right: "-12%" }}
      />
      <div
        className="blob blob-c h-[34vw] w-[34vw] bg-[color:var(--color-accent-soft)]"
        style={{ bottom: "-14%", left: "18%" }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,var(--color-base)_85%)]" />
    </div>
  );
}
