import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/atkinson-hyperlegible-next";
import "@fontsource/martian-mono/latin-400.css";
import "@fontsource/martian-mono/latin-600.css";
import App from "./App";
import "./styles.css";
import "./landing.css";
import "./pages.css";
import "./report.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
