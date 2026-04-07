import { z } from "./zod";
import { sessionEnvelopeSchema } from "./session-envelope";
import {
  toolCallPayloadSchema,
  toolErrorPayloadSchema,
  toolProgressPayloadSchema,
  toolResultPayloadSchema,
} from "./tool-calls";
import { taskEventPayloadSchema } from "./task-events";

const turnMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("turn"),
  payload: z.object({
    text: z.string().min(1),
  }),
});

const handoffResumeMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("handoff_resume"),
  payload: z.object({
    taskId: z.string().min(1),
    text: z.string().min(1),
  }),
});

const toolResultMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("tool_result"),
  payload: toolResultPayloadSchema,
});

const toolErrorMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("tool_error"),
  payload: toolErrorPayloadSchema,
});

const taskEventMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("task_event"),
  payload: taskEventPayloadSchema,
});

const toolCallMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("tool_call"),
  payload: toolCallPayloadSchema,
});

const toolProgressMessageSchema = sessionEnvelopeSchema.extend({
  type: z.literal("tool_progress"),
  payload: toolProgressPayloadSchema,
});

export const clientMessageSchema = z.discriminatedUnion("type", [
  turnMessageSchema,
  handoffResumeMessageSchema,
  toolResultMessageSchema,
  toolErrorMessageSchema,
]);

export const serverMessageSchema = z.discriminatedUnion("type", [
  taskEventMessageSchema,
  toolCallMessageSchema,
  toolProgressMessageSchema,
  toolResultMessageSchema,
  toolErrorMessageSchema,
]);

export type ClientMessage = z.infer<typeof clientMessageSchema>;
export type ServerMessage = z.infer<typeof serverMessageSchema>;

export function parseClientMessage(input: unknown): ClientMessage {
  return clientMessageSchema.parse(input);
}

export function parseServerMessage(input: unknown): ServerMessage {
  return serverMessageSchema.parse(input);
}
