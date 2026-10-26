import js from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier/flat";
import globals from "globals";

export default [
  {
    ignores: [
      "app/static/js/fullcalendar/",
      "node_modules/",
      ".venv/",
      "data/",
      "storage/",
      "instance/",
    ],
  },
  js.configs.recommended,
  {
    // Classic <script> tags sharing the window.CineTagIt namespace
    files: ["app/static/js/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: { ...globals.browser, CineTagIt: "writable" },
    },
  },
  {
    files: ["app/static/js/sw.js"],
    languageOptions: { globals: { ...globals.serviceworker } },
  },
  eslintConfigPrettier,
];
