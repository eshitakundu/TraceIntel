import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useHealth } from "../hooks/useHealth";

export default function Layout() {
  const readiness = useHealth();
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [pathname]);
  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="ambient" aria-hidden="true">
        <span className="orb orb-warm" />
        <span className="orb orb-cool" />
      </div>
      <header className="site-header">
        <Link className="brand" to="/" translate="no">
          <span className="brand-key keycap">
            <img
              className="brand-mark"
              src="/traceintel-mark.svg"
              alt=""
              width="20"
              height="20"
            />
          </span>
          TRACEINTEL
        </Link>
        <nav aria-label="Main navigation">
          <NavLink to="/methodology">Methodology</NavLink>
          <NavLink to="/architecture">Architecture</NavLink>
          <a href="/docs">API docs</a>
        </nav>
      </header>
      <main id="main-content">
        <div className="page" key={pathname}>
          <Outlet context={readiness} />
        </div>
      </main>
      <footer className="site-footer">
        <span>TraceIntel · Evidence first</span>
        <a
          href="https://github.com/eshitakundu/TraceIntel"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </footer>
    </div>
  );
}
