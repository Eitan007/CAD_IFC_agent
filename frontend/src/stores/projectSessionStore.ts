import { create } from "zustand";

export type UploadPhase = "idle" | "uploading" | "done" | "error";

type ProjectSessionState = {
  /** In-memory IFC bytes for local 3D preview (skip /ifc fetch). */
  localIfcBuffers: Record<string, ArrayBuffer>;
  localModelFiles: Record<string, File>;
  uploadPhase: Record<string, UploadPhase>;
  uploadProgress: Record<string, number>;
  uploadError: Record<string, string | null>;

  setLocalModel: (projectId: string, file: File) => Promise<void>;
  getLocalIfcBuffer: (projectId: string) => ArrayBuffer | undefined;
  getLocalModelFile: (projectId: string) => File | undefined;
  setUploadPhase: (projectId: string, phase: UploadPhase, progress?: number, error?: string | null) => void;
  clearProject: (projectId: string) => void;
};

export const useProjectSessionStore = create<ProjectSessionState>((set, get) => ({
  localIfcBuffers: {},
  localModelFiles: {},
  uploadPhase: {},
  uploadProgress: {},
  uploadError: {},

  setLocalModel: async (projectId, file) => {
    const isIfc = file.name.toLowerCase().endsWith(".ifc");
    const buffer = isIfc ? await file.arrayBuffer() : undefined;
    set((s) => ({
      localIfcBuffers: buffer
        ? { ...s.localIfcBuffers, [projectId]: buffer }
        : Object.fromEntries(Object.entries(s.localIfcBuffers).filter(([id]) => id !== projectId)),
      localModelFiles: { ...s.localModelFiles, [projectId]: file },
      uploadPhase: { ...s.uploadPhase, [projectId]: "idle" },
      uploadProgress: { ...s.uploadProgress, [projectId]: 0 },
      uploadError: { ...s.uploadError, [projectId]: null },
    }));
  },

  getLocalModelFile: (projectId) => get().localModelFiles[projectId],

  getLocalIfcBuffer: (projectId) => get().localIfcBuffers[projectId],

  setUploadPhase: (projectId, phase, progress = 0, error = null) => {
    set((s) => ({
      uploadPhase: { ...s.uploadPhase, [projectId]: phase },
      uploadProgress: { ...s.uploadProgress, [projectId]: progress },
      uploadError: { ...s.uploadError, [projectId]: error },
    }));
  },

  clearProject: (projectId) => {
    set((s) => {
      const { [projectId]: _b, ...localIfcBuffers } = s.localIfcBuffers;
      const { [projectId]: _f, ...localModelFiles } = s.localModelFiles;
      const { [projectId]: _p, ...uploadPhase } = s.uploadPhase;
      const { [projectId]: _g, ...uploadProgress } = s.uploadProgress;
      const { [projectId]: _e, ...uploadError } = s.uploadError;
      return { localIfcBuffers, localModelFiles, uploadPhase, uploadProgress, uploadError };
    });
  },
}));
