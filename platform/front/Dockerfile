# -----------------------------
# Étape 1 : Build de l'application React
# -----------------------------
FROM node:20-alpine AS build

# Dossier de travail
WORKDIR /app

# Copier package.json et package-lock.json
COPY app/package*.json ./

# Installer dépendances
RUN npm install

# Copier le reste du projet
COPY app/. .

# En production Docker, l'API est exposee sur la meme origine via Nginx.
ENV REACT_APP_API_BASE_URL=/api

# Build production
RUN npm run build

# -----------------------------
# Étape 2 : Serveur Nginx
# -----------------------------
FROM nginx:stable-alpine

# Copier les fichiers build React vers nginx
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exposer port 80
EXPOSE 80

# Lancer nginx
CMD ["nginx", "-g", "daemon off;"]
