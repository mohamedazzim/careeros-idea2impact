import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [".next/", "node_modules/", "dist/"],
  },
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    rules: {
      "no-unused-vars": "warn",
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-expressions": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      "no-console": "off",
      "prefer-const": "off",
    },
  },
);
