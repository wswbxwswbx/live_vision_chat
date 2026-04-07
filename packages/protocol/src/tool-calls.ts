import { z, callIdSchema, taskIdSchema } from "./zod";

export const toolCallStateSchema = z.enum([
  "queued",
  "running",
  "waiting_approval",
  "paused",
  "completed",
  "failed",
  "cancelled",
]);

export const toolCallPayloadSchema = z.object({
  callId: callIdSchema,
  taskId: taskIdSchema,
  toolName: z.string().min(1),
  params: z.record(z.string(), z.unknown()),
});

export const toolProgressPayloadSchema = z.object({
  callId: callIdSchema,
  state: toolCallStateSchema,
  status: z.string().min(1),
});

export const toolResultPayloadSchema = z.object({
  callId: callIdSchema,
  result: z.unknown(),
});

export const toolErrorPayloadSchema = z.object({
  callId: callIdSchema,
  error: z.string().min(1),
});

export type ToolCallState = z.infer<typeof toolCallStateSchema>;
export type ToolCallPayload = z.infer<typeof toolCallPayloadSchema>;
export type ToolProgressPayload = z.infer<typeof toolProgressPayloadSchema>;
export type ToolResultPayload = z.infer<typeof toolResultPayloadSchema>;
export type ToolErrorPayload = z.infer<typeof toolErrorPayloadSchema>;
