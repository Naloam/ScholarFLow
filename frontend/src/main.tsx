import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./i18n";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Suspense>
      <App />
    </Suspense>
  </React.StrictMode>,
);
