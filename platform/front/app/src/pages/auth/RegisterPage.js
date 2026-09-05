import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { registerAccount } from '../../services/auth';
import './AuthPages.css';

const isStrongPassword = password => (
  password.length >= 8
  && /[A-Z]/.test(password)
  && /[a-z]/.test(password)
  && /[^A-Za-z]/.test(password)
);

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: '',
    password: '',
    passwordConfirm: '',
    isAdmin: false,
    adminCode: '',
    acceptTerms: false,
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const update = (field, value) => setForm(current => ({ ...current, [field]: value }));

  const toggleAdmin = (checked) => {
    setForm(current => ({ ...current, isAdmin: checked, adminCode: checked ? current.adminCode : '' }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (!isStrongPassword(form.password)) {
      setError('Le mot de passe ne respecte pas les règles indiquées.');
      return;
    }
    if (form.password !== form.passwordConfirm) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }
    if (form.isAdmin && !/^\d{6}$/.test(form.adminCode)) {
      setError('Le code administrateur doit contenir exactement 6 chiffres.');
      return;
    }
    if (!form.acceptTerms) {
      setError('Vous devez accepter les conditions et la politique de confidentialité.');
      return;
    }

    setSubmitting(true);
    try {
      await registerAccount({
        email: form.email,
        password: form.password,
        password_confirm: form.passwordConfirm,
        is_admin: form.isAdmin,
        admin_code: form.isAdmin ? form.adminCode : null,
        accept_terms: form.acceptTerms,
      });
      navigate('/login', { replace: true, state: { registered: true } });
    } catch (requestError) {
      setError(requestError.status === 429 ? 'Trop de tentatives. Réessayez plus tard.' : requestError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Créer un compte</h1>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <label htmlFor="register-email">Email</label>
        <input id="register-email" type="email" value={form.email} onChange={event => update('email', event.target.value)} required />
        <label htmlFor="register-password">Mot de passe</label>
        <input id="register-password" type="password" value={form.password} onChange={event => update('password', event.target.value)} required />
        <ul className="password-rules">
          <li>8 caractères minimum</li>
          <li>1 majuscule et 1 minuscule</li>
          <li>1 chiffre ou caractère spécial</li>
        </ul>
        <label htmlFor="register-confirm">Confirmation du mot de passe</label>
        <input id="register-confirm" type="password" value={form.passwordConfirm} onChange={event => update('passwordConfirm', event.target.value)} required />
        <label className="checkbox-row">
          <input type="checkbox" checked={form.isAdmin} onChange={event => toggleAdmin(event.target.checked)} />
          Je suis administrateur
        </label>
        {form.isAdmin && (
          <>
            <label htmlFor="admin-code">Code administrateur à 6 chiffres</label>
            <input
              id="admin-code"
              type="text"
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              value={form.adminCode}
              onChange={event => update('adminCode', event.target.value.replace(/\D/g, '').slice(0, 6))}
              required
            />
          </>
        )}
        <label className="checkbox-row">
          <input type="checkbox" checked={form.acceptTerms} onChange={event => update('acceptTerms', event.target.checked)} required />
          J’accepte les Conditions générales d’utilisation et reconnais avoir pris connaissance de la Politique de confidentialité.
        </label>
        <Link to="/legal">Voir les détails</Link>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Création...' : 'Créer mon compte'}
        </button>
        <p>Déjà inscrit ? <Link to="/login">Se connecter</Link></p>
      </form>
    </main>
  );
}
