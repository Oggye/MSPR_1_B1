import { render, screen } from '@testing-library/react';

import ProtectedRoute from './ProtectedRoute';
import { useAuth } from './AuthContext';

jest.mock('./AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('react-router-dom', () => ({
  Navigate: ({ to }) => <h1>Redirection {to}</h1>,
  Outlet: () => <h1>Contenu protégé</h1>,
  useLocation: () => ({ pathname: '/private' }),
}), { virtual: true });

test('redirige un visiteur vers la connexion', () => {
  useAuth.mockReturnValue({ user: null, loading: false });
  render(<ProtectedRoute />);

  expect(screen.getByRole('heading', { name: 'Redirection /login' })).toBeInTheDocument();
});

test('refuse la route admin à un utilisateur simple', () => {
  useAuth.mockReturnValue({ user: { role: 'user' }, loading: false });
  render(<ProtectedRoute adminOnly />);

  expect(screen.getByRole('heading', { name: 'Redirection /externe/HomePage' })).toBeInTheDocument();
});

test('autorise la route admin à un administrateur', () => {
  useAuth.mockReturnValue({ user: { role: 'admin' }, loading: false });
  render(<ProtectedRoute adminOnly />);

  expect(screen.getByRole('heading', { name: 'Contenu protégé' })).toBeInTheDocument();
});
