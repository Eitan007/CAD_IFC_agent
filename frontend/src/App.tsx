import { Navigate, Route, Routes } from "react-router-dom";
import { UploadPage } from "./pages/UploadPage";
import { ProjectWorkspace } from "./pages/ProjectWorkspace";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/project/:projectId" element={<ProjectWorkspace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
