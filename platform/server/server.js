// server.js
require("dotenv").config();
const express = require("express");
const cors = require("cors");
const authRoutes = require("./routes/auth");

const app = express();
app.use(cors());
app.use(express.json());

app.use("/auth", authRoutes);

app.get("/", (req, res) => res.send("Service READ (login) OK"));

const port = process.env.PORT || 5000;
app.listen(port, () => console.log(`Read service running on ${port}`));
