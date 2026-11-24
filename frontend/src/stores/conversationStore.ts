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
  activeProjectId: string | null;
  loadConversation: (projectId: string) => void;
  appendMessage: (msg: Omit<ConversationMessage, "id"> & { id?: string }) => void;
  replacePendingMessage: (msg: ConversationMessage | null) => void;
  resetConversation: () => void;
};

const WELCOME: ConversationMessage = {
  id: "welcome",
  role: "assistant",
  text: "Ask about quantities, cost, schedule, or compliance. Select elements on the model to add context.",
};

let msgCounter = 0;
const nextId = () => `msg-${++msgCounter}-${Date.now()}`;
const storageKey = (projectId: string) => `cad-ifc-chat:${projectId}`;

function savedMessages(messages: ConversationMessage[]) {
  return messages
    .filter((message) => message.id !== "welcome" && message.id !== "pending-assistant" && !message.id.startsWith("err-"))
    .slice(-24);
}

function writeMessages(projectId: string | null, messages: ConversationMessage[]) {
  if (!projectId) return;
  try {
    localStorage.setItem(storageKey(projectId), JSON.stringify(savedMessages(messages)));
  } catch {
    // Chat still works if the browser blocks local storage.
  }
}

export const useConversationStore = create<ConversationState>((set) => ({
  messages: [WELCOME],
  activeProjectId: null,

  loadConversation: (projectId) => {
    let previous: ConversationMessage[] = [];
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey(projectId)) ?? "[]");
      if (Array.isArray(stored)) {
        previous = stored.filter((message): message is ConversationMessage =>
          message && typeof message.text === "string" && (message.role === "user" || message.role === "assistant"),
        );
      }
    } catch {
      previous = [];
    }
    set({ activeProjectId: projectId, messages: [WELCOME, ...previous] });
  },

  appendMessage: (msg) => {
    const id = msg.id ?? nextId();
    set((s) => {
      const messages = [...s.messages, { ...msg, id }];
      writeMessages(s.activeProjectId, messages);
      return { messages };
    });
  },

  replacePendingMessage: (msg) => set((s) => {
    const withoutPending = s.messages.filter((message) => message.id !== "pending-assistant");
    const messages = msg ? [...withoutPending, msg] : withoutPending;
    writeMessages(s.activeProjectId, messages);
    return { messages };
  }),

  resetConversation: () => {
    msgCounter = 0;
    set((s) => {
      writeMessages(s.activeProjectId, []);
      return { messages: [WELCOME] };
    });
  },
}));
