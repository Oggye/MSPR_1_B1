import { Link } from 'react-router-dom';

import '../auth/AuthPages.css';

export default function LegalPage() {
  return (
    <main className="auth-page">
      <article className="auth-card legal-card">
        <h1>Conditions et confidentialité</h1>
        <section>
          <h2>Conditions générales d’utilisation</h2>
          <p>
            ObRail fournit un accès informatif aux données ferroviaires et à ses outils de prévision.
            Chaque utilisateur doit conserver ses identifiants confidentiels et utiliser le service de manière licite.
          </p>
        </section>
        <section>
          <h2>Politique de confidentialité</h2>
          <p>
            Nous collectons l’email, le rôle et les données techniques strictement nécessaires à la création du compte,
            à l’authentification et au contrôle des accès. Le mot de passe n’est jamais stocké en clair : seul un hash
            sécurisé Argon2 est conservé.
          </p>
          <p>
            Un cookie technique HttpOnly maintient la session pendant une durée limitée. Les données sont conservées
            tant que le compte est nécessaire au service. Vous pouvez demander l’accès, la rectification ou la suppression
            de vos données en contactant l’équipe responsable du projet ObRail.
          </p>
          <p>Cette présentation synthétique ne constitue pas un document juridique exhaustif.</p>
        </section>
        <Link to="/">Retour à l’accueil</Link>
      </article>
    </main>
  );
}
