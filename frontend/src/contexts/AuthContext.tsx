import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authAPI } from '../services/api';
import type { LoginRequest } from '../types';

interface AuthContextType {
  loading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  userEmail: string | null;
  userRole: string | null;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);

  // Auto-refresh token 5 minutes before expiration (25 minutes after login)
  useEffect(() => {
    if (!isAuthenticated) return;

    // Refresh every 25 minutes (5 minutes before the 30-minute expiration)
    const refreshInterval = setInterval(async () => {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const tokenData = await authAPI.refresh(refreshToken);
          localStorage.setItem('access_token', tokenData.access_token);
          localStorage.setItem('refresh_token', tokenData.refresh_token);
          // Email and role don't change, no need to update
        } catch (error) {
          // If refresh fails, logout the user
          console.error('Failed to refresh token:', error);
          logout();
        }
      }
    }, 25 * 60 * 1000); // 25 minutes in milliseconds

    return () => clearInterval(refreshInterval);
  }, [isAuthenticated]);

  // Check if token exists on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    const email = localStorage.getItem('user_email');
    const role = localStorage.getItem('user_role');

    if (token && refreshToken && email && role) {
      setIsAuthenticated(true);
      setUserEmail(email);
      setUserRole(role);
    }
    setLoading(false);
  }, []);

  const login = async (credentials: LoginRequest) => {
    const tokenData = await authAPI.login(credentials);
    localStorage.setItem('access_token', tokenData.access_token);
    localStorage.setItem('refresh_token', tokenData.refresh_token);
    localStorage.setItem('user_email', tokenData.email);
    localStorage.setItem('user_role', tokenData.role);
    setIsAuthenticated(true);
    setUserEmail(tokenData.email);
    setUserRole(tokenData.role);
  };

  const logout = async () => {
    const refreshToken = localStorage.getItem('refresh_token');

    // Call backend to revoke refresh token
    if (refreshToken) {
      try {
        await authAPI.logout(refreshToken);
      } catch (error) {
        console.error('Logout error:', error);
        // Continue with local logout even if backend call fails
      }
    }

    // Clear local storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_role');
    setIsAuthenticated(false);
    setUserEmail(null);
    setUserRole(null);
  };

  const value = {
    loading,
    login,
    logout,
    isAuthenticated,
    userEmail,
    userRole,
    isAdmin: userRole === 'admin',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
