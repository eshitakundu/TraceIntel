import { Link, NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
  return <><header><Link className="brand" to="/"><span className="brand-mark">T</span> TRACEINTEL</Link>
    <nav aria-label="Main navigation"><NavLink to="/methodology">Methodology</NavLink><NavLink to="/architecture">Architecture</NavLink><a href="/docs">API docs ↗</a></nav></header>
    <main><Outlet /></main><footer><span>TRACEINTEL / EVIDENCE FIRST</span><a href="https://github.com/eshitakundu/TraceIntel">GitHub ↗</a></footer></>
}