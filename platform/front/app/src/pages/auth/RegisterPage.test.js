import { fireEvent, render, screen } from '@testing-library/react';
import RegisterPage from './RegisterPage';

jest.mock('../../services/auth', () => ({ registerAccount: jest.fn() }));
jest.mock('react-router-dom', () => ({
  Link: ({ children }) => <a href="/">{children}</a>,
  useNavigate: () => jest.fn(),
}), { virtual: true });

test('affiche le code administrateur uniquement lorsque la case est cochée', () => {
  render(<RegisterPage />);

  const adminCheckbox = screen.getByRole('checkbox', { name: 'Je suis administrateur' });
  expect(screen.queryByLabelText(/Code administrateur/)).not.toBeInTheDocument();

  fireEvent.click(adminCheckbox);
  expect(screen.getByLabelText(/Code administrateur/)).toBeInTheDocument();

  fireEvent.click(adminCheckbox);
  expect(screen.queryByLabelText(/Code administrateur/)).not.toBeInTheDocument();
});
