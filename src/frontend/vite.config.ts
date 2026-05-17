import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
    const isDev = mode === 'development'

    return {
        plugins: [react()],
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './src'),
            },
        },
        server: {
            port: 3000,
            strictPort: true,  // Fail if port 3000 is taken

            // CRITICAL: Proxy configuration
            proxy: isDev ? {
                '/api': {
                    target: 'http://localhost:8000',
                    changeOrigin: true,
                    // Remove /api prefix when forwarding to backend
                    rewrite: (path) => path.replace(/^\/api/, ''),

                    // Log proxy activity for debugging
                    configure: (proxy, _options) => {
                        proxy.on('error', (err, _req, _res) => {
                            console.log('Proxy error:', err.message)
                        })
                        proxy.on('proxyReq', (proxyReq, req, _res) => {
                            console.log('Proxy request:', req.method, req.url, '→', proxyReq.path)
                        })
                        proxy.on('proxyRes', (proxyRes, req, _res) => {
                            console.log('Proxy response:', proxyRes.statusCode, req.url)
                        })
                    },
                },
            } : undefined,
        },
        build: {
            outDir: 'dist',
            sourcemap: true,
            rollupOptions: {
                output: {
                    manualChunks: {
                        three: ['three', '@react-three/fiber', '@react-three/drei'],
                        charts: ['recharts'],
                        vendor: ['react', 'react-dom', 'react-router-dom', 'framer-motion'],
                    },
                },
            },
        },
        // Ensure env vars are exposed
        envPrefix: 'VITE_',
    }
})