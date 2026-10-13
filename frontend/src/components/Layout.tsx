import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useHealth } from "../hooks/useHealth";

export default function Layout() {
  const readiness = useHealth();
  const { pathname } = useLocation();
  return (
    <div className="app">
      <div className="ambient" aria-hidden="true">
        <span className="orb orb-warm" />
        <span className="orb orb-cool" />
      </div>
      <header>
        <Link className="brand" to="/">
          <span className="brand-key keycap">
            <img
              className="brand-mark"
              src="/favicon.svg"
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
          <a href="/docs">API docs ↗</a>
        </nav>
      </header>
      <main>
        <div className="page" key={pathname}>
          <Outlet context={readiness} />
        </div>
      </main>
      <footer>
        <span>TRACEINTEL / EVIDENCE FIRST</span>
        <a href="https://github.com/eshitakundu/TraceIntel">GitHub ↗</a>
      </footer>
    </div>
  );
}
