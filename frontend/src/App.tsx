import { Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Documentation from './pages/Documentation'

export default function App() {
  return <Routes><Route element={<Layout />}><Route index element={<Home />} />
    <Route path="methodology" element={<Documentation kind="methodology" />} />
    <Route path="architecture" element={<Documentation kind="architecture" />} />
    <Route path="*" element={<section className="document"><h1>Page not found</h1><Link to="/">Return to workspace</Link></section>} />
  </Route></Routes>
}