import { create } from "zustand";

export type UploadPhase = "idle" | "uploading" | "done" | "error";

type ProjectSessionState = {
  /** In-memory IFC bytes for local preview (skip /ifc fetch). */
  localIfcBuffers: Record<string, ArrayBuffer>;
  localIfcFiles: Record<string, File>;
  uploadPhase: Record<string, UploadPhase>;
  uploadProgress: Record<string, number>;
  uploadError: Record<string, string | null>;

  setLocalIfc: (projectId: string, file: File) => Promise<void>;
  getLocalIfcBuffer: (projectId: string) => ArrayBuffer | undefined;
  getLocalIfcFile: (projectId: string) => File | undefined;
  setUploadPhase: (projectId: string, phase: UploadPhase, progress?: number, error?: string | null) => void;
  clearProject: (projectId: string) => void;
};

export const useProjectSessionStore = create<ProjectSessionState>((set, get) => ({
  localIfcBuffers: {},
  localIfcFiles: {},
  uploadPhase: {},
  uploadProgress: {},
  uploadError: {},

  setLocalIfc: async (projectId, file) => {
    const buffer = await file.arrayBuffer();
    set((s) => ({
      localIfcBuffers: { ...s.localIfcBuffers, [projectId]: buffer },
      localIfcFiles: { ...s.localIfcFiles, [projectId]: file },
      uploadPhase: { ...s.uploadPhase, [projectId]: "idle" },
      uploadProgress: { ...s.uploadProgress, [projectId]: 0 },
      uploadError: { ...s.uploadError, [projectId]: null },
    }));
  },

  getLocalIfcFile: (projectId) => get().localIfcFiles[projectId],

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
      const { [projectId]: _f, ...localIfcFiles } = s.localIfcFiles;
      const { [projectId]: _p, ...uploadPhase } = s.uploadPhase;
      const { [projectId]: _g, ...uploadProgress } = s.uploadProgress;
      const { [projectId]: _e, ...uploadError } = s.uploadError;
      return { localIfcBuffers, localIfcFiles, uploadPhase, uploadProgress, uploadError };
    });
  },
}));
