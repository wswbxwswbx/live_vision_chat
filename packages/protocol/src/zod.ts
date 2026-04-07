import { z } from "zod";

export { z };

export const sessionIdSchema = z.string().regex(/^session_[A-Za-z0-9_-]+$/);
export const messageIdSchema = z.string().regex(/^msg_[A-Za-z0-9_-]+$/);
export const taskIdSchema = z.string().regex(/^task_[A-Za-z0-9_-]+$/);
export const callIdSchema = z.string().regex(/^call_[A-Za-z0-9_-]+$/);
