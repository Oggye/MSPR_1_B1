// routes/auth.js
const express = require("express");
const router = express.Router();
const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const pool = require("../db");

const JWT_SECRET = process.env.JWT_SECRET || "changeme";

router.post("/login", async (req, res) => {
  try {
    const { identifier, password } = req.body; // identifier = username ou email
    if (!identifier || !password) return res.status(400).json({ error: "Champs manquants" });

    const [rows] = await pool.execute(
      "SELECT id, username, email, password FROM users WHERE username = ? OR email = ?",
      [identifier, identifier]
    );

    if (rows.length === 0) return res.status(401).json({ error: "Utilisateur introuvable" });

    const user = rows[0];
    const match = await bcrypt.compare(password, user.password);
    if (!match) return res.status(401).json({ error: "Mot de passe incorrect" });

    const token = jwt.sign({ id: user.id, username: user.username, email: user.email }, JWT_SECRET, {
      expiresIn: "7d"
    });

    res.json({ message: "Connecté", token, user: { id: user.id, username: user.username, email: user.email } });
  } catch (err) {
    console.error("Login error:", err);
    res.status(500).json({ error: "Erreur serveur" });
  }
});

module.exports = router;
