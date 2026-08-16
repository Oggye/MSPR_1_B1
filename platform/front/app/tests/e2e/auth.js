const API_BASE_URL = process.env.E2E_API_URL || 'http://localhost:8000';

async function createAuthenticatedSession(request, role = 'user') {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const email = `${role}-${suffix}@example.com`;
  const password = 'Password1';
  const adminCode = role === 'admin' ? process.env.E2E_ADMIN_CODE : null;

  if (role === 'admin' && !adminCode) {
    throw new Error('E2E_ADMIN_CODE doit être défini pour les tests administrateur.');
  }

  const registerResponse = await request.post(`${API_BASE_URL}/api/auth/register`, {
    data: {
      email,
      password,
      password_confirm: password,
      is_admin: role === 'admin',
      admin_code: adminCode,
      accept_terms: true,
    },
  });
  if (registerResponse.status() !== 201) {
    throw new Error(`Inscription E2E impossible (${registerResponse.status()}).`);
  }

  const loginResponse = await request.post(`${API_BASE_URL}/api/auth/login`, {
    data: { email, password },
  });
  if (loginResponse.status() !== 200) {
    throw new Error(`Connexion E2E impossible (${loginResponse.status()}).`);
  }
}

module.exports = { createAuthenticatedSession };
