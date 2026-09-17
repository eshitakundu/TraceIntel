import { Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Documentation from "./pages/Documentation";
import AnalysisProgress from "./pages/AnalysisProgress";
import ReportPage from "./pages/ReportPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="analysis/:id" element={<AnalysisProgress />} />
        <Route path="reports/:id" element={<ReportPage />} />
        <Route
          path="methodology"
          element={<Documentation kind="methodology" />}
        />
        <Route
          path="architecture"
          element={<Documentation kind="architecture" />}
        />
        <Route
          path="*"
          element={
            <section className="document">
              <h1>Page not found</h1>
              <Link to="/">Return to workspace</Link>
            </section>
          }
        />
      </Route>
    </Routes>
  );
}
