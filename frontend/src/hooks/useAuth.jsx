/**
 * useAuth - React hook for authentication state management
 * Provides AuthContext and AuthProvider for app-wide auth state
 */

import { createContext, useContext, useState, useEffect } from 'react';
import * as api from '../lib/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      const result = await api.fetchMe();

      if (result.data) {
        setUser(result.data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }

      setIsLoading(false);
    }

    checkAuth();
  }, []);

  const sendMagicLink = (email) => api.sendMagicLink(email);

  const verifyToken = async (token) => {
    const result = await api.verifyToken(token);

    if (result.data) {
      setUser(result.data);
      setIsAuthenticated(true);
    }

    return result;
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
    setIsAuthenticated(false);
  };

  const value = {
    user,
    isAuthenticated,
    isLoading,
    sendMagicLink,
    verifyToken,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (context === null) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  return context;
}
