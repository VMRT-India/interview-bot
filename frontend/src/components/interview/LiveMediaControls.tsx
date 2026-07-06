import { AnimatePresence, motion } from "framer-motion";
import { Camera, Mic, MoreVertical } from "lucide-react";
import { useState } from "react";

/**
 * Live video/audio has no backend support yet (planned for a later phase). The
 * controls exist in the DOM so wiring them up later is a small diff, but they're
 * tucked behind a closed-by-default menu and disabled, so nobody stumbles into
 * them expecting a working feature today.
 */
export function LiveMediaControls() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="More options"
        className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/5 text-white/60 hover:bg-white/10"
      >
        <MoreVertical size={16} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            className="glass-panel-tight absolute right-0 top-11 z-10 flex w-52 flex-col gap-1 p-2"
          >
            <div className="px-2 pb-1 text-[11px] uppercase tracking-wide text-white/35">
              Live media (coming soon)
            </div>
            <button
              disabled
              title="Live video — coming soon"
              className="flex items-center gap-2 rounded-xl px-2 py-2 text-sm text-white/35"
            >
              <Camera size={16} /> Enable camera
            </button>
            <button
              disabled
              title="Live audio — coming soon"
              className="flex items-center gap-2 rounded-xl px-2 py-2 text-sm text-white/35"
            >
              <Mic size={16} /> Enable microphone
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
