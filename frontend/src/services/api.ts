import axios, { AxiosError } from 'axios';
import type {
  LoginRequest,
  Token,
  DeploymentInfo,
  Schedule,
  ScheduleCreate,
  ScheduleUpdate,
  ApiError,
  User,
  UserCreate,
  UserUpdate,
  UserListResponse,
  ApiKey,
  ApiKeyCreate,
  ApiKeyCreated,
} from '../types';

// Create axios instance
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle errors and auto-refresh tokens
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config;

    // If error is 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && originalRequest && !(originalRequest as any)._retry) {
      (originalRequest as any)._retry = true;

      try {
        // Try to refresh the token
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const tokenData = await authAPI.refresh(refreshToken);

          // Update tokens in localStorage
          localStorage.setItem('access_token', tokenData.access_token);
          localStorage.setItem('refresh_token', tokenData.refresh_token);

          // Update authorization header for the original request
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${tokenData.access_token}`;
          }

          // Retry the original request with new token
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, logout user
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_email');
        localStorage.removeItem('user_role');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    // If not 401 or refresh failed, reject the error
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_email');
      localStorage.removeItem('user_role');
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

// Auth API - Simple admin password authentication
export const authAPI = {
  login: async (credentials: LoginRequest): Promise<Token> => {
    const response = await api.post<Token>('/auth/login', credentials);
    return response.data;
  },

  refresh: async (refreshToken: string): Promise<Token> => {
    const response = await api.post<Token>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  logout: async (refreshToken: string): Promise<void> => {
    await api.post('/auth/logout', {
      refresh_token: refreshToken,
    });
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },
};

// Schedules API
export const schedulesAPI = {
  getAll: async (): Promise<Schedule[]> => {
    const response = await api.get<Schedule[]>('/schedules');
    return response.data;
  },

  getById: async (id: number): Promise<Schedule> => {
    const response = await api.get<Schedule>(`/schedules/${id}`);
    return response.data;
  },

  create: async (schedule: ScheduleCreate): Promise<Schedule> => {
    const response = await api.post<Schedule>('/schedules', schedule);
    return response.data;
  },

  update: async (id: number, schedule: ScheduleUpdate): Promise<Schedule> => {
    const response = await api.patch<Schedule>(`/schedules/${id}`, schedule);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/schedules/${id}`);
  },
};

// K8s API (Simplified - single cluster)
export const k8sAPI = {
  getNamespaces: async (): Promise<string[]> => {
    const response = await api.get<string[]>('/namespaces');
    return response.data;
  },

  getDeployments: async (namespace: string): Promise<DeploymentInfo[]> => {
    const response = await api.get<DeploymentInfo[]>(
      `/namespaces/${namespace}/deployments`
    );
    return response.data;
  },
};

// Users API
export const usersAPI = {
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/users/me');
    return response.data;
  },

  getAll: async (skip = 0, limit = 100): Promise<UserListResponse> => {
    const response = await api.get<UserListResponse>('/users', {
      params: { skip, limit },
    });
    return response.data;
  },

  getById: async (id: number): Promise<User> => {
    const response = await api.get<User>(`/users/${id}`);
    return response.data;
  },

  create: async (user: UserCreate): Promise<User> => {
    const response = await api.post<User>('/users', user);
    return response.data;
  },

  update: async (id: number, user: UserUpdate): Promise<User> => {
    const response = await api.patch<User>(`/users/${id}`, user);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/users/${id}`);
  },
};

// API Keys API
export const apiKeysAPI = {
  getAll: async (): Promise<ApiKey[]> => {
    const response = await api.get<ApiKey[]>('/api-keys');
    return response.data;
  },

  create: async (apiKey: ApiKeyCreate): Promise<ApiKeyCreated> => {
    const response = await api.post<ApiKeyCreated>('/api-keys', apiKey);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api-keys/${id}`);
  },
};

export default api;
