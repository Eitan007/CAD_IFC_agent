import { create } from "zustand";

export type UiState = {
  selectedElementId: string | null;
  storeyFilter: string;
  typeFilter: string;
  setSelectedElementId: (id: string | null) => void;
  setStoreyFilter: (value: string) => void;
  setTypeFilter: (value: string) => void;
};

export const useUiStore = create<UiState>((set) => ({
  selectedElementId: null,
  storeyFilter: "",
  typeFilter: "",
  setSelectedElementId: (id) => set({ selectedElementId: id }),
  setStoreyFilter: (storeyFilter) => set({ storeyFilter }),
  setTypeFilter: (typeFilter) => set({ typeFilter }),
}));
