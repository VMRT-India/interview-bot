import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/Button";

export function Navbar() {
  const { user, logout, continueAsGuest } = useAuth();
  const navigate = useNavigate();
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleGuest() {
    setGuestLoading(true);
    try {
      await continueAsGuest();
      navigate("/interview/new");
    } catch {
      navigate("/login");
    } finally {
      setGuestLoading(false);
    }
  }

  return (
    <header className="sticky top-4 z-50 mx-auto mt-4 flex w-[min(1100px,92%)] items-center justify-between rounded-2xl border border-white/12 bg-white/6 px-5 py-3 backdrop-blur-xl">
      <Link to="/" className="text-base font-semibold tracking-tight text-white">
        Interview<span className="text-[color:var(--color-accent)]">Sim</span>
      </Link>

      <nav className="hidden items-center gap-6 text-sm text-white/70 sm:flex">
        <Link to="/" className="hover:text-white">
          Home
        </Link>
        {user && (
          <>
            <Link to="/dashboard" className="hover:text-white">
              Dashboard
            </Link>
            <Link to="/interview/new" className="hover:text-white">
              New Interview
            </Link>
            <Link to="/settings" className="hover:text-white">
              Settings
            </Link>
          </>
        )}
      </nav>

      <div className="flex items-center gap-3">
        {user ? (
          <Button
            variant="ghost"
            onClick={() => {
              logout();
              navigate("/");
            }}
          >
            Log out
          </Button>
        ) : (
          <>
            <Button variant="ghost" disabled={guestLoading} onClick={handleGuest}>
              {guestLoading ? "Starting…" : "Try without signing up"}
            </Button>
            <Link to="/login" className="text-sm text-white/70 hover:text-white">
              Log in
            </Link>
            <Button onClick={() => navigate("/signup")}>Get started</Button>
          </>
        )}
      </div>
    </header>
  );
}
