-- ---------------------------
-- Table: User
-- ---------------------------
CREATE TABLE users (
    id_user INT AUTO_INCREMENT PRIMARY KEY,
    Nom VARCHAR(100) NOT NULL,
    Prenom VARCHAR(100) NOT NULL,
    Email VARCHAR(150) NOT NULL UNIQUE,
    Pwd VARCHAR(255) NOT NULL,
    Date_creation DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------
-- Table: Favori
-- ---------------------------
CREATE TABLE favoris (
    id_favori INT AUTO_INCREMENT PRIMARY KEY,
    id_users INT NOT NULL,
    id_morceau BIGINT NOT NULL,
    Date_ajout DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_users) REFERENCES users(id_user)
);

-- ---------------------------
-- Table: Playlist
-- ---------------------------
CREATE TABLE playlists (
    id_playlist INT AUTO_INCREMENT PRIMARY KEY,
    id_users INT NOT NULL,
    Titre VARCHAR(150) NOT NULL,
    Description TEXT,
    Date_creation DATETIME DEFAULT CURRENT_TIMESTAMP,
    Public BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_users) REFERENCES users(id_user)
);

-- ---------------------------
-- Table: Playlist_morceau
-- ---------------------------
CREATE TABLE playlist_morceau (
    id_playlists INT NOT NULL,
    id_morceau BIGINT NOT NULL,
    Ordre INT NOT NULL,
    PRIMARY KEY (id_playlists, id_morceau),
    FOREIGN KEY (id_playlists) REFERENCES playlists(id_playlist)
);

