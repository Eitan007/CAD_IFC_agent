import { create } from "zustand";

export type UiState = {
  selectedElementId: string | null;
  storeyFilter: string;
  typeFilter: string;
  sidebarOpen: boolean;
  setSelectedElementId: (id: string | null) => void;
  setStoreyFilter: (value: string) => void;
  setTypeFilter: (value: string) => void;
  setSidebarOpen: (open: boolean) => void;
};

export const useUiStore = create<UiState>((set) => ({
  selectedElementId: null,
  storeyFilter: "",
  typeFilter: "",
  sidebarOpen: false,
  setSelectedElementId: (id) => set({ selectedElementId: id }),
  setStoreyFilter: (storeyFilter) => set({ storeyFilter }),
  setTypeFilter: (typeFilter) => set({ typeFilter }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
}));
