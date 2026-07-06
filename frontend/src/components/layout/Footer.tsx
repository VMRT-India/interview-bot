const CONTACT_EMAIL = "marutiram.tv@gmail.com";

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="mx-auto mt-24 w-[min(1100px,92%)] border-t border-white/10 pb-10 pt-8 text-sm text-white/50">
      <div className="grid gap-8 sm:grid-cols-3">
        <div>
          <div className="text-base font-semibold text-white">InterviewSim</div>
          <p className="mt-2 max-w-xs text-white/45">
            An adaptive AI interview simulator — dynamic questions, real-time evaluation,
            actionable feedback.
          </p>
        </div>

        <div>
          <div className="font-medium text-white/75">Contact</div>
          <a href={`mailto:${CONTACT_EMAIL}`} className="mt-2 block hover:text-white">
            {CONTACT_EMAIL}
          </a>
        </div>

        <div>
          <div className="font-medium text-white/75">Legal</div>
          <p className="mt-2 text-white/45">
            © {year} InterviewSim. All rights reserved.
          </p>
          <p className="text-white/45">Licensed for personal and evaluation use.</p>
        </div>
      </div>
    </footer>
  );
}
