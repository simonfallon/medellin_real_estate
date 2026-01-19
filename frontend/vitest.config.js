
import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
    test: {
        environment: 'happy-dom', // Simulates browser environment
    },
    resolve: {
        alias: {
            '/static': path.resolve(__dirname, './'),
            '/static/utils.js': path.resolve(__dirname, './utils.js')
        },
    },
});
