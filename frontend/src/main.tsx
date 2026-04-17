import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

/**
 * Mount the React portal into the root DOM node.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   void
 *
 * Raises:
 *   Error: Raised if the root container is missing from `index.html`.
 */
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
