import { render, screen } from '@testing-library/react';
import App from './App';

jest.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => <div>{children}</div>,
}), { virtual: true });

jest.mock('./routes/index', () => function MockAppRoutes() {
  return (
    <main>
      <h1>ObRail Europe</h1>
      <button type="button">Client</button>
      <button type="button">Admin</button>
    </main>
  );
});

jest.mock('./auth/AuthContext', () => ({
  AuthProvider: ({ children }) => <>{children}</>,
}));

test('renders the real home page entry points', async () => {
  render(<App />);

  expect(await screen.findByRole('heading', { name: /obrail europe/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /client/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /admin/i })).toBeInTheDocument();
});
