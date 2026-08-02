"use client";

import {
  ConversationProvider,
  useConversation,
  useConversationControls,
} from "@elevenlabs/react";
import type { ReactNode } from "react";

import type {
  ConversationClient,
  ConversationDraft,
  ConversationSpeaker,
} from "./contracts";

type AdapterProperties = Readonly<{
  children: (client: ConversationClient) => ReactNode;
  onDisconnect: () => void;
  onDraft: (draft: ConversationDraft) => void;
  onError: (message: string) => void;
  onTranscript: (speaker: ConversationSpeaker, text: string) => void;
}>;

type IntakeToolParameters = Readonly<{
  full_name?: unknown;
  email?: unknown;
  phone?: unknown;
  intake_intent?: unknown;
}>;

export function ElevenLabsConversationAdapter(properties: AdapterProperties) {
  return (
    <ConversationProvider>
      <AdapterBridge {...properties} />
    </ConversationProvider>
  );
}

function AdapterBridge({
  children,
  onDisconnect,
  onDraft,
  onError,
  onTranscript,
}: AdapterProperties) {
  const controls = useConversationControls();
  const conversation = useConversation({
    clientTools: {
      submit_intake_draft: (parameters: IntakeToolParameters) => {
        onDraft({
          fullName: optionalString(parameters.full_name),
          email: optionalString(parameters.email),
          phone: optionalString(parameters.phone),
          intakeIntent: optionalString(parameters.intake_intent),
        });
        return "The draft is visible for user review. No data has been saved.";
      },
    },
    onDisconnect,
    onError: (message) => {
      onError(
        typeof message === "string" ? message : "Voice connection failed",
      );
      void controls.endSession().catch(() => undefined);
    },
    onMessage: (message) => {
      const speaker = message.source === "user" ? "USER" : "AGENT";
      const text = message.message.trim();
      if (text) {
        onTranscript(speaker, text);
      }
    },
  });

  const client: ConversationClient = {
    status: conversation.status,
    mode: conversation.mode,
    isMuted: conversation.isMuted,
    start: async (credential) => {
      await conversation.startSession({ conversationToken: credential });
    },
    end: async () => {
      await conversation.endSession();
    },
    setMuted: conversation.setMuted,
  };

  return children(client);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}
