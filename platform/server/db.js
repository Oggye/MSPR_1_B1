// db.js
const mysql = require("mysql2/promise");

const {
  DB_HOST = "db",
  DB_USER = "user",
  DB_PASSWORD = "1234",
  DB_NAME = "g4",
  DB_PORT = 3306
} = process.env;

const pool = mysql.createPool({
  host: DB_HOST,
  user: DB_USER,
  password: DB_PASSWORD,
  database: DB_NAME,
  port: DB_PORT,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

module.exports = pool;
