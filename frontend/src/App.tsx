import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from "framer-motion";
import { UploadPage } from "./pages/UploadPage";
import { ProjectWorkspace } from "./pages/ProjectWorkspace";
import { MonitoringDashboard } from "./pages/MonitoringDashboard";
import { motionPresets } from "./utils/motion";

export default function App() {
  const location = useLocation();
  const reduceMotion = useReducedMotion();

  return (
    <MotionConfig reducedMotion="user">
      <div className="app-shell">
        <motion.div
          className="app-page-glow"
          aria-hidden
          initial={reduceMotion ? { opacity: 0.5, scale: 1, x: "-50%" } : { opacity: 0.5, scale: 1.1, x: "-50%" }}
          animate={{ opacity: 1, scale: 1, x: "-50%" }}
          transition={{ duration: reduceMotion ? 0.2 : 10, ease: "easeInOut" }}
        />

        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            className="app-route"
            {...motionPresets.page}
          >
            <Routes location={location}>
              <Route path="/" element={<UploadPage />} />
              <Route path="/project/:projectId" element={<ProjectWorkspace />} />
              <Route path="/monitoring" element={<MonitoringDashboard />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </motion.main>
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
