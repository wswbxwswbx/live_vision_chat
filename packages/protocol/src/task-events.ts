import { z, taskIdSchema } from "./zod";

export const taskEventKindSchema = z.enum([
  "accepted",
  "progress",
  "need_user_input",
  "completed",
  "failed",
]);

export const taskEventPayloadSchema = z.object({
  taskId: taskIdSchema,
  eventKind: taskEventKindSchema,
  summary: z.string().min(1),
});

export type TaskEventPayload = z.infer<typeof taskEventPayloadSchema>;
