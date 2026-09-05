import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { getCurrentUser, loginAccount, logoutAccount } from '../services/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      return currentUser;
    } catch (error) {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (credentials) => {
    const currentUser = await loginAccount(credentials);
    setUser(currentUser);
    return currentUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAccount();
    } finally {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    const clearExpiredSession = () => setUser(null);
    window.addEventListener('obrail:unauthorized', clearExpiredSession);
    return () => window.removeEventListener('obrail:unauthorized', clearExpiredSession);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, refreshUser }), [
    user,
    loading,
    login,
    logout,
    refreshUser,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth doit être utilisé dans AuthProvider.');
  return context;
}
