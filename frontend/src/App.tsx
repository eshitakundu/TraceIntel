import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Documentation from "./pages/Documentation";
import AnalysisProgress from "./pages/AnalysisProgress";

const ReportPage = lazy(() => import("./pages/ReportPage"));
const SavedAnalysisProgress = lazy(
  () => import("./pages/SavedAnalysisProgress"),
);

export default function App() {
  const loading = (
    <section className="document trace-light-page route-loading">
      <p role="status">Loading recorded analysis…</p>
    </section>
  );
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="analysis/:id" element={<AnalysisProgress />} />
        <Route
          path="reports/:id"
          element={
            <Suspense fallback={loading}>
              <ReportPage />
            </Suspense>
          }
        />
        <Route
          path="demo/:id"
          element={
            <Suspense fallback={loading}>
              <SavedAnalysisProgress />
            </Suspense>
          }
        />
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
            <section className="document trace-light-page missing-page">
              <h1>Page not found</h1>
              <Link to="/">Return to workspace</Link>
            </section>
          }
        />
      </Route>
    </Routes>
  );
}
