-- Initial database setup script
-- This file is executed when PostgreSQL container starts for the first time

-- Create additional indexes if needed
-- (Main tables will be created by Alembic migrations)

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone
SET timezone = 'Asia/Shanghai';