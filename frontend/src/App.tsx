import { Navigate, Route, Routes, useLocation } from "react-router-dom";
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
      <div className="app-page-glow" aria-hidden />

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
