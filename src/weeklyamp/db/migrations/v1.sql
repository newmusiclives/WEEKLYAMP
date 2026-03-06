-- v1: Add email verification and unsubscribe token columns to subscribers
ALTER TABLE subscribers ADD COLUMN email_verified INTEGER DEFAULT 0;
ALTER TABLE subscribers ADD COLUMN verification_token TEXT DEFAULT '';
ALTER TABLE subscribers ADD COLUMN unsubscribe_token TEXT DEFAULT '';
