// routes/auth.js
const express = require("express");
const router = express.Router();
const bcrypt = require("bcryptjs");
const pool = require("../db");

router.post("/register", async (req, res) => {
  try {
    const { username, email, password } = req.body;
    if (!username || !email || !password) {
      return res.status(400).json({ error: "Champs manquants" });
    }

    const [exists] = await pool.execute(
      "SELECT id FROM users WHERE username = ? OR email = ?",
      [username, email]
    );
    if (exists.length > 0) {
      return res.status(409).json({ error: "Username ou email déjà utilisé" });
    }

    const hashed = await bcrypt.hash(password, 10);

    await pool.execute(
      "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
      [username, email, hashed]
    );

    res.status(201).json({ message: "Utilisateur créé" });
  } catch (err) {
    console.error("Register error:", err);
    res.status(500).json({ error: "Erreur serveur" });
  }
});

module.exports = router;
