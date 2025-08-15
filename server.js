import express from "express";
import axios from "axios";
import dotenv from "dotenv";
import cors from "cors";

dotenv.config();

const app = express();
app.use(express.json());
app.use(cors());

app.post("/api/recipes", async (req, res) => {
  const { prompt } = req.body;

  try {
    const response = await axios.post(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        model: "gpt-4o-mini", // or whichever OpenRouter model you want
        messages: [
          {
            role: "system",
            content: "You are a recipe generator. Respond in JSON format with a title, ingredients, and instructions."
          },
          {
            role: "user",
            content: prompt
          }
        ],
        temperature: 0.7,
      },
      {
        headers: {
          Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );

    const text = response.data.choices[0].message.content;

    let recipes;
    try {
      recipes = JSON.parse(text);
    } catch {
      recipes = [{ title: "AI Recipe", ingredients: [], instructions: text }];
    }

    res.json({ recipes });
  } catch (error) {
    console.error("OpenRouter API error:", error.response?.data || error.message);
    res.status(500).json({
      recipes: [{ title: "Error", ingredients: [], instructions: "Failed to fetch recipes." }]
    });
  }
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => console.log(`Backend running on port ${PORT}`));
