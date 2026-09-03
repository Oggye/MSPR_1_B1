import { render, screen } from '@testing-library/react';

import LayoutInterne from './LayoutInterne';
import { useAuth } from '../auth/AuthContext';

jest.mock('react-router-dom', () => ({
  NavLink: ({ children, className, to }) => {
    const isActive = to === '/ia';
    return (
      <a
        href={to}
        className={className({ isActive })}
        aria-current={isActive ? 'page' : undefined}
      >
        {children}
      </a>
    );
  },
  Outlet: () => <h1>Prévisions IA</h1>,
  useLocation: () => ({ pathname: '/ia' }),
}), { virtual: true });

jest.mock('../auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

test('affiche la navigation IA et indique la page active', () => {
  useAuth.mockReturnValue({
    user: { email: 'user@example.com', role: 'user' },
    logout: jest.fn(),
  });

  render(<LayoutInterne />);

  expect(screen.getByRole('navigation', { name: 'Navigation IA' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'IA' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('link', { name: 'Espace externe' })).toHaveAttribute(
    'href',
    '/externe/HomePage'
  );
  expect(screen.queryByRole('link', { name: 'Supervision' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Prévisions IA' })).toBeInTheDocument();
});
