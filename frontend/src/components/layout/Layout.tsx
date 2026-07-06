import type { ReactNode } from "react";
import { GradientBackdrop } from "../ui/GradientBackdrop";
import { Footer } from "./Footer";
import { Navbar } from "./Navbar";

export function Layout({
  children,
  showFooter = true,
}: {
  children: ReactNode;
  showFooter?: boolean;
}) {
  return (
    <div className="min-h-screen">
      <GradientBackdrop />
      <Navbar />
      <main className="mx-auto w-[min(1100px,92%)] pb-16 pt-14">{children}</main>
      {showFooter && <Footer />}
    </div>
  );
}
