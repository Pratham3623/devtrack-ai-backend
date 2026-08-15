module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/tests/frontend/setup.js'],
  testMatch: ['**/tests/frontend/**/*.test.js'],
  moduleFileExtensions: ['js', 'json'],
  transform: {},
  verbose: true,
  collectCoverageFrom: [
    'app/static/**/*.js',
    '!**/node_modules/**'
  ]
};
