import { z, messageIdSchema, sessionIdSchema } from "./zod";

export const sessionEnvelopeSchema = z.object({
  sessionId: sessionIdSchema,
  messageId: messageIdSchema,
});

export type SessionEnvelope = z.infer<typeof sessionEnvelopeSchema>;
