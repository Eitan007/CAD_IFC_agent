import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { UploadPage } from "./pages/UploadPage";
import { ProjectWorkspace } from "./pages/ProjectWorkspace";

export default function App() {
  const location = useLocation();
  const isWorkspace = location.pathname.startsWith("/project/");

  if (!isWorkspace && location.pathname !== "/") {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="app-shell">
      <motion.div
        className="app-page-glow"
        aria-hidden
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.8, 1, 0.8],
          x: ["-50%", "-48%", "-52%", "-50%"],
        }}
        transition={{
          duration: 10,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />

      <div className={`app-slider ${isWorkspace ? "to-workspace" : ""}`}>
        <div className="app-slide app-slide-upload">
          <UploadPage />
        </div>
        <div className="app-slide app-slide-workspace">
          <Routes>
            <Route path="/project/:projectId" element={<ProjectWorkspace />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
