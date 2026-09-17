import { Link, NavLink, Outlet } from "react-router-dom";

import { useHealth } from "../hooks/useHealth";

export default function Layout() {
  const readiness = useHealth();
  return (
    <>
      <header>
        <Link className="brand" to="/">
          <img
            className="brand-mark"
            src="/favicon.svg"
            alt=""
            width="32"
            height="32"
          />{" "}
          TRACEINTEL
        </Link>
        <nav aria-label="Main navigation">
          <NavLink to="/methodology">Methodology</NavLink>
          <NavLink to="/architecture">Architecture</NavLink>
          <a href="/docs">API docs ↗</a>
        </nav>
      </header>
      <main>
        <Outlet context={readiness} />
      </main>
      <footer>
        <span>TRACEINTEL / EVIDENCE FIRST</span>
        <a href="https://github.com/eshitakundu/TraceIntel">GitHub ↗</a>
      </footer>
    </>
  );
}
