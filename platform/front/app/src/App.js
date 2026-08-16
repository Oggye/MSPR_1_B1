// App.js
import './App.css';
import { BrowserRouter } from 'react-router-dom';
// Import des pages
import AppRoutes from './routes/index';
import { AuthProvider } from './auth/AuthContext';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
