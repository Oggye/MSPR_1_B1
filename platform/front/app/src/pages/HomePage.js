// fichier : platform/front/app/src/pages/HomePage.js

import { useNavigate } from 'react-router-dom';
import './HomePage.css';
import { useEffect } from 'react';
import { getHealth } from '../services/api';
import { useAuth } from '../auth/AuthContext';

export default function HomePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  useEffect(() => {
    getHealth()
      .then(res => console.log('✅ API connectée :', res.data))
      .catch(err => console.error('❌ API indisponible :', err.message));
  }, []);

  return (
    <div className="home-page">
      <div className="home-page__content">
        <p className="home-page__subtitle">Bienvenue sur</p>
        <h1>ObRail Europe</h1>
        <div className="home-page__actions">
          {!user ? (
            <>
              <button type="button" onClick={() => navigate('/login')}>Se connecter</button>
              <button type="button" onClick={() => navigate('/register')}>Créer un compte</button>
              <button type="button" onClick={() => navigate('/legal')}>Conditions</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => navigate('/externe/HomePage')}>Espace client</button>
              <button type="button" className="home-page__btn--ia" onClick={() => navigate('/ia')}>IA</button>
              {user.role === 'admin' && (
                <button type="button" onClick={() => navigate('/interne/HomePage')}>Administration</button>
              )}
              <button type="button" onClick={logout}>Déconnexion</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
