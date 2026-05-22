import { create } from "zustand";
import type { ChatReference } from "../api/types";

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  refs?: ChatReference[];
};

type ConversationState = {
  messages: ConversationMessage[];
  appendMessage: (msg: Omit<ConversationMessage, "id"> & { id?: string }) => void;
  resetConversation: () => void;
};

const WELCOME: ConversationMessage = {
  id: "welcome",
  role: "assistant",
  text: "Ask about quantities, cost, schedule, or compliance. Select elements on the model to add context.",
};

let msgCounter = 0;
const nextId = () => `msg-${++msgCounter}-${Date.now()}`;

export const useConversationStore = create<ConversationState>((set) => ({
  messages: [WELCOME],

  appendMessage: (msg) => {
    const id = msg.id ?? nextId();
    set((s) => ({
      messages: [...s.messages, { ...msg, id }],
    }));
  },

  resetConversation: () => {
    msgCounter = 0;
    set({ messages: [WELCOME] });
  },
}));
