const API_ROOT_URL = (
  process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api'
).replace(/\/api\/?$/, '');

async function authRequest(path, options = {}) {
  const response = await fetch(`${API_ROOT_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(payload.detail || 'Erreur d’authentification.');
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export const registerAccount = payload => authRequest('/api/auth/register', {
  method: 'POST',
  body: JSON.stringify(payload),
});

export const loginAccount = payload => authRequest('/api/auth/login', {
  method: 'POST',
  body: JSON.stringify(payload),
});

export const logoutAccount = () => authRequest('/api/auth/logout', { method: 'POST' });

export const getCurrentUser = () => authRequest('/api/auth/me');
