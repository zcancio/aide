/**
 * useAuth - React hook for authentication state management
 * Provides AuthContext and AuthProvider for app-wide auth state
 */

import { createContext, useContext, useState, useEffect } from 'react';
import * as api from '../lib/api.js';
import { getFingerprint } from '../lib/fingerprint.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isShadow, setIsShadow] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      // Try existing session first
      const result = await api.fetchMe();

      if (result.data) {
        setUser(result.data);
        setIsAuthenticated(true);
        setIsShadow(result.data.is_shadow || false);
      } else {
        // No session - create shadow user
        const fingerprint = getFingerprint();
        const shadowResult = await api.createShadowSession(fingerprint);

        if (shadowResult.data) {
          // Fetch the user data after creating shadow session
          const userResult = await api.fetchMe();
          if (userResult.data) {
            setUser(userResult.data);
            setIsAuthenticated(true);
            setIsShadow(true);
          }
        }
      }

      setIsLoading(false);
    }

    checkAuth();
  }, []);

  const sendMagicLink = (email) => api.sendMagicLink(email);

  const logout = async () => {
    await api.logout();
    setUser(null);
    setIsAuthenticated(false);
  };

  const convertShadowUser = async (email) => {
    const fingerprint = getFingerprint();
    return api.convertShadowUser(email, fingerprint);
  };

  const value = {
    user,
    isAuthenticated,
    isShadow,
    isLoading,
    sendMagicLink,
    convertShadowUser,
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
