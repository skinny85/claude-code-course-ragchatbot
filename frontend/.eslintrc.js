module.exports = {
  env: {
    browser: true,
    es2021: true,
  },
  extends: ['standard'],
  globals: {
    marked: 'readonly',
  },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  rules: {
    'no-console': 'warn',
    'no-unused-vars': 'warn',
    'prefer-const': 'error',
    'no-var': 'error',
  },
  overrides: [
    {
      files: ['*.html'],
      parser: '@html-eslint/parser',
      plugins: ['@html-eslint'],
      extends: ['plugin:@html-eslint/recommended'],
      rules: {
        'spaced-comment': 'off',
        '@html-eslint/indent': ['error', 2],
        '@html-eslint/require-doctype': 'error',
        '@html-eslint/require-lang': 'error',
        '@html-eslint/no-duplicate-attrs': 'error',
        '@html-eslint/no-inline-styles': 'warn',
      },
    },
  ],
};
