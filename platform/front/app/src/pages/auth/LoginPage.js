import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../auth/AuthContext';
import './AuthPages.css';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const user = await login({ email, password });
      navigate(user.role === 'admin' ? '/interne/HomePage' : '/externe/HomePage', { replace: true });
    } catch (requestError) {
      setError(requestError.status === 429 ? 'Trop de tentatives. Réessayez plus tard.' : requestError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Connexion</h1>
        {location.state?.registered && <p className="auth-success">Compte créé. Vous pouvez vous connecter.</p>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <label htmlFor="login-email">Email</label>
        <input id="login-email" type="email" value={email} onChange={event => setEmail(event.target.value)} required />
        <label htmlFor="login-password">Mot de passe</label>
        <input id="login-password" type="password" value={password} onChange={event => setPassword(event.target.value)} required />
        <button type="submit" disabled={submitting}>
          {submitting ? 'Connexion...' : 'Se connecter'}
        </button>
        <p>Pas encore de compte ? <Link to="/register">S’inscrire</Link></p>
        <Link to="/legal">Conditions et confidentialité</Link>
      </form>
    </main>
  );
}
