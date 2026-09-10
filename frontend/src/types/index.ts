export interface LoginRequest {
  email: string;
  password: string;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
  email: string;
  role: string;
}

export interface DeploymentInfo {
  name: string;
  namespace: string;
  replicas: number;
  available_replicas: number;
}

export interface Schedule {
  id: number;
  namespace: string;
  deployment_name: string;
  scale_down_time: string;
  scale_up_time: string;
  original_replicas: number;
  enabled: boolean;
  is_scaled_down: boolean;
  last_scaled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreate {
  namespace: string;
  deployment_name: string;
  scale_down_time: string;
  scale_up_time: string;
}

export interface ScheduleUpdate {
  scale_down_time?: string;
  scale_up_time?: string;
  enabled?: boolean;
}

export interface ApiError {
  detail: string;
}

// User Management Types
export interface User {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  allowed_namespaces: string[];
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  role: string;
  allowed_namespaces?: string[];
}

export interface UserUpdate {
  email?: string;
  password?: string;
  role?: string;
  is_active?: boolean;
  allowed_namespaces?: string[];
}

export interface UserListResponse {
  users: User[];
  total: number;
}

// API Key Management Types
export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface ApiKeyCreate {
  name: string;
  expires_in_days?: number;
}

export interface ApiKeyCreated {
  id: number;
  name: string;
  prefix: string;
  api_key: string;  // Full key shown only once
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
}
